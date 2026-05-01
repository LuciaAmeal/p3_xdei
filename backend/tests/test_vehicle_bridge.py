"""Tests for the telemetry bridge from simulator MQTT to IoT Agent JSON."""

import json
from unittest.mock import Mock, patch

from vehicle_bridge import (
    BridgeConfig,
    VehicleTelemetryBridge,
    build_vehicle_state_measure,
    parse_vehicle_id,
)


def test_parse_vehicle_id():
    assert parse_vehicle_id("vehicle/bus-17/telemetry") == "bus-17"
    assert parse_vehicle_id("vehicle/bus-17/status") is None


def test_build_vehicle_state_measure_maps_telemetry_to_ngsi_ld():
    measure = build_vehicle_state_measure(
        "bus-17",
        {
            "lon": -3.7,
            "lat": 40.4,
            "speed": 27.5,
            "delay": 90,
            "occupancy": 42,
            "trip_id": "trip-12",
            "timestamp": "2026-01-01T12:00:00Z",
        },
        previous_position=(-3.71, 40.39),
    )

    assert measure["id"] == "urn:ngsi-ld:VehicleState:bus-17"
    assert measure["type"] == "VehicleState"
    assert measure["measure_id"]["value"] == "urn:ngsi-ld:VehicleState:bus-17"
    assert measure["measure_type"]["value"] == "VehicleState"
    assert measure["currentPosition"]["type"] == "GeoProperty"
    assert measure["currentPosition"]["value"]["coordinates"] == [-3.7, 40.4]
    assert measure["delaySeconds"]["value"] == 90
    assert measure["occupancy"]["value"] == 42
    assert measure["speedKmh"]["value"] == 27.5
    assert measure["trip"]["object"] == "urn:ngsi-ld:GtfsTrip:trip-12"


def test_bridge_forwards_telemetry_to_iot_agent_topic():
    bridge = VehicleTelemetryBridge(
        BridgeConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            mqtt_timeout=5,
            mqtt_keepalive=60,
            mqtt_prefix="json",
            telemetry_prefix="vehicle",
            default_key="1234",
            iot_agent_url="http://iot-agent-json:4041",
            context_broker_url="http://orion-ld:1026",
            fiware_headers={"Fiware-Service": "smartgondor", "Fiware-ServicePath": "/gardens"},
            entity_type="VehicleState",
        )
    )
    bridge.mqtt_client = Mock()

    bridge.handle_message(
        "vehicle/bus-17/telemetry",
        json.dumps(
            {
                "lon": -3.7,
                "lat": 40.4,
                "speed": 27.5,
                "delay": 90,
                "occupancy": 42,
                "trip_id": "trip-12",
                "timestamp": "2026-01-01T12:00:00Z",
            }
        ),
    )

    bridge.mqtt_client.publish.assert_called_once()
    topic, payload = bridge.mqtt_client.publish.call_args.args[:2]
    assert topic == "json/1234/bus-17/attrs"
    assert payload["type"] == "VehicleState"
    assert payload["status"]["value"] == "in_transit"


@patch("vehicle_bridge.requests.post")
def test_provision_iot_agent_group_uses_ngsi_ld_payload(mock_post):
    mock_post.return_value.status_code = 201
    bridge = VehicleTelemetryBridge(
        BridgeConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            mqtt_timeout=5,
            mqtt_keepalive=60,
            mqtt_prefix="json",
            telemetry_prefix="vehicle",
            default_key="1234",
            iot_agent_url="http://iot-agent-json:4041",
            context_broker_url="http://orion-ld:1026",
            fiware_headers={"Fiware-Service": "smartgondor", "Fiware-ServicePath": "/gardens"},
            entity_type="VehicleState",
        )
    )

    bridge.provision_iot_agent_group()

    assert mock_post.called
    request_kwargs = mock_post.call_args.kwargs
    assert request_kwargs["json"]["services"][0]["payloadType"] == "ngsild"
    assert request_kwargs["json"]["services"][0]["entityNameExp"] == "measure_id"
    assert request_kwargs["json"]["services"][0]["cbHost"] == "http://orion-ld:1026"