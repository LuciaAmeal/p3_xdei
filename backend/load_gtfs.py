"""
GTFS loader.

Parses a GTFS ZIP feed and transforms it into NGSI-LD entities that can be
batch-upserted into Orion-LD.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from clients.orion import OrionClient
from config import settings

LOGGER = logging.getLogger(__name__)
NGSI_LD_CONTEXT = [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "https://smartdatamodels.org/context.jsonld",
]
REQUIRED_FILES = {"routes.txt", "stops.txt", "trips.txt", "stop_times.txt"}
OPTIONAL_FILES = {"calendar.txt", "calendar_dates.txt", "shapes.txt", "agency.txt"}


@dataclass
class GTFSFeed:
    routes: List[Dict[str, str]]
    stops: List[Dict[str, str]]
    trips: List[Dict[str, str]]
    stop_times: List[Dict[str, str]]
    shapes: List[Dict[str, str]]
    calendars: List[Dict[str, str]]
    calendar_dates: List[Dict[str, str]]
    agencies: List[Dict[str, str]]


@dataclass
class LoadSummary:
    total_entities: int = 0
    entity_counts: Dict[str, int] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    batches: int = 0
    errors: int = 0
    dry_run: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "entity_counts": self.entity_counts,
            "validation_errors": self.validation_errors,
            "batches": self.batches,
            "errors": self.errors,
            "dry_run": self.dry_run,
        }


class GTFSLoadError(Exception):
    """Raised when GTFS loading fails."""


class GTFSValidationError(GTFSLoadError):
    """Raised when GTFS validation fails."""


def read_gtfs_feed(zip_path: str | Path) -> GTFSFeed:
    """Read a GTFS ZIP feed into memory as CSV row dictionaries."""

    archive_path = Path(zip_path)
    if not archive_path.exists():
        raise GTFSLoadError(f"GTFS ZIP not found: {archive_path}")

    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        missing = sorted(REQUIRED_FILES - names)
        if missing:
            raise GTFSValidationError(f"Missing required GTFS files: {', '.join(missing)}")

        return GTFSFeed(
            routes=_read_csv(archive, "routes.txt"),
            stops=_read_csv(archive, "stops.txt"),
            trips=_read_csv(archive, "trips.txt"),
            stop_times=_read_csv(archive, "stop_times.txt"),
            shapes=_read_csv(archive, "shapes.txt") if "shapes.txt" in names else [],
            calendars=_read_csv(archive, "calendar.txt") if "calendar.txt" in names else [],
            calendar_dates=_read_csv(archive, "calendar_dates.txt") if "calendar_dates.txt" in names else [],
            agencies=_read_csv(archive, "agency.txt") if "agency.txt" in names else [],
        )


def _read_csv(archive: zipfile.ZipFile, member_name: str) -> List[Dict[str, str]]:
    with archive.open(member_name) as handle:
        text = (line.decode("utf-8-sig") for line in handle)
        reader = csv.DictReader(text)
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def _entity_id(entity_type: str, raw_id: str) -> str:
    return f"urn:ngsi-ld:{entity_type}:{raw_id}"


def _property(value: Any) -> Dict[str, Any]:
    return {"type": "Property", "value": value}


def _relationship(target_id: str) -> Dict[str, Any]:
    return {"type": "Relationship", "object": target_id}


def _geo_property(geometry_type: str, coordinates: Any) -> Dict[str, Any]:
    return {"type": "GeoProperty", "value": {"type": geometry_type, "coordinates": coordinates}}


def _optional_value(row: Dict[str, str], key: str) -> Optional[str]:
    value = row.get(key, "").strip()
    return value or None


def _optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _optional_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def validate_feed(feed: GTFSFeed) -> List[str]:
    """Validate a GTFS feed and return human-readable errors."""

    errors: List[str] = []

    if not feed.routes:
        errors.append("routes.txt is empty")
    if not feed.stops:
        errors.append("stops.txt is empty")
    if not feed.trips:
        errors.append("trips.txt is empty")
    if not feed.stop_times:
        errors.append("stop_times.txt is empty")
    if not feed.calendars and not feed.calendar_dates:
        errors.append("GTFS feed must include calendar.txt or calendar_dates.txt")

    route_ids = _collect_unique_ids(feed.routes, "route_id", errors, "routes.txt")
    stop_ids = _collect_unique_ids(feed.stops, "stop_id", errors, "stops.txt")
    trip_ids = _collect_unique_ids(feed.trips, "trip_id", errors, "trips.txt")
    service_ids = _collect_unique_ids(feed.calendars, "service_id", errors, "calendar.txt")

    for row in feed.trips:
        route_id = _optional_value(row, "route_id")
        service_id = _optional_value(row, "service_id")
        if route_id and route_id not in route_ids:
            errors.append(f"trips.txt references unknown route_id '{route_id}'")
        if service_id and service_ids and service_id not in service_ids:
            errors.append(f"trips.txt references unknown service_id '{service_id}'")
        if service_id and not service_ids and not feed.calendar_dates:
            errors.append(f"trips.txt references service_id '{service_id}' without calendar.txt")

    shapes_by_id: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in feed.shapes:
        shape_id = _optional_value(row, "shape_id")
        if shape_id:
            shapes_by_id[shape_id].append(row)

    for shape_id, rows in shapes_by_id.items():
        sequences: List[int] = []
        for row in rows:
            lat_raw = _optional_value(row, "shape_pt_lat")
            lon_raw = _optional_value(row, "shape_pt_lon")
            if not lat_raw or not lon_raw:
                errors.append(f"shapes.txt missing coordinates for shape_id '{shape_id}'")
                continue
            lat = _optional_float(lat_raw)
            lon = _optional_float(lon_raw)
            if lat is None or lon is None:
                errors.append(f"shapes.txt has invalid coordinates for shape_id '{shape_id}'")
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                errors.append(f"shapes.txt has out-of-range coordinates for shape_id '{shape_id}'")
            sequence = _optional_int(_optional_value(row, "shape_pt_sequence"))
            if sequence is None:
                errors.append(f"shapes.txt missing shape_pt_sequence for shape_id '{shape_id}'")
                continue
            sequences.append(sequence)
        duplicates = sorted({sequence for sequence in sequences if sequences.count(sequence) > 1})
        for duplicate in duplicates:
            errors.append(f"shapes.txt contains duplicate shape_pt_sequence '{duplicate}' for shape_id '{shape_id}'")

    for row in feed.stop_times:
        trip_id = _optional_value(row, "trip_id")
        stop_id = _optional_value(row, "stop_id")
        if trip_id and trip_id not in trip_ids:
            errors.append(f"stop_times.txt references unknown trip_id '{trip_id}'")
        if stop_id and stop_id not in stop_ids:
            errors.append(f"stop_times.txt references unknown stop_id '{stop_id}'")

    for row in feed.stops:
        if not _optional_value(row, "stop_lat") or not _optional_value(row, "stop_lon"):
            errors.append(f"stops.txt missing coordinates for stop_id '{_optional_value(row, 'stop_id')}'")
            continue
        lat = _optional_float(_optional_value(row, "stop_lat"))
        lon = _optional_float(_optional_value(row, "stop_lon"))
        if lat is None or lon is None:
            errors.append(f"stops.txt has invalid coordinates for stop_id '{_optional_value(row, 'stop_id')}'")
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            errors.append(f"stops.txt has out-of-range coordinates for stop_id '{_optional_value(row, 'stop_id')}'")

    return errors


def _collect_unique_ids(
    rows: List[Dict[str, str]],
    key: str,
    errors: List[str],
    filename: str,
    required: bool = True,
) -> set[str]:
    values: List[str] = []
    for row in rows:
        value = _optional_value(row, key)
        if value:
            values.append(value)
        elif required:
            errors.append(f"{filename} missing required field '{key}'")
    duplicates = sorted({value for value in values if values.count(value) > 1})
    for duplicate in duplicates:
        errors.append(f"{filename} contains duplicate {key} '{duplicate}'")
    return set(values)


def build_entities(feed: GTFSFeed) -> List[Dict[str, Any]]:
    """Transform a GTFS feed into NGSI-LD entities."""

    entities: List[Dict[str, Any]] = []
    routes_by_id = {row["route_id"]: row for row in feed.routes if _optional_value(row, "route_id")}
    stops_by_id = {row["stop_id"]: row for row in feed.stops if _optional_value(row, "stop_id")}
    calendars_by_service = {row["service_id"]: row for row in feed.calendars if _optional_value(row, "service_id")}
    calendar_dates_by_service: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in feed.calendar_dates:
        service_id = _optional_value(row, "service_id")
        if service_id:
            calendar_dates_by_service[service_id].append(row)

    agencies = feed.agencies[0] if feed.agencies else {}
    operator_name = _optional_value(agencies, "agency_name") if agencies else None

    for row in feed.routes:
        route_id = _optional_value(row, "route_id")
        if not route_id:
            continue
        entity = {
            "id": _entity_id("GtfsRoute", route_id),
            "type": "GtfsRoute",
            "@context": NGSI_LD_CONTEXT,
            "routeShortName": _property(_optional_value(row, "route_short_name")),
            "routeLongName": _property(_optional_value(row, "route_long_name")),
            "routeDesc": _property(_optional_value(row, "route_desc")),
            "routeType": _property(_optional_int(_optional_value(row, "route_type"))),
        }
        route_color = _optional_value(row, "route_color")
        if route_color:
            entity["routeColor"] = _property(route_color)
        route_text_color = _optional_value(row, "route_text_color")
        if route_text_color:
            entity["routeTextColor"] = _property(route_text_color)
        if operator_name:
            entity["operatorName"] = _property(operator_name)
        entities.append(entity)

    for row in feed.stops:
        stop_id = _optional_value(row, "stop_id")
        if not stop_id:
            continue
        lat = float(_optional_value(row, "stop_lat"))
        lon = float(_optional_value(row, "stop_lon"))
        entity = {
            "id": _entity_id("GtfsStop", stop_id),
            "type": "GtfsStop",
            "@context": NGSI_LD_CONTEXT,
            "stopName": _property(_optional_value(row, "stop_name")),
            "stopCode": _property(_optional_value(row, "stop_code")),
            "stopDesc": _property(_optional_value(row, "stop_desc")),
            "platformCode": _property(_optional_value(row, "platform_code")),
            "wheelchairBoarding": _property(_optional_int(_optional_value(row, "wheelchair_boarding"))),
            "zoneId": _property(_optional_value(row, "zone_id")),
            "location": _geo_property("Point", [lon, lat]),
        }
        entities.append(entity)

    for row in feed.calendars:
        service_id = _optional_value(row, "service_id")
        if not service_id:
            continue
        entity = {
            "id": _entity_id("GtfsService", service_id),
            "type": "GtfsService",
            "@context": NGSI_LD_CONTEXT,
            "startDate": _property(_optional_value(row, "start_date")),
            "endDate": _property(_optional_value(row, "end_date")),
            "monday": _property(_bool_value(row.get("monday"))),
            "tuesday": _property(_bool_value(row.get("tuesday"))),
            "wednesday": _property(_bool_value(row.get("wednesday"))),
            "thursday": _property(_bool_value(row.get("thursday"))),
            "friday": _property(_bool_value(row.get("friday"))),
            "saturday": _property(_bool_value(row.get("saturday"))),
            "sunday": _property(_bool_value(row.get("sunday"))),
        }
        entities.append(entity)

    for service_id, rows in calendar_dates_by_service.items():
        if service_id in calendars_by_service:
            continue
        sorted_dates = sorted(_optional_value(row, "date") for row in rows if _optional_value(row, "date"))
        entity = {
            "id": _entity_id("GtfsService", service_id),
            "type": "GtfsService",
            "@context": NGSI_LD_CONTEXT,
            "startDate": _property(sorted_dates[0] if sorted_dates else None),
            "endDate": _property(sorted_dates[-1] if sorted_dates else None),
            "monday": _property(False),
            "tuesday": _property(False),
            "wednesday": _property(False),
            "thursday": _property(False),
            "friday": _property(False),
            "saturday": _property(False),
            "sunday": _property(False),
        }
        entities.append(entity)

    shapes_by_id: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in feed.shapes:
        shape_id = _optional_value(row, "shape_id")
        if shape_id:
            shapes_by_id[shape_id].append(row)

    for shape_id, rows in shapes_by_id.items():
        ordered_rows = sorted(rows, key=lambda item: _optional_float(_optional_value(item, "shape_pt_sequence")) or 0.0)
        coordinates = [
            [float(_optional_value(shape_row, "shape_pt_lon")), float(_optional_value(shape_row, "shape_pt_lat"))]
            for shape_row in ordered_rows
        ]
        entity = {
            "id": _entity_id("GtfsShape", shape_id),
            "type": "GtfsShape",
            "@context": NGSI_LD_CONTEXT,
            "shapePoints": _property(coordinates),
            "location": _geo_property("LineString", coordinates),
        }
        last_dist = next(
            (
                _optional_float(_optional_value(shape_row, "shape_dist_traveled"))
                for shape_row in reversed(ordered_rows)
                if _optional_value(shape_row, "shape_dist_traveled")
            ),
            None,
        )
        if last_dist is not None:
            entity["shapeLength"] = _property(last_dist)
        entities.append(entity)

    for row in feed.trips:
        trip_id = _optional_value(row, "trip_id")
        if not trip_id:
            continue
        route_id = _optional_value(row, "route_id")
        service_id = _optional_value(row, "service_id")
        shape_id = _optional_value(row, "shape_id")
        entity = {
            "id": _entity_id("GtfsTrip", trip_id),
            "type": "GtfsTrip",
            "@context": NGSI_LD_CONTEXT,
            "tripHeadsign": _property(_optional_value(row, "trip_headsign")),
            "tripShortName": _property(_optional_value(row, "trip_short_name")),
            "directionId": _property(_optional_int(_optional_value(row, "direction_id"))),
            "blockId": _property(_optional_value(row, "block_id")),
            "shapeId": _property(shape_id),
        }
        if route_id:
            entity["hasRoute"] = _relationship(_entity_id("GtfsRoute", route_id))
        if service_id:
            entity["hasService"] = _relationship(_entity_id("GtfsService", service_id))
        if shape_id:
            entity["hasShape"] = _relationship(_entity_id("GtfsShape", shape_id))
        entities.append(entity)

    for row in feed.stop_times:
        trip_id = _optional_value(row, "trip_id")
        stop_id = _optional_value(row, "stop_id")
        stop_sequence = _optional_int(_optional_value(row, "stop_sequence"))
        if not trip_id or not stop_id or stop_sequence is None:
            continue
        entity_id = _entity_id("GtfsStopTime", f"{trip_id}_{stop_sequence:03d}")
        entity = {
            "id": entity_id,
            "type": "GtfsStopTime",
            "@context": NGSI_LD_CONTEXT,
            "arrivalTime": _property(_optional_value(row, "arrival_time")),
            "departureTime": _property(_optional_value(row, "departure_time")),
            "stopSequence": _property(stop_sequence),
            "pickupType": _property(_optional_int(_optional_value(row, "pickup_type"))),
            "dropOffType": _property(_optional_int(_optional_value(row, "drop_off_type"))),
            "hasStop": _relationship(_entity_id("GtfsStop", stop_id)),
            "hasTrip": _relationship(_entity_id("GtfsTrip", trip_id)),
        }
        entities.append(entity)

    return entities


def _bool_value(raw: Optional[str]) -> bool:
    return str(raw or "0").strip() == "1"


def load_gtfs(zip_path: str | Path, orion_client: Optional[OrionClient] = None, batch_size: int = 100, dry_run: bool = False) -> LoadSummary:
    """Load a GTFS ZIP into Orion-LD and return a summary."""

    feed = read_gtfs_feed(zip_path)
    validation_errors = validate_feed(feed)
    if validation_errors:
        raise GTFSValidationError("; ".join(validation_errors))

    entities = build_entities(feed)
    summary = LoadSummary(
        total_entities=len(entities),
        entity_counts=_count_entities(entities),
        dry_run=dry_run,
    )

    if dry_run:
        LOGGER.info("Dry run enabled; skipping Orion-LD upsert")
        return summary

    client = orion_client or OrionClient(
        base_url=settings.orion.url,
        timeout=settings.orion.timeout,
        retries=settings.orion.retries,
        fiware_headers=settings.get_fiware_headers(),
    )
    batch_result = client.batch_upsert(entities, batch_size=batch_size)
    summary.batches = batch_result.get("batches", 0)
    summary.errors = batch_result.get("errors", 0)
    return summary


def _count_entities(entities: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for entity in entities:
        counts[entity["type"]] += 1
    return dict(sorted(counts.items()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load a GTFS ZIP feed into Orion-LD")
    parser.add_argument("gtfs_zip", help="Path to the GTFS ZIP file")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for Orion upserts")
    parser.add_argument("--dry-run", action="store_true", help="Validate and transform without posting")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        summary = load_gtfs(args.gtfs_zip, batch_size=args.batch_size, dry_run=args.dry_run)
        output = summary.as_dict()
        if args.json:
            print(json.dumps(output, indent=2, sort_keys=True))
        else:
            print(f"Loaded {summary.total_entities} entities")
            print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except GTFSValidationError as exc:
        LOGGER.error(str(exc))
        print(str(exc), file=sys.stderr)
        return 2
    except GTFSLoadError as exc:
        LOGGER.error(str(exc))
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
