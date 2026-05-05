"""
XDEI Backend - Flask Application

Main application entry point with health check and service status endpoints.
"""

import math
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from flask import Flask, jsonify, request, make_response, g
import concurrent.futures
import requests
from clients.orion import OrionClient, OrionClientConflict, OrionClientError, OrionClientNotFound
from clients.quantumleap import QuantumLeapClient, QuantumLeapError, QuantumLeapNotFound
from clients.mqtt import MQTTClient
from config import settings
from auth import generate_jwt, JWTError
from prediction_service import (
    PredictionDependencyError,
    PredictionNotFoundError,
    PredictionServiceError,
    PredictionValidationError,
    StopCrowdPredictor,
)
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


@app.before_request
def _attach_request_id():
    """Attach a per-request id for log correlation."""
    try:
        rid = request.headers.get('X-Request-Id') or uuid4().hex
        # store on flask.g and request for access
        g.request_id = rid
        setattr(request, 'request_id', rid)
        logger.info('request.start', extra={'request_id': rid, 'method': request.method, 'path': request.path})
    except Exception:
        pass


@app.after_request
def _add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    # Propagate request id to clients
    try:
        rid = getattr(request, 'request_id', None) or getattr(g, 'request_id', None)
        if rid:
            response.headers['X-Request-Id'] = rid
    except Exception:
        pass
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

