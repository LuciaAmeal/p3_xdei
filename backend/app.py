"""
XDEI Backend - Flask Application

Main application entry point with health check and service status endpoints.
"""

import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request, make_response
from clients.orion import OrionClient, OrionClientConflict, OrionClientError
from clients.quantumleap import QuantumLeapClient
from clients.mqtt import MQTTClient
from config import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Initialize Flask app
app = Flask(__name__)


@app.before_request
def _handle_options_preflight():
    """Respond to CORS preflight requests early to simplify browser calls."""
    if request.method == 'OPTIONS':
        resp = make_response()
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return resp


@app.after_request
def _add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# Initialize FIWARE clients with configuration
orion_client = OrionClient(
    base_url=settings.orion.url,
    timeout=settings.orion.timeout,
    retries=settings.orion.retries,
    fiware_headers=settings.get_fiware_headers(),
)

ql_client = QuantumLeapClient(
    base_url=settings.quantumleap.url,
    timeout=settings.quantumleap.timeout,
    retries=settings.quantumleap.retries,
    fiware_headers=settings.get_fiware_headers(),
)

mqtt_client = MQTTClient(
    host=settings.mqtt.host,
    port=settings.mqtt.port,
    timeout=settings.mqtt.timeout,
    keepalive=settings.mqtt.keepalive,
)

VEHICLE_STATE_HISTORY_SUBSCRIPTION_ID = "urn:ngsi-ld:Subscription:vehicle-state-history"
VEHICLE_STATE_HISTORY_WATCHED_ATTRS = [
    "currentPosition",
    "delaySeconds",
    "occupancy",
    "speedKmh",
    "heading",
    "status",
    "trip",
]


def _attribute_value(entity: Dict[str, Any], name: str, default: Any = None) -> Any:
    attribute = entity.get(name)
    if isinstance(attribute, dict):
        return attribute.get("value", default)
    return default


def _relationship_object(entity: Dict[str, Any], name: str) -> Optional[str]:
    attribute = entity.get(name)
    if isinstance(attribute, dict):
        object_id = attribute.get("object")
        if isinstance(object_id, str):
            return object_id
    return None


def _line_coordinates(entity: Dict[str, Any]) -> List[List[float]]:
    location = entity.get("location")
    if not isinstance(location, dict):
        return []

    value = location.get("value")
    if not isinstance(value, dict):
        return []

    if value.get("type") != "LineString":
        return []

    coordinates = value.get("coordinates")
    if not isinstance(coordinates, list):
        return []

    normalized: List[List[float]] = []
    for coordinate in coordinates:
        if isinstance(coordinate, list) and len(coordinate) >= 2:
            normalized.append([coordinate[0], coordinate[1]])
    return normalized


def _point_coordinates(entity: Dict[str, Any]) -> Optional[List[float]]:
    location = entity.get("location")
    if not isinstance(location, dict):
        return None

    value = location.get("value")
    if not isinstance(value, dict):
        return None

    if value.get("type") != "Point":
        return None

    coordinates = value.get("coordinates")
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        return [coordinates[0], coordinates[1]]
    return None


def _geo_property_coordinates(entity: Dict[str, Any], name: str) -> Optional[List[float]]:
    attribute = entity.get(name)
    if not isinstance(attribute, dict):
        return None

    value = attribute.get("value")
    if not isinstance(value, dict):
        return None

    if value.get("type") != "Point":
        return None

    coordinates = value.get("coordinates")
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        return [coordinates[0], coordinates[1]]
    return None


def _shape_coordinates(entity: Dict[str, Any]) -> List[List[float]]:
    points = _attribute_value(entity, "shapePoints", [])
    if isinstance(points, list):
        normalized: List[List[float]] = []
        for coordinate in points:
            if isinstance(coordinate, list) and len(coordinate) >= 2:
                normalized.append([coordinate[0], coordinate[1]])
        if normalized:
            return normalized

    return _line_coordinates(entity)


def _safe_entity_list(entity_type: str) -> List[Dict[str, Any]]:
    try:
        return orion_client.get_entities(entity_type=entity_type, limit=500)
    except Exception as exc:
        logger.warning("Unable to load %s entities from Orion-LD: %s", entity_type, exc)
        return []


