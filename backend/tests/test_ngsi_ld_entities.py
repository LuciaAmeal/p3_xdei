"""
Tests for NGSI-LD entity structure and conformance.

Tests that generated NGSI-LD entities from GTFS data conform to:
- NGSI-LD core structure (id, type, @context)
- Property/Relationship/GeoProperty format
- Type alignment and valid ranges
- Relational integrity
- Geographic validity
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from load_gtfs import GTFSFeed, build_entities, read_gtfs_feed
from validate_gtfs import validate_ngsi_ld_structure


# Test data fixtures
ROUTES_CSV = """route_id,agency_id,route_short_name,route_long_name,route_desc,route_type,route_color,route_text_color
r1,a1,10,Centro - Campus,Main line,3,FF0000,FFFFFF
r2,a1,20,Estación - Barrio,Secondary line,3,00FF00,000000
"""

STOPS_CSV = """stop_id,stop_name,stop_code,stop_desc,platform_code,zone_id,wheelchair_boarding,stop_lat,stop_lon
s1,Parada 1,S1,First stop,P1,Z1,1,43.3623,-8.4115
s2,Parada 2,S2,Second stop,P2,Z1,0,43.3629,-8.4101
s3,Parada 3,S3,,P3,Z1,1,43.3635,-8.4090
"""

TRIPS_CSV = """route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id
r1,wd,t1,Campus,10A,0,b1,shape1
r1,wd,t2,Centro,10B,1,b2,shape2
r2,wd,t3,Barrio,20A,0,b3,shape3
"""

STOP_TIMES_CSV = """trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type
t1,08:00:00,08:00:00,s1,1,0,0
t1,08:05:00,08:05:00,s2,2,0,0
t1,08:10:00,08:10:00,s3,3,0,0
t2,14:00:00,14:00:00,s3,1,0,0
t2,14:05:00,14:05:00,s2,2,0,0
t2,14:10:00,14:10:00,s1,3,0,0
t3,09:00:00,09:00:00,s1,1,0,0
t3,09:08:00,09:08:00,s3,2,0,0
"""

CALENDAR_CSV = """service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
wd,1,1,1,1,1,0,0,20260101,20261231
"""

CALENDAR_DATES_CSV = """service_id,date,exception_type
wd,20260501,1
"""

SHAPES_CSV = """shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled
shape1,43.3623,-8.4115,1,0.0
shape1,43.3629,-8.4101,2,0.8
shape1,43.3635,-8.4090,3,1.6
shape2,43.3635,-8.4090,1,0.0
shape2,43.3629,-8.4101,2,0.8
shape2,43.3623,-8.4115,3,1.6
shape3,43.3623,-8.4115,1,0.0
shape3,43.3635,-8.4090,2,1.6
"""

AGENCY_CSV = """agency_id,agency_name,agency_url,agency_timezone
a1,Transportes Demo,https://example.com,Europe/Madrid
"""


def make_gtfs_zip(tmp_path: Path, **kwargs) -> Path:
    """Create a test GTFS ZIP file."""
    archive_path = tmp_path / "feed.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("routes.txt", kwargs.get("routes", ROUTES_CSV))
        archive.writestr("stops.txt", kwargs.get("stops", STOPS_CSV))
        archive.writestr("trips.txt", kwargs.get("trips", TRIPS_CSV))
        archive.writestr("stop_times.txt", kwargs.get("stop_times", STOP_TIMES_CSV))
        archive.writestr("shapes.txt", kwargs.get("shapes", SHAPES_CSV))
        archive.writestr("calendar.txt", kwargs.get("calendar", CALENDAR_CSV))
        archive.writestr("calendar_dates.txt", kwargs.get("calendar_dates", CALENDAR_DATES_CSV))
        archive.writestr("agency.txt", kwargs.get("agency", AGENCY_CSV))
    return archive_path


def extract_entities_by_type(entities: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group entities by their type."""
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for entity in entities:
        entity_type = entity.get("type", "Unknown")
        if entity_type not in by_type:
            by_type[entity_type] = []
        by_type[entity_type].append(entity)
    return by_type


# ============================================================================
# NGSI-LD Base Structure Tests
# ============================================================================


