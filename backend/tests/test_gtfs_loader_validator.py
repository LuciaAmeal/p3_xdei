"""
Tests for GTFS loader and validator.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from load_gtfs import GTFSValidationError, build_entities, load_gtfs, read_gtfs_feed, validate_feed
from validate_gtfs import validate_extended_gtfs, validate_gtfs, validate_ngsi_ld_structure


ROUTES_CSV = """route_id,agency_id,route_short_name,route_long_name,route_desc,route_type,route_color,route_text_color
r1,a1,10,Centro - Campus,Main line,3,FF0000,FFFFFF
"""

STOPS_CSV = """stop_id,stop_name,stop_code,stop_desc,platform_code,zone_id,wheelchair_boarding,stop_lat,stop_lon
s1,Parada 1,S1,,P1,Z1,1,43.3623,-8.4115
s2,Parada 2,S2,,P2,Z1,0,43.3629,-8.4101
"""

TRIPS_CSV = """route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id
r1,wd,t1,Campus,10A,0,b1,shape1
"""

STOP_TIMES_CSV = """trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type
t1,08:00:00,08:00:00,s1,1,0,0
t1,08:05:00,08:05:00,s2,2,0,0
"""

CALENDAR_CSV = """service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
wd,1,1,1,1,1,0,0,20260101,20261231
"""

SHAPES_CSV = """shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled
shape1,43.3623,-8.4115,1,0.0
shape1,43.3629,-8.4101,2,0.8
"""

CALENDAR_DATES_CSV = """service_id,date,exception_type
wd,20260430,1
"""

AGENCY_CSV = """agency_id,agency_name,agency_url,agency_timezone
a1,Transportes Demo,https://example.com,Europe/Madrid
"""


def make_gtfs_zip(tmp_path: Path, *, include_calendar: bool = True, include_calendar_dates: bool = True, broken_stop: bool = False, routes: str = None, stops: str = None, trips: str = None, stop_times: str = None, shapes: str = None, calendar: str = None, calendar_dates: str = None, agency: str = None) -> Path:
    archive_path = tmp_path / "feed.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("routes.txt", routes or (ROUTES_CSV if not broken_stop else ROUTES_CSV))
        archive.writestr("stops.txt", stops or (STOPS_CSV if not broken_stop else STOPS_CSV.replace("43.3629,-8.4101", "200.0,-8.4101")))
        archive.writestr("trips.txt", trips or TRIPS_CSV)
        archive.writestr("stop_times.txt", stop_times or STOP_TIMES_CSV)
        archive.writestr("shapes.txt", shapes or SHAPES_CSV)
        if include_calendar:
            archive.writestr("calendar.txt", calendar or CALENDAR_CSV)
        if include_calendar_dates:
            archive.writestr("calendar_dates.txt", calendar_dates or CALENDAR_DATES_CSV)
        archive.writestr("agency.txt", agency or AGENCY_CSV)
    return archive_path


class DummyOrionClient:
    def __init__(self):
        self.calls = []

    def batch_upsert(self, entities, batch_size=100):
        self.calls.append((entities, batch_size))
        return {"total": len(entities), "batches": 1, "errors": 0}


def test_read_and_validate_gtfs_feed(tmp_path):
    archive_path = make_gtfs_zip(tmp_path)
    feed = read_gtfs_feed(archive_path)
    errors = validate_feed(feed)

    assert errors == []
    entities = build_entities(feed)
    entity_types = {entity["type"] for entity in entities}
    assert entity_types == {"GtfsRoute", "GtfsStop", "GtfsTrip", "GtfsStopTime", "GtfsShape", "GtfsService"}
    assert len(entities) == 8


def test_loader_batches_entities(tmp_path):
    archive_path = make_gtfs_zip(tmp_path)
    client = DummyOrionClient()

    summary = load_gtfs(archive_path, orion_client=client, batch_size=2, dry_run=False)

    assert summary.total_entities == 8
    assert summary.entity_counts["GtfsRoute"] == 1
    assert summary.entity_counts["GtfsStop"] == 2
    assert summary.entity_counts["GtfsTrip"] == 1
    assert summary.entity_counts["GtfsStopTime"] == 2
    assert summary.entity_counts["GtfsShape"] == 1
    assert summary.entity_counts["GtfsService"] == 1
    assert client.calls
    assert client.calls[0][1] == 2
    assert len(client.calls[0][0]) == 8


def test_validator_reports_invalid_geometry(tmp_path):
    archive_path = make_gtfs_zip(tmp_path, broken_stop=True)
    summary = validate_gtfs(archive_path)

    assert summary.valid is False
    assert any("out-of-range coordinates" in error for error in summary.errors)


def test_validator_requires_calendar_or_calendar_dates(tmp_path):
    archive_path = make_gtfs_zip(tmp_path, include_calendar=False, include_calendar_dates=False)
    feed = read_gtfs_feed(archive_path)
    errors = validate_feed(feed)

    assert any("calendar.txt or calendar_dates.txt" in error for error in errors)


def test_validator_detects_duplicate_ids(tmp_path):
    archive_path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("routes.txt", ROUTES_CSV + "r1,a1,11,Duplicate,Main line,3,FF0000,FFFFFF\n")
        archive.writestr("stops.txt", STOPS_CSV)
        archive.writestr("trips.txt", TRIPS_CSV)
        archive.writestr("stop_times.txt", STOP_TIMES_CSV)
        archive.writestr("calendar.txt", CALENDAR_CSV)
    summary = validate_gtfs(archive_path)

    assert summary.valid is False
    assert any("duplicate route_id" in error for error in summary.errors)


# ============================================================================
# Extended Validation Tests (Negative Cases)
# ============================================================================


class TestExtendedValidationNegativeCases:
    """Test that extended validators correctly reject invalid GTFS."""

    def test_detects_non_chronological_stop_times(self, tmp_path):
        """Validator should detect when stop_times are not chronologically ordered."""
        # Create stop_times with non-chronological sequence
        bad_stop_times = """trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type
