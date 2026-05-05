import pytest
from backend.dynamic_simulator import publish_telemetry, simulate_once

pytestmark = pytest.mark.integration

class MockMQTT:
    def __init__(self):
        self.pubs = []

    def publish(self, topic, payload, qos=1):
        self.pubs.append((topic, payload))


def test_publish_telemetry_and_simulate_once():
    mock = MockMQTT()
    payload = {"foo": "bar"}
    publish_telemetry(mock, "v1", payload)
    assert mock.pubs
    topic, sent = mock.pubs[-1]
    assert topic == "vehicle/v1/telemetry"

    # simulate_once should publish and return payload dict
    mock2 = MockMQTT()
    out = simulate_once(mock2, "v2", 1.0, 2.0, "trip_1")
    assert isinstance(out, dict)
    assert mock2.pubs
    t, p = mock2.pubs[-1]
    assert t == "vehicle/v2/telemetry"
    assert p["trip_id"] == "trip_1"
