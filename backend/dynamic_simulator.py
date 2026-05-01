"""Dynamic vehicle simulator (Issue 7).

Publishes simple telemetry messages to MQTT topics `vehicle/{id}/telemetry`.
This implementation is intentionally small and testable; it uses GTFS feed
shapes to interpolate positions and computes basic telemetry fields.
"""
from __future__ import annotations

import argparse
import time
import datetime
import logging
import random
from typing import Optional

from clients.mqtt import MQTTClient
from config import settings
from load_gtfs import read_gtfs_feed
from utils.simulator_utils import (
    interpolate_along_line,
    cumulative_distances,
    trip_duration_seconds,
)

LOGGER = logging.getLogger(__name__)


def publish_telemetry(mqtt_client: MQTTClient, vehicle_id: str, payload: dict) -> None:
    topic = f"vehicle/{vehicle_id}/telemetry"
    mqtt_client.publish(topic, payload)


def simulate_once(mqtt_client: MQTTClient, vehicle_id: str, lon: float, lat: float, trip_id: str) -> dict:
    """Build and publish a single telemetry payload (testable helper)."""
    payload = {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "lon": lon,
        "lat": lat,
        "speed": round(random.uniform(5.0, 15.0), 2),
        "delay": 0,
        "occupancy": random.randint(5, 80),
    }
    publish_telemetry(mqtt_client, vehicle_id, payload)
    return payload


def run_simulator(gtfs_zip: str, date: Optional[str], speed_factor: float, interval: Optional[int]) -> None:
    feed = read_gtfs_feed(gtfs_zip)

    # Minimal selection: use all trips that reference shapes
    trips_with_shape = [t for t in feed.trips if t.get("shape_id")]
    if not trips_with_shape:
        LOGGER.error("No trips with shapes found in GTFS feed")
        return

    mqtt_client = MQTTClient(
        host=settings.mqtt.host,
        port=settings.mqtt.port,
        timeout=settings.mqtt.timeout,
        keepalive=settings.mqtt.keepalive,
    )
    mqtt_client.connect()

    try:
        # For demo: simulate first trip only in a simple loop
        trip = trips_with_shape[0]
        shape_id = trip.get("shape_id")
        # find shape entity in feed.shapes
        shapes = [s for s in feed.shapes if s.get("shape_id") == shape_id]
        if not shapes:
            LOGGER.error("Shape points not found for shape_id %s", shape_id)
            return
        # build coordinates list: shapes file has shape_pt_lon, shape_pt_lat
        ordered = sorted(shapes, key=lambda r: float(r.get("shape_pt_sequence", "0")))
        coords = [(float(r["shape_pt_lon"]), float(r["shape_pt_lat"])) for r in ordered]
        cum = cumulative_distances(coords)
        total_m = cum[-1] if cum else 0.0

        # get stop_times for trip to estimate duration
        stop_times = [st for st in feed.stop_times if st.get("trip_id") == trip.get("trip_id")]
        duration = trip_duration_seconds(stop_times) or 60

        start_real = time.time()
        while True:
            elapsed = (time.time() - start_real) * speed_factor
            frac = (elapsed % duration) / max(1, duration)
            dist = frac * total_m
            lon, lat = interpolate_along_line(coords, dist)
            vehicle_id = f"veh_{trip.get('trip_id')}"
            simulate_once(mqtt_client, vehicle_id, lon, lat, trip.get("trip_id"))
            time.sleep(interval or settings.simulator.publish_interval_seconds)

    finally:
        mqtt_client.disconnect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run dynamic vehicle simulator from GTFS feed")
    parser.add_argument("gtfs_zip", help="Path to GTFS ZIP file")
    parser.add_argument("--date", help="Date to simulate (YYYY-MM-DD)")
    parser.add_argument("--speed-factor", type=float, default=settings.simulator.default_speed_factor)
    parser.add_argument("--interval", type=int, help="Publish interval seconds (overrides config)")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run_simulator(args.gtfs_zip, args.date, args.speed_factor, args.interval)
    except Exception as exc:
        LOGGER.exception("Simulator failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
