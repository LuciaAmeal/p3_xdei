from backend.utils.simulator_utils import trip_duration_seconds


def test_trip_duration_seconds():
    stop_times = [
        {"departure_time": "08:00:00"},
        {"arrival_time": "08:15:00"},
    ]
    assert trip_duration_seconds(stop_times) == 15 * 60