t1,08:10:00,08:10:00,s1,1,0,0
t1,08:05:00,08:05:00,s2,2,0,0
t1,08:15:00,08:15:00,s3,3,0,0
"""
        archive_path = make_gtfs_zip(tmp_path, stop_times=bad_stop_times)
        feed = read_gtfs_feed(archive_path)
        errors = validate_extended_gtfs(feed)

        assert any("non-chronological" in error for error in errors), (
            f"Expected non-chronological error, got: {errors}"
        )

    def test_detects_arrival_after_departure(self, tmp_path):
        """Validator should detect when arrival_time > departure_time."""
        bad_stop_times = """trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type
t1,08:10:00,08:05:00,s1,1,0,0
t1,08:15:00,08:20:00,s2,2,0,0
"""
        archive_path = make_gtfs_zip(tmp_path, stop_times=bad_stop_times)
        feed = read_gtfs_feed(archive_path)
        errors = validate_extended_gtfs(feed)

        assert any("arrival_time > departure_time" in error for error in errors), (
            f"Expected arrival > departure error, got: {errors}"
        )

    def test_detects_shape_with_single_point(self, tmp_path):
        """Validator should reject shapes with fewer than 2 points."""
        bad_shapes = """shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled
shape_single,43.3623,-8.4115,1,0.0
"""
        archive_path = make_gtfs_zip(tmp_path, shapes=bad_shapes)
        feed = read_gtfs_feed(archive_path)
        errors = validate_extended_gtfs(feed)

        assert any("fewer than 2 points" in error for error in errors), (
            f"Expected single-point shape error, got: {errors}"
        )

    def test_detects_out_of_range_coordinates_in_shapes(self, tmp_path):
        """Validator should detect coordinates outside valid geographic bounds."""
        bad_shapes = """shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled
