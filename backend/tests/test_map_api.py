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


def _make_vehicle_history(vehicle_id: str, base_lon: float, base_lat: float):
    return {
        "id": vehicle_id,
        "type": "VehicleState",
        "index": ["2026-05-02T12:00:00Z", "2026-05-02T12:02:00Z"],
        "attributes": [
            {
                "attrName": "currentPosition",
                "values": [
                    {"type": "Point", "coordinates": [base_lon, base_lat]},
                    {"type": "Point", "coordinates": [base_lon + 0.01, base_lat + 0.01]},
                ],
            },
            {
                "attrName": "delaySeconds",
                "values": [45, 50],
            },
            {
                "attrName": "status",
                "values": ["in_transit", "approaching"],
            },
        ],
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


@patch("app.ql_client")
def test_api_vehicle_history_groups_and_paginates_by_vehicle(mock_ql):
    mock_ql.get_available_entities.return_value = [
        "urn:ngsi-ld:VehicleState:bus-17",
        "urn:ngsi-ld:VehicleState:bus-18",
        "urn:ngsi-ld:Sensor:ignore-me",
    ]
    mock_ql.get_time_series.side_effect = lambda entity_id, **kwargs: {
        "urn:ngsi-ld:VehicleState:bus-17": _make_vehicle_history("urn:ngsi-ld:VehicleState:bus-17", -8.41, 43.37),
        "urn:ngsi-ld:VehicleState:bus-18": _make_vehicle_history("urn:ngsi-ld:VehicleState:bus-18", -8.40, 43.36),
    }[entity_id]

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get(
            "/api/vehicles/history?fromDate=2026-05-02T12:00:00Z&toDate=2026-05-02T13:00:00Z&page=1&pageSize=1"
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["pagination"] == {"page": 1, "pageSize": 1, "totalVehicles": 2, "totalPages": 2}
    assert payload["filters"]["fromDate"] == "2026-05-02T12:00:00Z"
    assert payload["vehicles"][0]["vehicleId"] == "bus-17"
    assert payload["vehicles"][0]["sampleCount"] == 2
    assert payload["vehicles"][0]["history"][0]["currentPosition"] == [-8.41, 43.37]
    assert payload["vehicles"][0]["history"][1]["delaySeconds"] == 50


@patch("app.ql_client")
def test_api_vehicle_history_rejects_invalid_page(mock_ql):
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/vehicles/history?page=0")

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload