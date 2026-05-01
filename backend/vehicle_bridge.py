"""MQTT bridge from simulator telemetry to FIWARE IoT Agent JSON.

The simulator publishes compact vehicle telemetry on `vehicle/{id}/telemetry`.
This bridge converts those messages into NGSI-LD vehicle state measures and
forwards them to the IoT Agent JSON MQTT topic contract.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests

from clients.mqtt import MQTTClient
from config import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)

NGSI_LD_CONTEXT = ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bearing(previous: Tuple[float, float], current: Tuple[float, float]) -> float:
    """Calculate a simple compass bearing in degrees for consecutive points."""
    prev_lon, prev_lat = previous
    lon, lat = current
    lon1 = math.radians(prev_lon)
    lon2 = math.radians(lon)
    lat1 = math.radians(prev_lat)
    lat2 = math.radians(lat)
    delta_lon = lon2 - lon1

    x = math.sin(delta_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
    bearing = math.degrees(math.atan2(x, y))
    return round((bearing + 360.0) % 360.0, 2)


def parse_vehicle_id(topic: str, prefix: str = "vehicle") -> Optional[str]:
    """Extract the vehicle id from a telemetry topic."""
    parts = topic.strip("/").split("/")
    if len(parts) == 3 and parts[0] == prefix and parts[2] == "telemetry":
        return parts[1]
    return None


def build_vehicle_state_measure(
    vehicle_id: str,
    telemetry: Dict[str, Any],
    previous_position: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """Transform simulator telemetry into an NGSI-LD VehicleState measure."""
    lon = float(telemetry["lon"])
    lat = float(telemetry["lat"])
    heading = telemetry.get("heading")
    if heading is None and previous_position is not None:
        heading = _bearing(previous_position, (lon, lat))
    if heading is None:
        heading = 0.0

    trip_id = telemetry.get("trip_id")
    measure: Dict[str, Any] = {
        "id": f"urn:ngsi-ld:VehicleState:{vehicle_id}",
        "type": "VehicleState",
        "@context": NGSI_LD_CONTEXT,
        "measure_id": {
            "type": "Text",
            "value": f"urn:ngsi-ld:VehicleState:{vehicle_id}",
        },
        "measure_type": {
            "type": "Text",
            "value": "VehicleState",
        },
        "currentPosition": {
            "type": "GeoProperty",
            "value": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "observedAt": telemetry.get("timestamp", _now_iso()),
        },
        "delaySeconds": {
            "type": "Property",
            "value": telemetry.get("delay", 0),
            "observedAt": telemetry.get("timestamp", _now_iso()),
        },
        "occupancy": {
            "type": "Property",
            "value": telemetry.get("occupancy", 0),
            "observedAt": telemetry.get("timestamp", _now_iso()),
        },
        "speedKmh": {
            "type": "Property",
            "value": telemetry.get("speed", 0),
            "observedAt": telemetry.get("timestamp", _now_iso()),
        },
        "heading": {
            "type": "Property",
            "value": heading,
            "observedAt": telemetry.get("timestamp", _now_iso()),
        },
        "status": {
            "type": "Property",
            "value": telemetry.get("status", "in_transit"),
            "observedAt": telemetry.get("timestamp", _now_iso()),
        },
    }

    if trip_id:
        measure["trip"] = {
            "type": "Relationship",
            "object": f"urn:ngsi-ld:GtfsTrip:{trip_id}",
            "observedAt": telemetry.get("timestamp", _now_iso()),
        }

    return measure


@dataclass
class BridgeConfig:
    mqtt_host: str = field(default_factory=lambda: os.getenv("MQTT_HOST", settings.mqtt.host))
    mqtt_port: int = field(default_factory=lambda: int(os.getenv("MQTT_PORT", str(settings.mqtt.port))))
    mqtt_timeout: int = field(default_factory=lambda: int(os.getenv("MQTT_TIMEOUT", str(settings.mqtt.timeout))))
    mqtt_keepalive: int = field(default_factory=lambda: int(os.getenv("MQTT_KEEPALIVE", str(settings.mqtt.keepalive))))
    mqtt_prefix: str = field(default_factory=lambda: os.getenv("BRIDGE_MQTT_PREFIX", "json"))
    telemetry_prefix: str = field(default_factory=lambda: os.getenv("BRIDGE_TELEMETRY_PREFIX", "vehicle"))
    default_key: str = field(default_factory=lambda: os.getenv("BRIDGE_DEFAULT_KEY", "1234"))
    iot_agent_url: str = field(default_factory=lambda: os.getenv("IOTA_AGENT_URL", "http://iot-agent-json:4041"))
    context_broker_url: str = field(default_factory=lambda: os.getenv("ORION_URL", settings.orion.url))
    fiware_headers: Dict[str, str] = field(default_factory=settings.get_fiware_headers)
    entity_type: str = "VehicleState"


class VehicleTelemetryBridge:
    """Bridge simulator telemetry into FIWARE IoT Agent JSON."""

    def __init__(self, config: Optional[BridgeConfig] = None):
        self.config = config or BridgeConfig()
        self.mqtt_client = MQTTClient(
            host=self.config.mqtt_host,
            port=self.config.mqtt_port,
            timeout=self.config.mqtt_timeout,
            keepalive=self.config.mqtt_keepalive,
        )
        self._last_positions: Dict[str, Tuple[float, float]] = {}

    def provision_iot_agent_group(self) -> None:
        """Provision a reusable MQTT group for NGSI-LD measures."""
        payload = {
            "services": [
                {
                    "resource": "/iot/json",
                    "apikey": self.config.default_key,
                    "entity_type": self.config.entity_type,
                    "cbHost": self.config.context_broker_url,
                    "commands": [],
                    "lazy": [],
                    "attributes": [],
                    "static_attributes": [],
                    "transport": "MQTT",
                    "payloadType": "ngsild",
                    "entityNameExp": "measure_id",
                }
            ]
        }

        last_error: Optional[Exception] = None
        for _ in range(30):
            try:
                response = requests.post(
                    f"{self.config.iot_agent_url.rstrip('/')}/iot/services",
                    json=payload,
                    headers=self.config.fiware_headers,
                    timeout=15,
                )
                if response.status_code in (200, 201, 409):
                    return
                response.raise_for_status()
            except Exception as exc:  # pragma: no cover - retry loop is integration safety
                last_error = exc
                time.sleep(2)

        if last_error:
            raise last_error

    def _publish_measure(self, vehicle_id: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        previous = self._last_positions.get(vehicle_id)
        measure = build_vehicle_state_measure(vehicle_id, telemetry, previous)
        self._last_positions[vehicle_id] = (
            float(telemetry["lon"]),
            float(telemetry["lat"]),
        )

        topic = f"{self.config.mqtt_prefix}/{self.config.default_key}/{vehicle_id}/attrs"
        self.mqtt_client.publish(topic, measure)
        logger.info("Forwarded telemetry for %s to %s", vehicle_id, topic)
        return measure

    def handle_message(self, topic: str, payload: str) -> None:
        vehicle_id = parse_vehicle_id(topic, self.config.telemetry_prefix)
        if not vehicle_id:
            logger.debug("Ignoring MQTT topic %s", topic)
            return

        telemetry = json.loads(payload)
        self._publish_measure(vehicle_id, telemetry)

    def start(self) -> None:
        self.provision_iot_agent_group()
        self.mqtt_client.connect()
        self.mqtt_client.subscribe(
            f"{self.config.telemetry_prefix}/+/telemetry",
            self.handle_message,
        )
        logger.info(
            "Vehicle bridge listening on %s:%s and forwarding telemetry to IoT Agent JSON",
            self.config.mqtt_host,
            self.config.mqtt_port,
        )

    def stop(self) -> None:
        self.mqtt_client.disconnect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge vehicle telemetry into IoT Agent JSON")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    bridge = VehicleTelemetryBridge()
    bridge.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())