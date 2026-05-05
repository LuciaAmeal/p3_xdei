from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

from prediction_service import PredictionNotFoundError, StopCrowdPredictor


def _make_stop(stop_id: str = "urn:ngsi-ld:GtfsStop:s1"):
    return {
        "id": stop_id,
        "type": "GtfsStop",
        "stopName": {"type": "Property", "value": "Parada 1"},
    }


def _make_stop_time(trip_id: str, stop_id: str):
    return {
        "id": f"urn:ngsi-ld:GtfsStopTime:{trip_id}:1",
        "type": "GtfsStopTime",
        "hasTrip": {"type": "Relationship", "object": trip_id},
        "hasStop": {"type": "Relationship", "object": stop_id},
    }


def _make_trip(trip_id: str = "urn:ngsi-ld:GtfsTrip:t1", route_id: str = "urn:ngsi-ld:GtfsRoute:r1"):
    return {
        "id": trip_id,
        "type": "GtfsTrip",
        "hasRoute": {"type": "Relationship", "object": route_id},
    }


def _make_vehicle(vehicle_id: str, trip_id: str, occupancy: int):
    return {
        "id": vehicle_id,
        "type": "VehicleState",
        "occupancy": {"type": "Property", "value": occupancy},
        "trip": {"type": "Relationship", "object": trip_id},
    }


def _make_history(vehicle_id: str, trip_id: str, occupancies):
    return {
        "id": vehicle_id,
        "type": "VehicleState",
        "index": ["2026-05-02T12:00:00Z", "2026-05-02T12:10:00Z"],
        "attributes": [
            {
                "attrName": "occupancy",
                "values": occupancies,
            },
            {
                "attrName": "trip",
                "values": [
                    {"type": "Relationship", "object": trip_id},
                    {"type": "Relationship", "object": trip_id},
                ],
            },
        ],
    }


class StubOrionClient:
    def __init__(self):
        self.calls = []

    def get_entities(self, entity_type=None, **kwargs):
        self.calls.append((entity_type, kwargs))
        datasets = {
            "GtfsStop": [_make_stop()],
            "GtfsStopTime": [_make_stop_time("urn:ngsi-ld:GtfsTrip:t1", "urn:ngsi-ld:GtfsStop:s1")],
            "GtfsTrip": [_make_trip()],
            "VehicleState": [_make_vehicle("urn:ngsi-ld:VehicleState:bus-17", "urn:ngsi-ld:GtfsTrip:t1", 61)],
        }
        return datasets.get(entity_type, [])


class StubQLClient:
    def __init__(self):
        self.calls = 0

    def get_available_entities(self):
        return ["urn:ngsi-ld:VehicleState:bus-17"]

    def get_time_series(self, entity_id, **kwargs):
        self.calls += 1
        return _make_history(entity_id, "urn:ngsi-ld:GtfsTrip:t1", [58, 62])


def test_predictor_returns_prediction_and_uses_history():
    predictor = StopCrowdPredictor(
        StubOrionClient(),
        StubQLClient(),
        cache_ttl_seconds=60,
        model_version="heuristic-test",
        default_horizon_minutes=30,
        history_window_days=7,
    )

    result = predictor.predict("urn:ngsi-ld:GtfsStop:s1", "2026-05-03T12:00:00Z", 30)

    assert result["stopId"] == "urn:ngsi-ld:GtfsStop:s1"
    assert result["predictedOccupancy"] == 60
    assert result["confidence"] >= 0.4
    assert result["modelVersion"] == "heuristic-test"
    assert result["tripIds"] == ["urn:ngsi-ld:GtfsTrip:t1"]
    assert result["routeIds"] == ["urn:ngsi-ld:GtfsRoute:r1"]


def test_predictor_returns_series_for_chart_rendering():
    predictor = StopCrowdPredictor(StubOrionClient(), StubQLClient(), cache_ttl_seconds=60, default_horizon_minutes=30)

    result = predictor.predict_series(
        "urn:ngsi-ld:GtfsStop:s1",
        "2026-05-03T12:00:00Z",
        prediction_horizon_minutes=30,
        series_horizon_minutes=60,
        series_step_minutes=15,
    )

    assert result["stopId"] == "urn:ngsi-ld:GtfsStop:s1"
    assert result["predictionHorizonMinutes"] == 30
    assert result["seriesHorizonMinutes"] == 60
    assert result["seriesStepMinutes"] == 15
    assert len(result["series"]) == 5
    assert all("timestamp" in point and "predictedOccupancy" in point for point in result["series"])


def test_predictor_uses_cache_for_identical_request():
    orion_client = StubOrionClient()
    ql_client = StubQLClient()
    predictor = StopCrowdPredictor(orion_client, ql_client, cache_ttl_seconds=60)

    first = predictor.predict("urn:ngsi-ld:GtfsStop:s1", "2026-05-03T12:00:00Z", 30)
    second = predictor.predict("urn:ngsi-ld:GtfsStop:s1", "2026-05-03T12:00:00Z", 30)

    assert first == second
    assert ql_client.calls == 1


def test_predictor_rejects_unknown_stop():
    class EmptyOrionClient(StubOrionClient):
        def get_entities(self, entity_type=None, **kwargs):
            if entity_type == "GtfsStop":
                return []
            return super().get_entities(entity_type=entity_type, **kwargs)

    predictor = StopCrowdPredictor(EmptyOrionClient(), StubQLClient(), cache_ttl_seconds=60)

    with pytest.raises(PredictionNotFoundError):
        predictor.predict("urn:ngsi-ld:GtfsStop:missing", "2026-05-03T12:00:00Z", 30)


def test_predictor_with_empty_history_returns_heuristic():
    class NoHistoryQL(StubQLClient):
        def get_available_entities(self):
            return []

    predictor = StopCrowdPredictor(StubOrionClient(), NoHistoryQL(), cache_ttl_seconds=60, default_horizon_minutes=30)

    result = predictor.predict("urn:ngsi-ld:GtfsStop:s1", "2026-05-03T12:00:00Z", 30)

    assert result["stopId"] == "urn:ngsi-ld:GtfsStop:s1"
    assert isinstance(result["predictedOccupancy"], int)


def test_predictor_handles_long_horizon():
    predictor = StopCrowdPredictor(StubOrionClient(), StubQLClient(), cache_ttl_seconds=60)

    # Very long horizon should be accepted but capped by caller validation in app; here we expect no crash
    result = predictor.predict("urn:ngsi-ld:GtfsStop:s1", "2026-05-03T12:00:00Z", 24 * 60)
    assert isinstance(result["predictedOccupancy"], int)