class TestNGSILDBaseStructure:
    """Test that all entities have correct NGSI-LD base structure."""

    def test_entities_have_required_fields(self, tmp_path):
        """All entities must have id, type, and @context."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)

        for entity in entities:
            assert "id" in entity, f"Entity missing 'id': {entity}"
            assert "type" in entity, f"Entity missing 'type': {entity}"
            assert "@context" in entity, f"Entity missing '@context': {entity}"

    def test_entity_id_format(self, tmp_path):
        """Entity IDs must follow urn:ngsi-ld:type:id format."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)

        for entity in entities:
            entity_id = entity["id"]
            entity_type = entity["type"]
            assert entity_id.startswith("urn:ngsi-ld:"), f"Invalid ID format: {entity_id}"
            assert entity_type in entity_id, f"Entity type not in ID: {entity_type} not in {entity_id}"

    def test_context_is_list_or_string(self, tmp_path):
        """@context must be a list or string."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)

        for entity in entities:
            context = entity.get("@context")
            assert isinstance(context, (str, list)), (
                f"@context must be string or list, got {type(context).__name__}"
            )

    def test_all_entities_pass_ngsi_ld_validation(self, tmp_path):
        """All generated entities must pass NGSI-LD structure validation."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)

        errors = validate_ngsi_ld_structure(entities)
        assert errors == [], f"NGSI-LD validation errors:\n" + "\n".join(errors)


# ============================================================================
# Entity Type Tests
# ============================================================================


class TestGtfsRouteEntity:
    """Test GtfsRoute entity structure and properties."""

    def test_gtfs_route_exists(self, tmp_path):
        """At least one GtfsRoute entity should exist."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        assert "GtfsRoute" in by_type, "No GtfsRoute entities found"
        assert len(by_type["GtfsRoute"]) >= 1, "Expected at least 1 GtfsRoute"

    def test_gtfs_route_properties(self, tmp_path):
        """GtfsRoute must have required properties."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for route in by_type.get("GtfsRoute", []):
            assert "routeShortName" in route, f"Missing routeShortName in {route['id']}"
            assert "routeType" in route, f"Missing routeType in {route['id']}"
            # Properties must be dict with "type" and "value"
            assert isinstance(route["routeShortName"], dict)
            assert route["routeShortName"].get("type") == "Property"
            assert "value" in route["routeShortName"]

    def test_gtfs_route_optional_properties(self, tmp_path):
        """GtfsRoute optional properties should be dict when present."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for route in by_type.get("GtfsRoute", []):
            if "routeColor" in route:
                assert isinstance(route["routeColor"], dict)
                assert route["routeColor"].get("type") == "Property"


class TestGtfsStopEntity:
    """Test GtfsStop entity structure and properties."""

    def test_gtfs_stop_exists(self, tmp_path):
        """At least one GtfsStop entity should exist."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        assert "GtfsStop" in by_type, "No GtfsStop entities found"
        assert len(by_type["GtfsStop"]) >= 1, "Expected at least 1 GtfsStop"

    def test_gtfs_stop_has_location(self, tmp_path):
        """GtfsStop must have location GeoProperty."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for stop in by_type.get("GtfsStop", []):
            assert "location" in stop, f"Missing location in {stop['id']}"
            location = stop["location"]
            assert isinstance(location, dict)
            assert location.get("type") == "GeoProperty"
            assert "value" in location
            geo = location["value"]
            assert geo.get("type") == "Point"
            assert "coordinates" in geo
            coords = geo["coordinates"]
            assert len(coords) == 2, f"Point should have 2 coordinates, got {len(coords)}"
            lon, lat = coords
            assert -180 <= lon <= 180, f"Longitude out of range: {lon}"
            assert -90 <= lat <= 90, f"Latitude out of range: {lat}"

    def test_gtfs_stop_properties(self, tmp_path):
        """GtfsStop must have required properties."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for stop in by_type.get("GtfsStop", []):
            assert "stopName" in stop, f"Missing stopName in {stop['id']}"
            assert isinstance(stop["stopName"], dict)
            assert stop["stopName"].get("type") == "Property"


class TestGtfsServiceEntity:
    """Test GtfsService entity structure and properties."""

    def test_gtfs_service_exists(self, tmp_path):
        """At least one GtfsService entity should exist."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        assert "GtfsService" in by_type, "No GtfsService entities found"
        assert len(by_type["GtfsService"]) >= 1, "Expected at least 1 GtfsService"

    def test_gtfs_service_weekday_properties_are_boolean(self, tmp_path):
        """GtfsService weekday properties must be boolean."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for service in by_type.get("GtfsService", []):
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for weekday in weekdays:
                if weekday in service:
                    assert isinstance(service[weekday], dict)
                    assert service[weekday].get("type") == "Property"
                    value = service[weekday].get("value")
                    assert isinstance(value, bool), (
                        f"Weekday {weekday} should be boolean, got {type(value).__name__}"
                    )


