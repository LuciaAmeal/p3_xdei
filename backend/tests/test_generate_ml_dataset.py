"""Tests for ML dataset generation pipeline."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

# Import generator from scripts (add to path)
import sys
from pathlib import Path as PathlibPath

sys.path.insert(0, str(PathlibPath(__file__).parent.parent.parent / "scripts"))

from generate_ml_dataset import DatasetGenerator, DatasetGenerationError


# ============================================================================
# Test Fixtures
# ============================================================================


def _make_stop(stop_id: str = "urn:ngsi-ld:GtfsStop:s1", name: str = "Stop 1") -> Dict[str, Any]:
    """Create a GtfsStop entity."""
    return {
        "id": stop_id,
        "type": "GtfsStop",
        "stopName": {"type": "Property", "value": name},
    }


def _make_route(route_id: str = "urn:ngsi-ld:GtfsRoute:r1", name: str = "Route 1") -> Dict[str, Any]:
    """Create a GtfsRoute entity."""
    return {
        "id": route_id,
        "type": "GtfsRoute",
        "routeName": {"type": "Property", "value": name},
    }


def _make_trip(trip_id: str = "urn:ngsi-ld:GtfsTrip:t1", route_id: str = "urn:ngsi-ld:GtfsRoute:r1") -> Dict[str, Any]:
    """Create a GtfsTrip entity."""
    return {
        "id": trip_id,
        "type": "GtfsTrip",
        "hasRoute": {"type": "Relationship", "object": route_id},
    }


def _make_stop_time(
    stop_time_id: str,
    trip_id: str = "urn:ngsi-ld:GtfsTrip:t1",
    stop_id: str = "urn:ngsi-ld:GtfsStop:s1",
) -> Dict[str, Any]:
    """Create a GtfsStopTime entity."""
    return {
        "id": stop_time_id,
        "type": "GtfsStopTime",
        "hasTrip": {"type": "Relationship", "object": trip_id},
        "hasStop": {"type": "Relationship", "object": stop_id},
    }


def _make_history(
    vehicle_id: str,
    trip_id: str = "urn:ngsi-ld:GtfsTrip:t1",
    occupancies: List[int] | None = None,
    timestamps: List[str] | None = None,
) -> Dict[str, Any]:
    """Create a QuantumLeap time series response for VehicleState.occupancy."""
    if occupancies is None:
        occupancies = [30, 35, 40, 45, 50]
    if timestamps is None:
        timestamps = [
            "2026-05-02T12:00:00Z",
            "2026-05-02T12:10:00Z",
            "2026-05-02T12:20:00Z",
            "2026-05-02T12:30:00Z",
            "2026-05-02T12:40:00Z",
        ]

    return {
        "id": vehicle_id,
        "type": "VehicleState",
        "index": timestamps,
        "attributes": [
            {
                "attrName": "occupancy",
                "values": [{"type": "Property", "value": v} for v in occupancies],
            },
            {
                "attrName": "trip",
                "values": [
                    {"type": "Relationship", "object": trip_id} for _ in occupancies
                ],
            },
        ],
    }


class StubOrionClient:
    """Stub Orion client for testing."""

    def __init__(self, entities: Dict[str, List[Dict[str, Any]]] | None = None):
        """Initialize with predefined entity sets."""
        self.entities = entities or {}
        self.calls = []

    def get_entities(self, entity_type: str | None = None, **kwargs) -> List[Dict[str, Any]]:
        """Return predefined entities for type."""
        self.calls.append(("get_entities", entity_type, kwargs))
        return self.entities.get(entity_type, [])


class StubQLClient:
    """Stub QuantumLeap client for testing."""

    def __init__(self, histories: Dict[str, Dict[str, Any]] | None = None):
        """Initialize with predefined histories."""
        self.histories = histories or {}
        self.calls = []

    def get_available_entities(self) -> List[str]:
        """Return available vehicle IDs."""
        return list(self.histories.keys())

    def get_time_series(self, entity_id: str, **kwargs) -> Dict[str, Any]:
        """Return history for entity."""
        self.calls.append(("get_time_series", entity_id, kwargs))
        if entity_id not in self.histories:
            raise Exception(f"Entity {entity_id} not found")
        return self.histories[entity_id]


# ============================================================================
# Tests
# ============================================================================


class TestDatasetGeneratorMetadata:
    """Test metadata loading."""

    def test_load_metadata_success(self):
        """Test successful metadata loading."""
        orion_entities = {
            "GtfsStop": [_make_stop("urn:ngsi-ld:GtfsStop:s1")],
            "GtfsRoute": [_make_route("urn:ngsi-ld:GtfsRoute:r1")],
            "GtfsTrip": [_make_trip("urn:ngsi-ld:GtfsTrip:t1")],
            "GtfsStopTime": [_make_stop_time("st1")],
        }

        orion_client = StubOrionClient(orion_entities)
        ql_client = StubQLClient()

        generator = DatasetGenerator(orion_client, ql_client)
        generator.load_metadata()

        assert len(generator._stops) == 1
        assert len(generator._routes) == 1
        assert len(generator._trips) == 1
        assert len(generator._stop_times) == 1

    def test_load_metadata_empty(self):
        """Test handling of empty metadata."""
        orion_client = StubOrionClient({})
        ql_client = StubQLClient()

        generator = DatasetGenerator(orion_client, ql_client)
        generator.load_metadata()

        assert len(generator._stops) == 0
        assert len(generator._routes) == 0


class TestDatasetGeneratorFeatures:
    """Test feature engineering."""

    def test_resolve_trip_route_and_stops(self):
        """Test trip-to-route and trip-to-stops resolution."""
        trip_id = "urn:ngsi-ld:GtfsTrip:t1"
        route_id = "urn:ngsi-ld:GtfsRoute:r1"
        stop_id = "urn:ngsi-ld:GtfsStop:s1"

        generator = DatasetGenerator(StubOrionClient(), StubQLClient())
        generator._trips[trip_id] = _make_trip(trip_id, route_id)
        generator._stop_times = [_make_stop_time("st1", trip_id, stop_id)]

        resolved_route, resolved_stops = generator._resolve_trip_route_and_stops(trip_id)

        assert resolved_route == route_id
        assert stop_id in resolved_stops

    def test_parse_occupancy_history(self):
        """Test parsing QuantumLeap time series response."""
        generator = DatasetGenerator(StubOrionClient(), StubQLClient())

        response = _make_history(
            "urn:ngsi-ld:VehicleState:bus-1",
            occupancies=[30, 35, 40],
            timestamps=["2026-05-02T12:00:00Z", "2026-05-02T12:10:00Z", "2026-05-02T12:20:00Z"],
        )

        timestamps, occupancies, trip_ids = generator._parse_occupancy_history(response)

        assert len(timestamps) == 3
        assert occupancies == [30, 35, 40]
        assert len(trip_ids) == 3


class TestDatasetGeneratorPipeline:
    """Test complete pipeline."""

    def test_generate_features_small_dataset(self):
        """Test feature generation with small mock dataset."""
        # Setup mock data
        orion_entities = {
            "GtfsStop": [_make_stop("urn:ngsi-ld:GtfsStop:s1")],
            "GtfsRoute": [_make_route("urn:ngsi-ld:GtfsRoute:r1")],
            "GtfsTrip": [_make_trip("urn:ngsi-ld:GtfsTrip:t1")],
            "GtfsStopTime": [_make_stop_time("st1")],
        }

        histories = {
            "urn:ngsi-ld:VehicleState:bus-1": _make_history(
                "urn:ngsi-ld:VehicleState:bus-1",
                occupancies=[30, 35, 40, 45, 50],
            ),
        }

        orion_client = StubOrionClient(orion_entities)
        ql_client = StubQLClient(histories)

        generator = DatasetGenerator(orion_client, ql_client)
        generator.load_metadata()
        generator.generate_features()

        assert generator.dataset is not None
        assert len(generator.dataset) > 0
        assert "route_encoded" in generator.dataset.columns
        assert "stop_encoded" in generator.dataset.columns
        assert "day" in generator.dataset.columns
        assert "hour" in generator.dataset.columns
        assert "prev_occupancy_lag1" in generator.dataset.columns
        assert "prev_occupancy_rolling5min" in generator.dataset.columns
        assert "target" in generator.dataset.columns

    def test_generate_features_creates_valid_records(self):
        """Test that generated features are valid and in expected ranges."""
        orion_entities = {
            "GtfsStop": [_make_stop("urn:ngsi-ld:GtfsStop:s1")],
            "GtfsRoute": [_make_route("urn:ngsi-ld:GtfsRoute:r1")],
            "GtfsTrip": [_make_trip("urn:ngsi-ld:GtfsTrip:t1")],
            "GtfsStopTime": [_make_stop_time("st1")],
        }

        histories = {
            "urn:ngsi-ld:VehicleState:bus-1": _make_history(
                "urn:ngsi-ld:VehicleState:bus-1",
                occupancies=[25, 30, 35, 40, 45, 50, 55, 60],
            ),
        }

        orion_client = StubOrionClient(orion_entities)
        ql_client = StubQLClient(histories)

        generator = DatasetGenerator(orion_client, ql_client)
        generator.load_metadata()
        generator.generate_features()

        df = generator.dataset
        assert df is not None

        # Validate day of week range
        assert df["day"].min() >= 0
        assert df["day"].max() <= 6

        # Validate hour range
        assert df["hour"].min() >= 0
        assert df["hour"].max() <= 23

        # Validate occupancy range
        assert df["occupancy"].min() >= 0
        assert df["occupancy"].max() <= 100


class TestDatasetGeneratorSerialization:
    """Test dataset saving and loading."""

    def test_save_dataset_creates_csv(self):
        """Test that save_dataset creates a valid CSV file."""
        orion_entities = {
            "GtfsStop": [_make_stop("urn:ngsi-ld:GtfsStop:s1")],
            "GtfsRoute": [_make_route("urn:ngsi-ld:GtfsRoute:r1")],
            "GtfsTrip": [_make_trip("urn:ngsi-ld:GtfsTrip:t1")],
            "GtfsStopTime": [_make_stop_time("st1")],
        }

        histories = {
            "urn:ngsi-ld:VehicleState:bus-1": _make_history(
                "urn:ngsi-ld:VehicleState:bus-1",
            ),
        }

        orion_client = StubOrionClient(orion_entities)
        ql_client = StubQLClient(histories)

        generator = DatasetGenerator(orion_client, ql_client)
        generator.load_metadata()
        generator.generate_features()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_dataset.csv"
            generator.save_dataset(str(output_path))

            # Verify CSV was created
            assert output_path.exists()

            # Verify contents
            df = pd.read_csv(output_path)
            assert len(df) > 0
            assert "route" in df.columns
            assert "stop" in df.columns

    def test_save_dataset_creates_encoders_json(self):
        """Test that save_dataset creates an encoders JSON file."""
        orion_entities = {
            "GtfsStop": [_make_stop("urn:ngsi-ld:GtfsStop:s1"), _make_stop("urn:ngsi-ld:GtfsStop:s2")],
            "GtfsRoute": [_make_route("urn:ngsi-ld:GtfsRoute:r1"), _make_route("urn:ngsi-ld:GtfsRoute:r2")],
            "GtfsTrip": [_make_trip("urn:ngsi-ld:GtfsTrip:t1")],
            "GtfsStopTime": [_make_stop_time("st1"), _make_stop_time("st2")],
        }

        histories = {
            "urn:ngsi-ld:VehicleState:bus-1": _make_history(
                "urn:ngsi-ld:VehicleState:bus-1",
            ),
        }

        orion_client = StubOrionClient(orion_entities)
        ql_client = StubQLClient(histories)

        generator = DatasetGenerator(orion_client, ql_client)
        generator.load_metadata()
        generator.generate_features()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_dataset.csv"
            generator.save_dataset(str(output_path))

            # Verify encoders JSON was created
            encoder_path = Path(tmpdir) / "test_dataset_encoders.json"
            assert encoder_path.exists()

            # Verify encoders content
            with open(encoder_path) as f:
                encoders = json.load(f)
            assert "routes" in encoders
            assert "stops" in encoders
            assert len(encoders["routes"]) > 0


class TestDatasetGeneratorSampling:
    """Test sampling functionality."""

    def test_generate_features_with_sampling(self):
        """Test that sample_size parameter limits output rows."""
        orion_entities = {
            "GtfsStop": [_make_stop("urn:ngsi-ld:GtfsStop:s1")],
            "GtfsRoute": [_make_route("urn:ngsi-ld:GtfsRoute:r1")],
            "GtfsTrip": [_make_trip("urn:ngsi-ld:GtfsTrip:t1")],
            "GtfsStopTime": [_make_stop_time("st1")],
        }

        # Create larger history
        occupancies = list(range(20, 100))
        histories = {
            "urn:ngsi-ld:VehicleState:bus-1": _make_history(
                "urn:ngsi-ld:VehicleState:bus-1",
                occupancies=occupancies,
                timestamps=[f"2026-05-02T{i:02d}:{(i*10) % 60:02d}:00Z" for i in range(len(occupancies))],
            ),
        }

        orion_client = StubOrionClient(orion_entities)
        ql_client = StubQLClient(histories)

        generator = DatasetGenerator(orion_client, ql_client, sample_size=10)
        generator.load_metadata()
        generator.generate_features()

        assert generator.dataset is not None
        assert len(generator.dataset) <= 10