def _build_route_payloads() -> List[Dict[str, Any]]:
    routes = _safe_entity_list("GtfsRoute")
    trips = _safe_entity_list("GtfsTrip")
    shapes = _safe_entity_list("GtfsShape")
    stops = _safe_entity_list("GtfsStop")
    stop_times = _safe_entity_list("GtfsStopTime")

    shapes_by_id = {
        shape["id"]: _shape_coordinates(shape)
        for shape in shapes
        if isinstance(shape, dict) and shape.get("id")
    }

    trips_by_route: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for trip in trips:
        route_id = _relationship_object(trip, "hasRoute")
        if route_id:
            trips_by_route[route_id].append(trip)

    stop_ids_by_trip: Dict[str, List[str]] = defaultdict(list)
    for stop_time in stop_times:
        trip_id = _relationship_object(stop_time, "hasTrip")
        stop_id = _relationship_object(stop_time, "hasStop")
        if trip_id and stop_id:
            stop_ids_by_trip[trip_id].append(stop_id)

    stop_lookup = {stop["id"]: stop for stop in stops if isinstance(stop, dict) and stop.get("id")}

    payloads: List[Dict[str, Any]] = []
    for route in routes:
        route_id = route.get("id")
        if not route_id:
            continue

        related_trips = trips_by_route.get(route_id, [])
        path: List[List[float]] = []
        for trip in related_trips:
            shape_id = _relationship_object(trip, "hasShape") or _attribute_value(trip, "shapeId")
            if shape_id and shape_id in shapes_by_id and shapes_by_id[shape_id]:
                path = shapes_by_id[shape_id]
                break

        route_stop_ids: List[str] = []
        for trip in related_trips:
            for stop_id in stop_ids_by_trip.get(trip.get("id", ""), []):
                if stop_id not in route_stop_ids:
                    route_stop_ids.append(stop_id)

        payloads.append(
            {
                "id": route_id,
                "routeShortName": _attribute_value(route, "routeShortName"),
                "routeLongName": _attribute_value(route, "routeLongName"),
                "routeDesc": _attribute_value(route, "routeDesc"),
                "routeType": _attribute_value(route, "routeType"),
                "routeColor": _attribute_value(route, "routeColor"),
                "routeTextColor": _attribute_value(route, "routeTextColor"),
                "operatorName": _attribute_value(route, "operatorName"),
                "path": path,
                "tripIds": [trip.get("id") for trip in related_trips if trip.get("id")],
                "stopIds": route_stop_ids,
                "stops": [
                    {
                        "id": stop_id,
                        "stopName": _attribute_value(stop_lookup.get(stop_id, {}), "stopName"),
                    }
                    for stop_id in route_stop_ids
                    if stop_id in stop_lookup
                ],
            }
        )

    return payloads


def _build_stop_payloads() -> List[Dict[str, Any]]:
    stops = _safe_entity_list("GtfsStop")
    payloads: List[Dict[str, Any]] = []

    for stop in stops:
        stop_id = stop.get("id")
        if not stop_id:
            continue
        payloads.append(
            {
                "id": stop_id,
                "stopName": _attribute_value(stop, "stopName"),
                "stopCode": _attribute_value(stop, "stopCode"),
                "stopDesc": _attribute_value(stop, "stopDesc"),
                "platformCode": _attribute_value(stop, "platformCode"),
                "wheelchairBoarding": _attribute_value(stop, "wheelchairBoarding"),
                "zoneId": _attribute_value(stop, "zoneId"),
                "location": _point_coordinates(stop),
            }
        )

    return payloads


def _build_vehicle_payloads() -> List[Dict[str, Any]]:
    vehicles = _safe_entity_list("VehicleState")
    payloads: List[Dict[str, Any]] = []

    for vehicle in vehicles:
        vehicle_id = vehicle.get("id")
        if not vehicle_id:
            continue

        payloads.append(
            {
                "id": vehicle_id,
                "vehicleId": vehicle_id.split(":")[-1],
                "tripId": _relationship_object(vehicle, "trip"),
                "currentStopId": _relationship_object(vehicle, "currentStop"),
                "currentPosition": _geo_property_coordinates(vehicle, "currentPosition"),
                "delaySeconds": _attribute_value(vehicle, "delaySeconds"),
                "occupancy": _attribute_value(vehicle, "occupancy"),
                "speedKmh": _attribute_value(vehicle, "speedKmh"),
                "heading": _attribute_value(vehicle, "heading"),
                "status": _attribute_value(vehicle, "status"),
                "nextStopName": _attribute_value(vehicle, "nextStopName"),
                "predictedArrivalTime": _attribute_value(vehicle, "predictedArrivalTime"),
            }
        )

    return payloads


def build_vehicle_state_history_subscription() -> dict:
    """Build the NGSI-LD subscription used to persist VehicleState changes."""
    return {
        "id": VEHICLE_STATE_HISTORY_SUBSCRIPTION_ID,
        "type": "Subscription",
        "description": "Persist VehicleState changes in QuantumLeap",
        "entities": [
            {
                "type": "VehicleState",
            }
        ],
        "watchedAttributes": VEHICLE_STATE_HISTORY_WATCHED_ATTRS,
        "notification": {
            "attributes": VEHICLE_STATE_HISTORY_WATCHED_ATTRS,
            "endpoint": {
                "uri": f"{settings.quantumleap.url.rstrip('/')}/v2/notify",
                "accept": "application/ld+json",
            },
        },
    }


