"""Tests for the map read API used by the Leaflet frontend."""

from __future__ import annotations

from unittest.mock import patch

from app import app


def _make_route(route_id: str = "urn:ngsi-ld:GtfsRoute:r1"):
    return {
        "id": route_id,
        "type": "GtfsRoute",
        "routeShortName": {"type": "Property", "value": "1"},
        "routeLongName": {"type": "Property", "value": "Centro - Campus"},
        "routeColor": {"type": "Property", "value": "0B74DE"},
    }


def _make_trip(trip_id: str = "urn:ngsi-ld:GtfsTrip:t1"):
    return {
        "id": trip_id,
        "type": "GtfsTrip",
        "hasRoute": {"type": "Relationship", "object": "urn:ngsi-ld:GtfsRoute:r1"},
        "hasShape": {"type": "Relationship", "object": "urn:ngsi-ld:GtfsShape:s1"},
    }


def _make_shape():
    return {
        "id": "urn:ngsi-ld:GtfsShape:s1",
        "type": "GtfsShape",
        "shapePoints": {"type": "Property", "value": [[-8.41, 43.37], [-8.4, 43.36]]},
        "location": {
            "type": "GeoProperty",
            "value": {"type": "LineString", "coordinates": [[-8.41, 43.37], [-8.4, 43.36]]},
        },
    }


def _make_stop(stop_id: str, name: str, lon: float, lat: float):
    return {
        "id": stop_id,
        "type": "GtfsStop",
        "stopName": {"type": "Property", "value": name},
        "stopCode": {"type": "Property", "value": stop_id.rsplit(":", 1)[-1]},
        "location": {"type": "GeoProperty", "value": {"type": "Point", "coordinates": [lon, lat]}},
    }


def _make_stop_time(trip_id: str, stop_id: str, sequence: int):
    return {
        "id": f"urn:ngsi-ld:GtfsStopTime:{trip_id}:{sequence}",
        "type": "GtfsStopTime",
        "hasTrip": {"type": "Relationship", "object": trip_id},
        "hasStop": {"type": "Relationship", "object": stop_id},
    }


def _make_vehicle(vehicle_id: str = "urn:ngsi-ld:VehicleState:bus-17"):
    return {
        "id": vehicle_id,
        "type": "VehicleState",
        "currentPosition": {"type": "GeoProperty", "value": {"type": "Point", "coordinates": [-8.405, 43.365]}},
        "delaySeconds": {"type": "Property", "value": 45},
        "occupancy": {"type": "Property", "value": 62},
        "speedKmh": {"type": "Property", "value": 26},
        "heading": {"type": "Property", "value": 128},
        "status": {"type": "Property", "value": "in_transit"},
        "trip": {"type": "Relationship", "object": "urn:ngsi-ld:GtfsTrip:t1"},
        "nextStopName": {"type": "Property", "value": "Campus Sur"},
    }


@patch("app.orion_client")
def test_api_routes_returns_render_ready_payload(mock_orion):
    mock_orion.get_entities.side_effect = lambda entity_type=None, **kwargs: {
        "GtfsRoute": [_make_route()],
        "GtfsTrip": [_make_trip()],
        "GtfsShape": [_make_shape()],
        "GtfsStop": [_make_stop("urn:ngsi-ld:GtfsStop:s1", "Parada 1", -8.41, 43.37)],
        "GtfsStopTime": [_make_stop_time("urn:ngsi-ld:GtfsTrip:t1", "urn:ngsi-ld:GtfsStop:s1", 1)],
    }.get(entity_type, [])

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/routes")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["routes"][0]["routeShortName"] == "1"
    assert payload["routes"][0]["path"] == [[-8.41, 43.37], [-8.4, 43.36]]
    assert payload["routes"][0]["stopIds"] == ["urn:ngsi-ld:GtfsStop:s1"]


@patch("app.orion_client")
def test_api_stops_returns_point_coordinates(mock_orion):
    mock_orion.get_entities.side_effect = lambda entity_type=None, **kwargs: {
        "GtfsStop": [_make_stop("urn:ngsi-ld:GtfsStop:s1", "Parada 1", -8.41, 43.37)],
    }.get(entity_type, [])

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/stops")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["stops"][0]["stopName"] == "Parada 1"
    assert payload["stops"][0]["location"] == [-8.41, 43.37]


@patch("app.orion_client")
def test_api_current_vehicles_returns_vehicle_state(mock_orion):
    mock_orion.get_entities.side_effect = lambda entity_type=None, **kwargs: {
        "VehicleState": [_make_vehicle()],
    }.get(entity_type, [])

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/vehicles/current")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["vehicles"][0]["vehicleId"] == "bus-17"
    assert payload["vehicles"][0]["currentPosition"] == [-8.405, 43.365]
    assert payload["vehicles"][0]["tripId"] == "urn:ngsi-ld:GtfsTrip:t1"