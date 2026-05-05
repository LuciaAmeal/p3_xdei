import time


def build_vehicle(entity_id: str, lat: float, lon: float, ts: int = None):
    """Return a minimal NGSI-LD Vehicle entity dict for ingestion tests."""
    ts = ts or int(time.time() * 1000)
    return {
        "id": entity_id,
        "type": "Vehicle",
        "location": {
            "type": "GeoProperty",
            "value": {"type": "Point", "coordinates": [lon, lat]},
            "observedAt": ts,
        },
    }
