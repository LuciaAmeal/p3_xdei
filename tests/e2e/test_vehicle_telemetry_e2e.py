import os
import time
import requests
import pytest


@pytest.mark.e2e
def test_vehicle_telemetry_flow(start_compose, clean_orion, orion_url):
    """Create a VehicleState entity in Orion and verify backend exposes it via /api/vehicles/current."""
    entity_id = 'urn:ngsi-ld:VehicleState:vehicle-123'
    entity = {
        'id': entity_id,
        'type': 'VehicleState',
        '@context': ['https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld'],
        'currentPosition': {
            'type': 'GeoProperty',
            'value': {'type': 'Point', 'coordinates': [-3.7038, 40.4168]},
        },
    }

    headers = {'Content-Type': 'application/ld+json'}
    res = requests.post(f"{orion_url}/ngsi-ld/v1/entities", json=entity, headers=headers, timeout=10)
    assert res.status_code in (201, 409)

    backend_host = os.environ.get('FIWARE_HOST', 'localhost')
    backend_port = os.environ.get('BACKEND_PORT', '8000')
    backend_url = f"http://{backend_host}:{backend_port}"

    deadline = time.time() + 30
    found = False
    while time.time() < deadline:
        try:
            r = requests.get(f"{backend_url}/api/vehicles/current", timeout=5)
            if r.status_code == 200:
                data = r.json()
                vehicles = data.get('vehicles', [])
                if any(v.get('id') == entity_id for v in vehicles):
                    found = True
                    break
        except Exception:
            pass
        time.sleep(1)

    assert found, 'Vehicle entity not visible via backend /api/vehicles/current'
