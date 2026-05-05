import os
import requests
import pytest


@pytest.mark.e2e
def test_backend_health_and_ping(start_compose):
    host = os.environ.get('FIWARE_HOST', 'localhost')
    port = os.environ.get('BACKEND_PORT', '8000')
    base = f"http://{host}:{port}"

    r = requests.get(f"{base}/api/ping", timeout=5)
    assert r.status_code == 200 and r.json().get('ping') == 'pong'

    r = requests.get(f"{base}/health", timeout=10)
    assert r.status_code in (200, 503)