prediction_service = StopCrowdPredictor(
    orion_client=orion_client,
    ql_client=ql_client,
    cache_ttl_seconds=settings.prediction.cache_ttl_seconds,
    model_path=settings.prediction.model_path,
    model_version=settings.prediction.model_version,
    default_horizon_minutes=settings.prediction.default_horizon_minutes,
    history_window_days=settings.prediction.history_window_days,
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
VEHICLE_HISTORY_PAGE_SIZE_DEFAULT = 20
VEHICLE_HISTORY_PAGE_SIZE_MAX = 100
VEHICLE_HISTORY_SAMPLE_LIMIT = 1000
NGSI_LD_CONTEXT = [
    'https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld',
    'https://smartdatamodels.org/context.jsonld',
]
GAMIFICATION_TRIP_POINTS = 10
GAMIFICATION_NEW_STOP_BONUS = 5
GAMIFICATION_ACHIEVEMENT_RULES = [
    (1, 'first_trip'),
    (5, 'explorer_5'),
    (10, 'explorer_10'),
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


def _is_vehicle_state_entity_id(entity_id: str) -> bool:
    if not isinstance(entity_id, str):
        return False

    parts = entity_id.split(":")
    return len(parts) >= 4 and parts[2] == "VehicleState"


def _parse_history_int(raw_value: Optional[str], default: int, minimum: int = 1, maximum: Optional[int] = None) -> int:
    if raw_value in (None, ""):
        return default

    try:
        parsed_value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid integer value: {raw_value}") from exc

    if parsed_value < minimum:
        raise ValueError(f"Value must be at least {minimum}")

    if maximum is not None:
        parsed_value = min(parsed_value, maximum)

    return parsed_value


def _parse_history_datetime(raw_value: Optional[str]) -> Optional[str]:
    if raw_value in (None, ""):
        return None

    normalized = raw_value.strip()
    if not normalized:
        return None

    candidate = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO-8601 datetime: {raw_value}") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.isoformat().replace("+00:00", "Z")


def _normalize_history_value(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("type") == "Point":
            coordinates = value.get("coordinates")
            if isinstance(coordinates, list) and len(coordinates) >= 2:
                return [coordinates[0], coordinates[1]]

        if "object" in value and isinstance(value["object"], str):
            return value["object"]

        if "value" in value and not isinstance(value["value"], (dict, list)):
            return value["value"]

    return value


def _build_vehicle_history_records(series_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    timestamps = series_data.get("index")
    attributes = series_data.get("attributes")

    if not isinstance(timestamps, list) or not isinstance(attributes, list):
        return []

    records: List[Dict[str, Any]] = []
    for position, timestamp in enumerate(timestamps):
        record: Dict[str, Any] = {"timestamp": timestamp}

        for attribute in attributes:
            if not isinstance(attribute, dict):
                continue

            attr_name = attribute.get("attrName") or attribute.get("name")
            if not attr_name:
                continue

            values = attribute.get("values")
            if isinstance(values, list):
                if position >= len(values):
                    continue
                record[attr_name] = _normalize_history_value(values[position])
            elif position == 0:
                record[attr_name] = _normalize_history_value(values)

        records.append(record)

    return records


def _build_vehicle_history_payloads(from_date: Optional[str], to_date: Optional[str], vehicle_filter: Optional[str], page: int, page_size: int) -> Dict[str, Any]:
    available_entities = ql_client.get_available_entities()
    if isinstance(available_entities, dict):
        available_entities = available_entities.get("entities", [])

    vehicle_entity_ids = [
        entity_id
        for entity_id in available_entities
        if _is_vehicle_state_entity_id(entity_id)
    ]

    if vehicle_filter:
        vehicle_entity_ids = [
            entity_id
            for entity_id in vehicle_entity_ids
            if entity_id == vehicle_filter or entity_id.endswith(f":{vehicle_filter}")
        ]

    vehicle_histories: List[Dict[str, Any]] = []
    for entity_id in sorted(vehicle_entity_ids):
        try:
            series_data = ql_client.get_time_series(
                entity_id,
                attrs=VEHICLE_STATE_HISTORY_WATCHED_ATTRS,
                from_date=from_date,
                to_date=to_date,
                limit=VEHICLE_HISTORY_SAMPLE_LIMIT,
                offset=0,
            )
        except QuantumLeapNotFound:
            continue

        if not isinstance(series_data, dict):
            continue

        history_records = _build_vehicle_history_records(series_data)
        if not history_records:
            continue

        latest_record = history_records[-1]
        vehicle_histories.append(
            {
                "id": entity_id,
                "vehicleId": entity_id.split(":")[-1],
                "latestTimestamp": latest_record.get("timestamp"),
                "sampleCount": len(history_records),
                "history": history_records,
            }
        )

    total_vehicles = len(vehicle_histories)
    total_pages = math.ceil(total_vehicles / page_size) if total_vehicles else 0
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "vehicles": vehicle_histories[start:end],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "totalVehicles": total_vehicles,
            "totalPages": total_pages,
        },
    }


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


def _ngsi_property(value: Any) -> Dict[str, Any]:
    return {
        'type': 'Property',
        'value': value,
    }


def _authenticated_user_id() -> Optional[str]:
    """
    Extract and validate user ID from request headers.
    
    Supports two authentication methods (in order of preference):
    1. X-User-Id header (for backward compatibility with tests)
    2. Authorization: Bearer <JWT> header (validates JWT signature)
    
    Returns:
        User ID if authentication is valid, None otherwise
    """
    # Try X-User-Id header first (backward compatibility)
    user_id = request.headers.get('X-User-Id')
    if user_id:
        return user_id.strip() or None

    # Try Bearer token (JWT)
    authorization = request.headers.get('Authorization', '').strip()
    if authorization.lower().startswith('bearer '):
        token = authorization[7:].strip()
        if token:
            # Import here to avoid circular imports
            from auth import get_user_id_from_jwt
            user_id = get_user_id_from_jwt(token)
            if user_id:
                return user_id
    
    return None


def _identity_key(user_id: str) -> str:
    for prefix in ('urn:ngsi-ld:UserProfile:', 'urn:ngsi-ld:User:'):
        if user_id.startswith(prefix):
            return user_id[len(prefix):]
    return user_id


def _user_profile_entity_id(user_id: str) -> str:
    if user_id.startswith('urn:ngsi-ld:UserProfile:'):
        return user_id
    return f'urn:ngsi-ld:UserProfile:{user_id}'


def _redeemed_discount_entity_id(user_id: str) -> str:
    return f'urn:ngsi-ld:RedeemedDiscount:{_identity_key(user_id)}:{uuid4().hex}'


def _profile_from_entity(entity: Dict[str, Any]) -> Dict[str, Any]:
    visited_stops = _attribute_value(entity, 'visitedStops', [])
    if not isinstance(visited_stops, list):
        visited_stops = []

    achievements = _attribute_value(entity, 'achievements', [])
    if not isinstance(achievements, list):
        achievements = []

    redeemed_discounts = _attribute_value(entity, 'redeemedDiscounts', [])
    if not isinstance(redeemed_discounts, list):
        redeemed_discounts = []

    entity_id = entity.get('id') if isinstance(entity.get('id'), str) else None
    return {
        'id': entity_id,
        'userId': _identity_key(entity_id) if entity_id else None,
        'displayName': _attribute_value(entity, 'displayName'),
        'totalPoints': int(_attribute_value(entity, 'totalPoints', 0) or 0),
        'visitedStops': visited_stops,
        'achievements': achievements,
        'lastActivityAt': _attribute_value(entity, 'lastActivityAt'),
        'redeemedDiscounts': redeemed_discounts,
    }


def _base_profile_payload(user_id: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    resolved_display_name = (display_name or user_id).strip() or user_id
    return {
        'id': _user_profile_entity_id(user_id),
        'type': 'UserProfile',
        '@context': NGSI_LD_CONTEXT,
        'displayName': _ngsi_property(resolved_display_name),
        'totalPoints': _ngsi_property(0),
        'visitedStops': _ngsi_property([]),
        'achievements': _ngsi_property([]),
        'lastActivityAt': _ngsi_property(None),
        'redeemedDiscounts': _ngsi_property([]),
    }


def _build_profile_entity(profile: Dict[str, Any]) -> Dict[str, Any]:
    user_id = profile.get('userId') or ''
    return {
        'id': _user_profile_entity_id(user_id),
        'type': 'UserProfile',
        '@context': NGSI_LD_CONTEXT,
        'displayName': _ngsi_property(profile.get('displayName')),
        'totalPoints': _ngsi_property(int(profile.get('totalPoints', 0) or 0)),
        'visitedStops': _ngsi_property(list(profile.get('visitedStops') or [])),
        'achievements': _ngsi_property(list(profile.get('achievements') or [])),
        'lastActivityAt': _ngsi_property(profile.get('lastActivityAt')),
        'redeemedDiscounts': _ngsi_property(list(profile.get('redeemedDiscounts') or [])),
    }


def _compute_gamification_achievements(total_points: int, visited_stops: List[str]) -> List[str]:
    achievements = []
    if total_points >= GAMIFICATION_TRIP_POINTS:
        achievements.append('first_trip')
    for minimum_visits, achievement_id in GAMIFICATION_ACHIEVEMENT_RULES[1:]:
        if len(visited_stops) >= minimum_visits:
            achievements.append(achievement_id)
    return list(dict.fromkeys(achievements))


def _load_user_profile(user_id: str) -> Dict[str, Any]:
    entity = orion_client.get_entity(_user_profile_entity_id(user_id))
    if not isinstance(entity, dict):
        raise OrionClientError('Invalid UserProfile payload')
    return entity


def _ensure_user_profile(user_id: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    try:
        return _load_user_profile(user_id)
    except OrionClientNotFound:
        entity = _base_profile_payload(user_id, display_name=display_name)
        orion_client.create_entity(entity)
        return entity


def _save_user_profile(profile: Dict[str, Any]) -> None:
    entity = _build_profile_entity(profile)
    try:
        orion_client.update_entity(
            entity['id'],
            {key: value for key, value in entity.items() if key not in {'id', 'type', '@context'}},
        )
    except OrionClientNotFound:
        orion_client.create_entity(entity)


def _parse_positive_int(value: Any, field_name: str) -> int:
    if value in (None, ''):
        raise ValueError(f'{field_name} is required')

    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{field_name} must be an integer') from exc

    if parsed_value <= 0:
        raise ValueError(f'{field_name} must be greater than 0')

    return parsed_value


def _parse_optional_datetime(value: Any, field_name: str) -> Optional[str]:
    if value in (None, ''):
        return None
    if not isinstance(value, str):
        raise ValueError(f'{field_name} must be an ISO-8601 string')
    try:
        return _parse_history_datetime(value)
    except ValueError as exc:
        raise ValueError(f'{field_name} must be an ISO-8601 string') from exc


def _resolve_request_user_id(expected_user_id: Optional[str] = None) -> str:
    user_id = _authenticated_user_id()
    if not user_id:
        raise PermissionError('Missing user authentication')

    if expected_user_id is not None and _identity_key(user_id) != _identity_key(expected_user_id):
        raise PermissionError('Authenticated user does not match requested profile')

    return user_id


def _update_profile_after_trip(profile: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    visited_stops = list(profile.get('visitedStops') or [])
    stop_id = payload.get('stopId') or payload.get('stop_id') or payload.get('stop')
    bonus_points = 0

    if isinstance(stop_id, str) and stop_id:
        if stop_id not in visited_stops:
            visited_stops.append(stop_id)
            bonus_points = GAMIFICATION_NEW_STOP_BONUS

    total_points = int(profile.get('totalPoints', 0) or 0) + GAMIFICATION_TRIP_POINTS + bonus_points
    updated_profile = dict(profile)
    updated_profile['visitedStops'] = visited_stops
    updated_profile['totalPoints'] = total_points
    updated_profile['lastActivityAt'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    updated_profile['achievements'] = _compute_gamification_achievements(total_points, visited_stops)
    return updated_profile


def _update_profile_after_redeem(profile: Dict[str, Any], redemption: Dict[str, Any], points_cost: int) -> Dict[str, Any]:
    current_points = int(profile.get('totalPoints', 0) or 0)
    if current_points < points_cost:
        raise ValueError('Insufficient points to redeem discount')

    redeemed_discounts = list(profile.get('redeemedDiscounts') or [])
    redeemed_discounts.append(redemption)

    updated_profile = dict(profile)
    updated_profile['totalPoints'] = current_points - points_cost
    updated_profile['redeemedDiscounts'] = redeemed_discounts
    updated_profile['lastActivityAt'] = redemption['redeemedAt']
    updated_profile['achievements'] = _compute_gamification_achievements(
        updated_profile['totalPoints'],
        list(profile.get('visitedStops') or []),
    )
    return updated_profile


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

    request_id = getattr(request, 'request_id', None) or getattr(g, 'request_id', None) or uuid4().hex

    # Helper to send alert webhook if configured
    def _send_alert_if_needed(rid: str, services: dict):
        webhook_url = os.getenv('ALERT_WEBHOOK_URL') or getattr(settings.app, 'alert_webhook_url', None)
        dry_run = os.getenv('ALERT_DRY_RUN', '').lower() in ('1', 'true', 'yes')
        if not webhook_url:
            return
        payload = {
            'request_id': rid,
            'services': services,
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        }
        if dry_run:
            logger.info('alert.dry_run', extra={'request_id': rid, 'alert_payload': payload})
            return
        try:
            requests.post(webhook_url, json=payload, timeout=5)
            logger.info('alert.sent', extra={'request_id': rid})
        except Exception as exc:
            logger.warning('Failed to send alert webhook: %s', exc, extra={'request_id': rid})

    # Run checks in parallel to reduce latency
    def _check_orion():
        start = time.monotonic()
        try:
            ok = orion_client.health_check()
            latency_ms = int((time.monotonic() - start) * 1000)
            if ok:
                return {'status': 'ok', 'url': settings.orion.url, 'latency_ms': latency_ms}
            return {'status': 'error', 'url': settings.orion.url, 'latency_ms': latency_ms}
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            return {'status': 'error', 'url': settings.orion.url, 'latency_ms': latency_ms, 'error': str(e)}

    def _check_ql():
        start = time.monotonic()
        try:
            ok = ql_client.health_check()
            latency_ms = int((time.monotonic() - start) * 1000)
            if ok:
                return {'status': 'ok', 'url': settings.quantumleap.url, 'latency_ms': latency_ms}
            return {'status': 'error', 'url': settings.quantumleap.url, 'latency_ms': latency_ms}
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            return {'status': 'error', 'url': settings.quantumleap.url, 'latency_ms': latency_ms, 'error': str(e)}

    def _check_mqtt():
        start = time.monotonic()
        try:
            mqtt_client.connect()
            connected = mqtt_client.is_connected
            latency_ms = int((time.monotonic() - start) * 1000)
            if connected:
                mqtt_client.disconnect()
                return {'status': 'ok', 'host': settings.mqtt.host, 'port': settings.mqtt.port, 'latency_ms': latency_ms}
            return {'status': 'error', 'host': settings.mqtt.host, 'port': settings.mqtt.port, 'latency_ms': latency_ms}
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            return {'status': 'error', 'host': settings.mqtt.host, 'port': settings.mqtt.port, 'latency_ms': latency_ms, 'error': str(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {
            'orion-ld': ex.submit(_check_orion),
            'quantumleap': ex.submit(_check_ql),
            'mqtt': ex.submit(_check_mqtt),
        }
        for name, fut in futs.items():
            try:
                services_status[name] = fut.result(timeout=10)
                if services_status[name].get('status') != 'ok':
                    overall_status = 'degraded'
            except Exception as exc:
                services_status[name] = {'status': 'error', 'error': str(exc)}
                overall_status = 'degraded'
                logger.warning('Health check %s failed: %s', name, exc, extra={'request_id': request_id})

    response = {
        'status': overall_status,
        'services': services_status,
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'request_id': request_id,
    }

    # Send alert if any service reports error (configurable webhook)
    try:
        if any(s.get('status') != 'ok' for s in services_status.values()):
            _send_alert_if_needed(request_id, services_status)
    except Exception:
        pass

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


@app.route('/api/login', methods=['POST'])
def login():
    """
    Mock login endpoint for development JWT authentication.
    
    Accepts any non-empty username and password combination.
    Returns a JWT token valid for 24 hours.
    
    Request body:
        {
            "username": "string (required, non-empty)",
            "password": "string (required, non-empty)"
        }
    
    Returns:
        {
            "token": "JWT_TOKEN_STRING",
            "user_id": "username",
            "expires_in_hours": 24
        }
    
    Status codes:
        200: Login successful
        400: Missing or empty credentials
        500: Token generation failed
    """
    try:
        # Check Content-Type if request has a body
        if request.data and request.content_type and 'application/json' not in request.content_type:
            return jsonify(error='Content-Type must be application/json'), 415
        
        data = request.get_json(force=False, silent=True) or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        # Validate credentials are not empty
        if not username or not password:
            return jsonify(error='Username and password are required'), 400
        
        # Generate JWT token
        token = generate_jwt(username)
        
        return jsonify(
            token=token,
            user_id=username,
            expires_in_hours=settings.jwt.expiration_hours
        ), 200
        
    except JWTError as e:
        logger.error(f"JWT generation error: {str(e)}")
        return jsonify(error='Token generation failed'), 500
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify(error='Login failed'), 500


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


@app.route('/api/vehicles/history', methods=['GET'])
def api_vehicle_history():
    """Return historical VehicleState data grouped by vehicle."""
    try:
        page = _parse_history_int(request.args.get("page"), default=1, minimum=1)
        page_size = _parse_history_int(
            request.args.get("pageSize"),
            default=VEHICLE_HISTORY_PAGE_SIZE_DEFAULT,
            minimum=1,
            maximum=VEHICLE_HISTORY_PAGE_SIZE_MAX,
        )
        from_date = _parse_history_datetime(request.args.get("fromDate"))
        to_date = _parse_history_datetime(request.args.get("toDate"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    vehicle_filter = request.args.get("vehicleId")

    try:
        payload = _build_vehicle_history_payloads(from_date, to_date, vehicle_filter, page, page_size)
    except QuantumLeapError as exc:
        logger.warning("Unable to load historical vehicle data: %s", exc)
        return jsonify(error="Unable to load historical vehicle data", detail=str(exc)), 502

    return jsonify(
        vehicles=payload["vehicles"],
        pagination=payload["pagination"],
        filters={
            "fromDate": from_date,
            "toDate": to_date,
            "vehicleId": vehicle_filter,
        },
    ), 200


@app.route('/api/predict', methods=['POST'])
def api_predict():
    """Predict occupancy for a stop using historical and current context."""
    payload = request.get_json(silent=True) or {}
    stop_id = payload.get("stopId") or payload.get("stop_id") or payload.get("stop") or payload.get("id")
    date_time = payload.get("dateTime") or payload.get("date_time") or payload.get("timestamp")
    raw_horizon_minutes = payload.get("horizonMinutes")
    if raw_horizon_minutes in (None, ""):
        raw_horizon_minutes = payload.get("horizon_minutes")

    try:
        horizon_minutes = _parse_history_int(
            str(raw_horizon_minutes) if raw_horizon_minutes not in (None, "") else None,
            default=settings.prediction.default_horizon_minutes,
            minimum=1,
            maximum=24 * 60,
        )
        normalized_date_time = _parse_history_datetime(date_time)
        prediction = prediction_service.predict(
            stop_id=stop_id,
            target_datetime=normalized_date_time,
            horizon_minutes=horizon_minutes,
        )
    except (ValueError, PredictionValidationError) as exc:
        return jsonify(error=str(exc)), 400
    except PredictionNotFoundError as exc:
        return jsonify(error=str(exc)), 404
    except PredictionDependencyError as exc:
        logger.warning("Prediction dependency error: %s", exc)
        return jsonify(error="Unable to generate prediction", detail=str(exc)), 502
    except PredictionServiceError as exc:
        logger.warning("Prediction service error: %s", exc)
        return jsonify(error="Unable to generate prediction", detail=str(exc)), 500

    return jsonify(prediction), 200

@app.route('/api/stops/<path:stop_id>/prediction', methods=['GET'])
def api_stop_prediction(stop_id):
    """Return a short stop prediction plus a 2-hour series for chart rendering."""
    try:
        prediction_horizon_minutes = _parse_history_int(
            request.args.get("horizonMinutes"),
            default=settings.prediction.default_horizon_minutes,
            minimum=1,
            maximum=24 * 60,
        )
        series_horizon_minutes = _parse_history_int(
            request.args.get("seriesHorizonMinutes"),
            default=120,
            minimum=1,
            maximum=24 * 60,
        )
        series_step_minutes = _parse_history_int(
            request.args.get("stepMinutes"),
            default=15,
            minimum=1,
            maximum=series_horizon_minutes,
        )
        normalized_date_time = _parse_history_datetime(request.args.get("dateTime") or request.args.get("date_time") or request.args.get("timestamp"))
        prediction = prediction_service.predict_series(
            stop_id=stop_id,
            target_datetime=normalized_date_time,
            prediction_horizon_minutes=prediction_horizon_minutes,
            series_horizon_minutes=series_horizon_minutes,
            series_step_minutes=series_step_minutes,
        )
    except (ValueError, PredictionValidationError) as exc:
        return jsonify(error=str(exc)), 400
    except PredictionNotFoundError as exc:
        return jsonify(error=str(exc)), 404
    except PredictionDependencyError as exc:
        logger.warning("Prediction dependency error: %s", exc)
        return jsonify(error="Unable to generate prediction", detail=str(exc)), 502
    except PredictionServiceError as exc:
        logger.warning("Prediction service error: %s", exc)
        return jsonify(error="Unable to generate prediction", detail=str(exc)), 500

    return jsonify(prediction), 200


@app.route('/api/user/<user_id>/profile', methods=['GET'])
def api_user_profile(user_id: str):
    """Return the authenticated user's gamification profile."""
    try:
        _resolve_request_user_id(user_id)
    except PermissionError as exc:
        return jsonify(error=str(exc)), 403 if 'match' in str(exc).lower() else 401

    try:
        entity = _load_user_profile(user_id)
    except OrionClientNotFound:
        return jsonify(error='User profile not found'), 404
    except OrionClientError as exc:
        logger.warning('Unable to load user profile: %s', exc)
        return jsonify(error='Unable to load user profile', detail=str(exc)), 502

    return jsonify(_profile_from_entity(entity)), 200


@app.route('/api/user/record-trip', methods=['POST'])
def api_user_record_trip():
    """Record trip activity for the authenticated user."""
    payload = request.get_json(silent=True) or {}
    trip_id = payload.get('tripId') or payload.get('trip_id')

    if not isinstance(trip_id, str) or not trip_id.strip():
        return jsonify(error='tripId is required'), 400

    try:
        request_user_id = _resolve_request_user_id(payload.get('userId') or payload.get('user_id'))
        display_name = request.headers.get('X-User-Name') or payload.get('displayName')
        profile_entity = _ensure_user_profile(
            request_user_id,
            display_name=display_name if isinstance(display_name, str) else None,
        )
        profile = _profile_from_entity(profile_entity)
        updated_profile = _update_profile_after_trip(profile, payload)
        _save_user_profile(updated_profile)
    except PermissionError as exc:
        return jsonify(error=str(exc)), 403 if 'match' in str(exc).lower() else 401
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except OrionClientError as exc:
        logger.warning('Unable to record trip for user profile: %s', exc)
        return jsonify(error='Unable to record trip', detail=str(exc)), 502

    return jsonify(updated_profile), 200


@app.route('/api/user/redeem', methods=['POST'])
def api_user_redeem():
    """Redeem points for a virtual discount."""
    payload = request.get_json(silent=True) or {}

    discount_code = payload.get('discountCode') or payload.get('discount_code') or payload.get('code')
    if not isinstance(discount_code, str) or not discount_code.strip():
        return jsonify(error='discountCode is required'), 400

    try:
        points_cost = _parse_positive_int(
            payload.get('pointsCost') or payload.get('points_cost') or payload.get('costPoints') or payload.get('cost'),
            'pointsCost',
        )
        discount_value = payload.get('discountValue') or payload.get('discount_value') or payload.get('value')
        if discount_value in (None, ''):
            discount_value = 0
        valid_until = _parse_optional_datetime(payload.get('validUntil') or payload.get('valid_until'), 'validUntil')
        request_user_id = _resolve_request_user_id(payload.get('userId') or payload.get('user_id'))
        display_name = request.headers.get('X-User-Name') or payload.get('displayName')
        profile_entity = _ensure_user_profile(
            request_user_id,
            display_name=display_name if isinstance(display_name, str) else None,
        )
        profile = _profile_from_entity(profile_entity)

        redeemed_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        redemption = {
            'discountCode': discount_code,
            'discountValue': discount_value,
            'redeemedAt': redeemed_at,
            'validUntil': valid_until,
            'status': 'redeemed',
        }
        updated_profile = _update_profile_after_redeem(profile, redemption, points_cost)
        _save_user_profile(updated_profile)

        redemption_entity = {
            'id': _redeemed_discount_entity_id(request_user_id),
            'type': 'RedeemedDiscount',
            '@context': NGSI_LD_CONTEXT,
            'discountCode': _ngsi_property(discount_code),
            'discountValue': _ngsi_property(discount_value),
            'redeemedAt': _ngsi_property(redeemed_at),
            'validUntil': _ngsi_property(valid_until),
            'status': _ngsi_property('redeemed'),
            'belongsToUser': {
                'type': 'Relationship',
                'object': _user_profile_entity_id(request_user_id),
            },
        }
        orion_client.create_entity(redemption_entity)
    except PermissionError as exc:
        return jsonify(error=str(exc)), 403 if 'match' in str(exc).lower() else 401
    except ValueError as exc:
        return jsonify(error=str(exc)), 400 if 'required' in str(exc).lower() or 'must' in str(exc).lower() else 409
    except OrionClientError as exc:
        logger.warning('Unable to redeem discount for user profile: %s', exc)
        return jsonify(error='Unable to redeem discount', detail=str(exc)), 502

    return jsonify({'profile': updated_profile, 'redemption': redemption}), 201


if __name__ == '__main__':
    logger.info(f"Starting XDEI Backend on {settings.app.flask_host}:{settings.app.flask_port}")
    # Allow skipping the Orion/QuantumLeap subscription bootstrap for local/dev runs
    skip_bootstrap = os.getenv('SKIP_SUBSCRIPTION_BOOTSTRAP', '').lower() in ('1', 'true', 'yes')
    if skip_bootstrap:
        logger.info('Skipping VehicleState historical subscription bootstrap (SKIP_SUBSCRIPTION_BOOTSTRAP set)')
    else:
        ensure_vehicle_state_history_subscription()
    app.run(
        host=settings.app.flask_host,
        port=settings.app.flask_port,
        debug=(settings.app.flask_env == 'development'),
    )
