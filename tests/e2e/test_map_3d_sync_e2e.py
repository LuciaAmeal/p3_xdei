import os
import requests
import pytest


@pytest.mark.e2e
def test_map_endpoints(start_compose):
    host = os.environ.get('FIWARE_HOST', 'localhost')
    port = os.environ.get('BACKEND_PORT', '8000')
    base = f"http://{host}:{port}"

    r = requests.get(f"{base}/api/routes", timeout=5)
    assert r.status_code == 200 and 'routes' in r.json()

    r = requests.get(f"{base}/api/stops", timeout=5)
    assert r.status_code == 200 and 'stops' in r.json()