class TestGtfsTripEntity:
    """Test GtfsTrip entity structure and relationships."""

    def test_gtfs_trip_exists(self, tmp_path):
        """At least one GtfsTrip entity should exist."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        assert "GtfsTrip" in by_type, "No GtfsTrip entities found"

    def test_gtfs_trip_has_route_relationship(self, tmp_path):
        """GtfsTrip should have hasRoute relationship."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for trip in by_type.get("GtfsTrip", []):
            if "hasRoute" in trip:
                rel = trip["hasRoute"]
                assert isinstance(rel, dict)
                assert rel.get("type") == "Relationship"
                assert "object" in rel
                assert isinstance(rel["object"], str)
                assert rel["object"].startswith("urn:ngsi-ld:GtfsRoute:")


class TestGtfsStopTimeEntity:
    """Test GtfsStopTime entity structure and relationships."""

    def test_gtfs_stop_time_exists(self, tmp_path):
        """At least one GtfsStopTime entity should exist."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        assert "GtfsStopTime" in by_type, "No GtfsStopTime entities found"

    def test_gtfs_stop_time_has_stop_sequence(self, tmp_path):
        """GtfsStopTime must have stopSequence as integer."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for stop_time in by_type.get("GtfsStopTime", []):
            assert "stopSequence" in stop_time, f"Missing stopSequence in {stop_time['id']}"
            seq = stop_time["stopSequence"]
            assert isinstance(seq, dict)
            assert seq.get("type") == "Property"
            assert isinstance(seq.get("value"), int), (
                f"stopSequence value should be integer, got {type(seq.get('value')).__name__}"
            )

    def test_gtfs_stop_time_has_relationships(self, tmp_path):
        """GtfsStopTime must have hasStop and hasTrip relationships."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for stop_time in by_type.get("GtfsStopTime", []):
            assert "hasStop" in stop_time, f"Missing hasStop in {stop_time['id']}"
            assert "hasTrip" in stop_time, f"Missing hasTrip in {stop_time['id']}"
            
            for rel_name in ["hasStop", "hasTrip"]:
                rel = stop_time[rel_name]
                assert isinstance(rel, dict)
                assert rel.get("type") == "Relationship"
                assert "object" in rel


class TestGtfsShapeEntity:
    """Test GtfsShape entity structure and geo properties."""

    def test_gtfs_shape_exists(self, tmp_path):
        """At least one GtfsShape entity should exist."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        assert "GtfsShape" in by_type, "No GtfsShape entities found"

    def test_gtfs_shape_has_location_linestring(self, tmp_path):
        """GtfsShape must have location as LineString GeoProperty."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for shape in by_type.get("GtfsShape", []):
            assert "location" in shape, f"Missing location in {shape['id']}"
            location = shape["location"]
            assert isinstance(location, dict)
            assert location.get("type") == "GeoProperty"
            geo = location["value"]
            assert geo.get("type") == "LineString"
            coords = geo.get("coordinates", [])
            assert len(coords) >= 2, f"LineString should have >=2 points, got {len(coords)}"
            for idx, coord in enumerate(coords):
                assert len(coord) == 2, f"Point {idx} should have [lon, lat]"
                lon, lat = coord
                assert -180 <= lon <= 180, f"Longitude out of range at point {idx}: {lon}"
                assert -90 <= lat <= 90, f"Latitude out of range at point {idx}: {lat}"

    def test_gtfs_shape_has_shape_points_property(self, tmp_path):
        """GtfsShape should have shapePoints property."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        for shape in by_type.get("GtfsShape", []):
            if "shapePoints" in shape:
                prop = shape["shapePoints"]
                assert isinstance(prop, dict)
                assert prop.get("type") == "Property"
                assert "value" in prop


# ============================================================================
# Relational Integrity Tests
# ============================================================================