shape_bad,91.0,-8.4115,1,0.0
shape_bad,43.3629,-8.4101,2,0.8
"""
        archive_path = make_gtfs_zip(tmp_path, shapes=bad_shapes)
        feed = read_gtfs_feed(archive_path)
        errors = validate_extended_gtfs(feed)

        assert any("out-of-range" in error for error in errors), (
            f"Expected out-of-range coordinates error, got: {errors}"
        )


class TestNGSILDStructureValidationNegativeCases:
    """Test that NGSI-LD validator rejects malformed entities."""

    def test_rejects_entity_without_id(self, tmp_path):
        """NGSI-LD validator should reject entity without id."""
        bad_entity = {
            "type": "GtfsRoute",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "routeShortName": {"type": "Property", "value": "10"},
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("missing 'id'" in error for error in errors)

    def test_rejects_entity_without_type(self, tmp_path):
        """NGSI-LD validator should reject entity without type."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsRoute:r1",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "routeShortName": {"type": "Property", "value": "10"},
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("missing 'type'" in error for error in errors)

    def test_rejects_entity_without_context(self, tmp_path):
        """NGSI-LD validator should reject entity without @context."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsRoute:r1",
            "type": "GtfsRoute",
            "routeShortName": {"type": "Property", "value": "10"},
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("missing '@context'" in error for error in errors)

    def test_rejects_property_without_value(self, tmp_path):
        """NGSI-LD validator should reject Property without value field."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsRoute:r1",
            "type": "GtfsRoute",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "routeShortName": {"type": "Property"},  # Missing 'value'
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("missing 'value'" in error for error in errors)

    def test_rejects_relationship_without_object(self, tmp_path):
        """NGSI-LD validator should reject Relationship without object field."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsTrip:t1",
            "type": "GtfsTrip",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "hasRoute": {"type": "Relationship"},  # Missing 'object'
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("missing 'object'" in error for error in errors)

    def test_rejects_geoproperty_without_coordinates(self, tmp_path):
        """NGSI-LD validator should reject GeoProperty without coordinates."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsStop:s1",
            "type": "GtfsStop",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "location": {
                "type": "GeoProperty",
                "value": {"type": "Point"},  # Missing 'coordinates'
            },
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("missing 'coordinates'" in error for error in errors)

    def test_rejects_point_with_wrong_coordinate_count(self, tmp_path):
        """NGSI-LD validator should reject Point with != 2 coordinates."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsStop:s1",
            "type": "GtfsStop",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "location": {
                "type": "GeoProperty",
                "value": {"type": "Point", "coordinates": [43.3623]},  # Only 1 coord
            },
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("Point" in error and "2" in error for error in errors)

    def test_rejects_linestring_with_insufficient_points(self, tmp_path):
        """NGSI-LD validator should reject LineString with <2 points."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsShape:shape1",
            "type": "GtfsShape",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "location": {
                "type": "GeoProperty",
                "value": {"type": "LineString", "coordinates": [[43.3623, -8.4115]]},  # Only 1 point
            },
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("LineString" in error and ">=2" in error for error in errors)

    def test_rejects_out_of_range_coordinates(self, tmp_path):
        """NGSI-LD validator should reject coordinates outside valid ranges."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsStop:s1",
            "type": "GtfsStop",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "location": {
                "type": "GeoProperty",
                "value": {"type": "Point", "coordinates": [-8.4115, 91.0]},  # lat=91.0 is out of range
            },
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("out-of-range" in error for error in errors)

    def test_rejects_integer_property_as_string(self, tmp_path):
        """NGSI-LD validator should reject integer property stored as string."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsStopTime:t1_001",
            "type": "GtfsStopTime",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "stopSequence": {"type": "Property", "value": "1"},  # Should be int, not string
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("stopSequence" in error and "integer" in error for error in errors)

    def test_rejects_boolean_property_as_string(self, tmp_path):
        """NGSI-LD validator should reject boolean property stored as string."""
        bad_entity = {
            "id": "urn:ngsi-ld:GtfsService:wd",
            "type": "GtfsService",
            "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
            "monday": {"type": "Property", "value": "1"},  # Should be bool, not string
        }
        errors = validate_ngsi_ld_structure([bad_entity])
        assert any("monday" in error and "boolean" in error for error in errors)