def ensure_vehicle_state_history_subscription(max_attempts: int = 30, retry_delay_seconds: int = 2) -> bool:
    """Ensure the historical subscription exists before the backend starts serving traffic."""
    subscription = build_vehicle_state_history_subscription()

    for attempt in range(1, max_attempts + 1):
        try:
            existing_subscriptions = orion_client.get_subscriptions()
            if any(item.get("id") == subscription["id"] for item in existing_subscriptions):
                logger.info("VehicleState historical subscription already exists")
                return False

            orion_client.create_subscription(subscription)
            logger.info("Created VehicleState historical subscription")
            return True

        except OrionClientConflict:
            logger.info("VehicleState historical subscription already exists")
            return False
        except OrionClientError as exc:
            logger.warning(
                "Attempt %s/%s to create VehicleState historical subscription failed: %s",
                attempt,
                max_attempts,
                exc,
            )
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)

    raise RuntimeError("Unable to create VehicleState historical subscription")


@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint that validates FIWARE service connectivity.
    
    Returns:
        JSON response with overall status and per-service health:
        - status: 'healthy', 'degraded', or 'unhealthy'
        - services: dict with individual service status
        - timestamp: ISO8601 timestamp
    """
    services_status = {}
    overall_status = 'healthy'
    
    # Check Orion-LD
    try:
        if orion_client.health_check():
            services_status['orion-ld'] = {
                'status': 'ok',
                'url': settings.orion.url,
            }
        else:
            services_status['orion-ld'] = {
                'status': 'error',
                'url': settings.orion.url,
            }
            overall_status = 'degraded'
    except Exception as e:
        services_status['orion-ld'] = {
            'status': 'error',
            'url': settings.orion.url,
            'error': str(e),
        }
        overall_status = 'degraded'
        logger.warning(f"Orion-LD health check failed: {e}")
    
    # Check QuantumLeap
    try:
        if ql_client.health_check():
            services_status['quantumleap'] = {
                'status': 'ok',
                'url': settings.quantumleap.url,
            }
        else:
            services_status['quantumleap'] = {
                'status': 'error',
                'url': settings.quantumleap.url,
            }
            overall_status = 'degraded'
    except Exception as e:
        services_status['quantumleap'] = {
            'status': 'error',
            'url': settings.quantumleap.url,
            'error': str(e),
        }
        overall_status = 'degraded'
        logger.warning(f"QuantumLeap health check failed: {e}")
    
    # Check MQTT
    try:
        mqtt_client.connect()
        if mqtt_client.is_connected:
            services_status['mqtt'] = {
                'status': 'ok',
                'host': settings.mqtt.host,
                'port': settings.mqtt.port,
            }
            mqtt_client.disconnect()
        else:
            services_status['mqtt'] = {
                'status': 'error',
                'host': settings.mqtt.host,
                'port': settings.mqtt.port,
            }
            overall_status = 'degraded'
    except Exception as e:
        services_status['mqtt'] = {
            'status': 'error',
            'host': settings.mqtt.host,
            'port': settings.mqtt.port,
            'error': str(e),
        }
        overall_status = 'degraded'
        logger.warning(f"MQTT health check failed: {e}")
    
    response = {
        'status': overall_status,
        'services': services_status,
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    }
    
    # Return 200 for healthy/degraded, 503 for unhealthy
    http_status = 200 if overall_status in ['healthy', 'degraded'] else 503
    
    return jsonify(response), http_status


@app.route('/api/ping', methods=['GET'])
def ping():
    """
    Simple ping endpoint for basic connectivity check.
    
    Returns:
        JSON response with ping acknowledgment
    """
    return jsonify(ping='pong'), 200


@app.route('/api/routes', methods=['GET'])
def api_routes():
    """Return route data ready for Leaflet rendering."""
    return jsonify(routes=_build_route_payloads()), 200


@app.route('/api/stops', methods=['GET'])
def api_stops():
    """Return stop data ready for Leaflet markers."""
    return jsonify(stops=_build_stop_payloads()), 200


@app.route('/api/vehicles/current', methods=['GET'])
def api_current_vehicles():
    """Return current VehicleState data for the frontend map."""
    return jsonify(vehicles=_build_vehicle_payloads()), 200


if __name__ == '__main__':
    logger.info(f"Starting XDEI Backend on {settings.app.flask_host}:{settings.app.flask_port}")
    ensure_vehicle_state_history_subscription()
    app.run(
        host=settings.app.flask_host,
        port=settings.app.flask_port,
        debug=(settings.app.flask_env == 'development'),
    )