class TestRelationalIntegrity:
    """Test that relationships between entities are valid."""

    def test_all_trip_route_refs_exist(self, tmp_path):
        """All GtfsTrip hasRoute references must point to existing GtfsRoute."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        route_ids = {route["id"] for route in by_type.get("GtfsRoute", [])}

        for trip in by_type.get("GtfsTrip", []):
            if "hasRoute" in trip:
                ref = trip["hasRoute"]["object"]
                assert ref in route_ids, (
                    f"GtfsTrip {trip['id']} references non-existent route {ref}"
                )

    def test_all_stop_time_stop_refs_exist(self, tmp_path):
        """All GtfsStopTime hasStop references must point to existing GtfsStop."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        stop_ids = {stop["id"] for stop in by_type.get("GtfsStop", [])}

        for stop_time in by_type.get("GtfsStopTime", []):
            if "hasStop" in stop_time:
                ref = stop_time["hasStop"]["object"]
                assert ref in stop_ids, (
                    f"GtfsStopTime {stop_time['id']} references non-existent stop {ref}"
                )

    def test_all_stop_time_trip_refs_exist(self, tmp_path):
        """All GtfsStopTime hasTrip references must point to existing GtfsTrip."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        trip_ids = {trip["id"] for trip in by_type.get("GtfsTrip", [])}

        for stop_time in by_type.get("GtfsStopTime", []):
            if "hasTrip" in stop_time:
                ref = stop_time["hasTrip"]["object"]
                assert ref in trip_ids, (
                    f"GtfsStopTime {stop_time['id']} references non-existent trip {ref}"
                )

    def test_all_shape_refs_exist(self, tmp_path):
        """All GtfsTrip hasShape references must point to existing GtfsShape."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        shape_ids = {shape["id"] for shape in by_type.get("GtfsShape", [])}

        for trip in by_type.get("GtfsTrip", []):
            if "hasShape" in trip:
                ref = trip["hasShape"]["object"]
                # Shape might not exist for all trips in test data
                if ref:  # Only check non-null references
                    assert ref in shape_ids, (
                        f"GtfsTrip {trip['id']} references non-existent shape {ref}"
                    )


# ============================================================================
# Type and Format Tests
# ============================================================================


class TestPropertyTypes:
    """Test that property values have correct types."""

    def test_integer_properties_are_integers(self, tmp_path):
        """Integer properties should be int type, not string."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        int_properties = ["routeType", "wheelchairBoarding", "pickupType", "dropOffType"]

        for entity in entities:
            for prop_name in int_properties:
                if prop_name in entity:
                    prop = entity[prop_name]
                    if prop.get("type") == "Property":
                        value = prop.get("value")
                        if value is not None:
                            assert isinstance(value, int), (
                                f"{entity['id']} {prop_name} should be int, got {type(value).__name__}"
                            )

    def test_string_properties_are_strings(self, tmp_path):
        """String properties should be str type, not int."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        string_properties = ["stopName", "routeShortName", "tripHeadsign"]

        for entity in entities:
            for prop_name in string_properties:
                if prop_name in entity:
                    prop = entity[prop_name]
                    if prop.get("type") == "Property" and "value" in prop:
                        value = prop.get("value")
                        if value is not None:
                            assert isinstance(value, str), (
                                f"{entity['id']} {prop_name} should be str, got {type(value).__name__}"
                            )


# ============================================================================
# Geographic Validation Tests
# ============================================================================


class TestGeographicValidity:
    """Test that geographic coordinates are realistic for A Coruña region."""

    def test_stops_near_corunna(self, tmp_path):
        """Stop coordinates should be near A Coruña region."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        # A Coruña is approximately at 43.35°N, 8.41°W
        # Allow ±0.1° tolerance for test data
        corunna_lat, corunna_lon = 43.35, -8.41
        lat_tolerance, lon_tolerance = 0.2, 0.2

        for stop in by_type.get("GtfsStop", []):
            geo = stop["location"]["value"]
            lon, lat = geo["coordinates"]
            assert (
                abs(lat - corunna_lat) <= lat_tolerance
            ), f"Stop {stop['id']} lat {lat} too far from A Coruña"
            assert (
                abs(lon - corunna_lon) <= lon_tolerance
            ), f"Stop {stop['id']} lon {lon} too far from A Coruña"

    def test_shapes_near_corunna(self, tmp_path):
        """Shape coordinates should be near A Coruña region."""
        archive_path = make_gtfs_zip(tmp_path)
        feed = read_gtfs_feed(archive_path)
        entities = build_entities(feed)
        by_type = extract_entities_by_type(entities)

        corunna_lat, corunna_lon = 43.35, -8.41
        lat_tolerance, lon_tolerance = 0.2, 0.2

        for shape in by_type.get("GtfsShape", []):
            geo = shape["location"]["value"]
            for coord in geo["coordinates"]:
                lon, lat = coord
                assert (
                    abs(lat - corunna_lat) <= lat_tolerance
                ), f"Shape {shape['id']} point lat {lat} too far from A Coruña"
                assert (
                    abs(lon - corunna_lon) <= lon_tolerance
                ), f"Shape {shape['id']} point lon {lon} too far from A Coruña"
