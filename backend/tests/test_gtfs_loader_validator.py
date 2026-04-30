"""
Tests for GTFS loader and validator.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from load_gtfs import GTFSValidationError, build_entities, load_gtfs, read_gtfs_feed, validate_feed
from validate_gtfs import validate_gtfs


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


def make_gtfs_zip(tmp_path: Path, *, include_calendar: bool = True, include_calendar_dates: bool = True, broken_stop: bool = False) -> Path:
    archive_path = tmp_path / "feed.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("routes.txt", ROUTES_CSV)
        archive.writestr("stops.txt", STOPS_CSV if not broken_stop else STOPS_CSV.replace("43.3629,-8.4101", "200.0,-8.4101"))
        archive.writestr("trips.txt", TRIPS_CSV)
        archive.writestr("stop_times.txt", STOP_TIMES_CSV)
        archive.writestr("shapes.txt", SHAPES_CSV)
        if include_calendar:
            archive.writestr("calendar.txt", CALENDAR_CSV)
        if include_calendar_dates:
            archive.writestr("calendar_dates.txt", CALENDAR_DATES_CSV)
        archive.writestr("agency.txt", AGENCY_CSV)
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
