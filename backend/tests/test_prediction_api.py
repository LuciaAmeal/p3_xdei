from __future__ import annotations

from unittest.mock import patch

from app import app


@patch("app.prediction_service")
def test_api_predict_returns_prediction(mock_prediction_service):
    mock_prediction_service.predict.return_value = {
        "stopId": "urn:ngsi-ld:GtfsStop:s1",
        "stopName": "Parada 1",
        "predictedOccupancy": 59,
        "confidence": 0.81,
        "validFrom": "2026-05-03T12:00:00Z",
        "validTo": "2026-05-03T12:30:00Z",
        "modelVersion": "heuristic-test",
        "horizonMinutes": 30,
        "tripIds": ["urn:ngsi-ld:GtfsTrip:t1"],
        "routeIds": ["urn:ngsi-ld:GtfsRoute:r1"],
        "sampleCount": 2,
        "currentSampleCount": 1,
    }

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post(
            "/api/predict",
            json={
                "stopId": "urn:ngsi-ld:GtfsStop:s1",
                "dateTime": "2026-05-03T12:00:00Z",
                "horizonMinutes": 30,
            },
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["predictedOccupancy"] == 59
    assert payload["confidence"] == 0.81
    mock_prediction_service.predict.assert_called_once()


@patch("app.prediction_service")
def test_api_predict_rejects_invalid_horizon(mock_prediction_service):
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post(
            "/api/predict",
            json={
                "stopId": "urn:ngsi-ld:GtfsStop:s1",
                "horizonMinutes": 0,
            },
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload
    mock_prediction_service.predict.assert_not_called()


@patch("app.prediction_service")
def test_api_predict_maps_missing_stop_to_404(mock_prediction_service):
    from prediction_service import PredictionNotFoundError

    mock_prediction_service.predict.side_effect = PredictionNotFoundError("Stop not found")

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post("/api/predict", json={"stopId": "urn:ngsi-ld:GtfsStop:missing"})

    assert response.status_code == 404
    payload = response.get_json()
    assert payload["error"] == "Stop not found"


@patch("app.prediction_service")
def test_api_predict_dependency_error_returns_502(mock_prediction_service):
    from prediction_service import PredictionDependencyError

    mock_prediction_service.predict.side_effect = PredictionDependencyError("Orion unavailable")

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post("/api/predict", json={"stopId": "urn:ngsi-ld:GtfsStop:s1"})

    assert response.status_code == 502
    payload = response.get_json()
    assert "error" in payload


@patch("app.prediction_service")
def test_api_predict_service_error_returns_500(mock_prediction_service):
    from prediction_service import PredictionServiceError

    mock_prediction_service.predict.side_effect = PredictionServiceError("Internal failure")

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post("/api/predict", json={"stopId": "urn:ngsi-ld:GtfsStop:s1"})

    assert response.status_code == 500
    payload = response.get_json()
    assert "error" in payload


def test_api_predict_empty_payload_returns_400():
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post("/api/predict", json={})

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload