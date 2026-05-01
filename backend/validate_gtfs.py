"""
GTFS validator.

Provides a standalone CLI for checking GTFS ZIP structure and integrity before
running the loader. Includes validation for GTFS schema, data referential integrity,
geometry validation, and NGSI-LD entity structure conformance.
"""
# flake8: noqa

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from load_gtfs import GTFSFeed, GTFSLoadError, GTFSValidationError, read_gtfs_feed, validate_feed

LOGGER = logging.getLogger(__name__)


@dataclass
class ValidationSummary:
    valid: bool
    errors: List[str]

    def as_dict(self) -> dict:
        return {"valid": self.valid, "errors": self.errors}


def _validate_time_format(time_str: Optional[str], context: str = "") -> bool:
    """Validate that a time string matches HH:MM:SS format."""
    if not time_str:
        return False
    # GTFS allows HH:MM:SS format, including up to 24+ hours for multi-day shifts
    pattern = r"^(\d{1,2}):([0-5]\d):([0-5]\d)$"
    if not re.match(pattern, time_str):
        LOGGER.warning(f"Invalid time format '{time_str}' {context}")
        return False
    return True


def _parse_time_to_seconds(time_str: Optional[str]) -> Optional[int]:
    """Parse HH:MM:SS to seconds since midnight (or 00:00:00)."""
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        if len(parts) != 3:
            return None
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        return None


def _validate_coordinate(lat: Optional[float], lon: Optional[float], context: str = "") -> bool:
    """Validate that coordinates are within valid geographic bounds."""
    if lat is None or lon is None:
        return False
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        LOGGER.warning(f"Coordinates out of valid range: lat={lat}, lon={lon} {context}")
        return False
    return True


def _validate_stop_time_sequence(feed: GTFSFeed) -> List[str]:
    """Validate that stop_times within each trip are chronologically ordered."""
    errors: List[str] = []
    
    from load_gtfs import _optional_value, _optional_int
    
    stop_times_by_trip: Dict[str, List[Dict[str, str]]] = {}
    for row in feed.stop_times:
        trip_id = _optional_value(row, "trip_id")
        if trip_id:
            if trip_id not in stop_times_by_trip:
                stop_times_by_trip[trip_id] = []
            stop_times_by_trip[trip_id].append(row)
    
    for trip_id, rows in stop_times_by_trip.items():
        # Sort by stop_sequence
        sorted_rows = sorted(
            rows,
            key=lambda r: _optional_int(_optional_value(r, "stop_sequence")) or 0
        )
        
        for i in range(len(sorted_rows) - 1):
            curr_row = sorted_rows[i]
            next_row = sorted_rows[i + 1]
            
            curr_departure = _optional_value(curr_row, "departure_time")
            next_arrival = _optional_value(next_row, "arrival_time")
            # Validate time format before comparing
            seq_curr = _optional_value(curr_row, "stop_sequence")
            seq_next = _optional_value(next_row, "stop_sequence")

            if not _validate_time_format(curr_departure, f"trip {trip_id} seq {seq_curr}"):
                errors.append(
                    f"Invalid time format '{curr_departure}' in stop_times.txt trip_id '{trip_id}' stop_sequence '{seq_curr}'"
                )
                continue

            if not _validate_time_format(next_arrival, f"trip {trip_id} seq {seq_next}"):
                errors.append(
                    f"Invalid time format '{next_arrival}' in stop_times.txt trip_id '{trip_id}' stop_sequence '{seq_next}'"
                )
                continue

            curr_seconds = _parse_time_to_seconds(curr_departure)
            next_seconds = _parse_time_to_seconds(next_arrival)

            if curr_seconds is not None and next_seconds is not None:
                if curr_seconds > next_seconds:
                    errors.append(
                        f"stop_times.txt trip_id '{trip_id}' has non-chronological stops: "
                        f"departure at sequence {seq_curr} ({curr_departure}) > arrival at next sequence ({next_arrival})"
                    )
    
    return errors


def _validate_shapes_geometry(feed: GTFSFeed) -> List[str]:
    """Validate shapes have valid geometry (minimum 2 points for LineString)."""
    errors: List[str] = []
    
    from load_gtfs import _optional_value, _optional_float
    from collections import defaultdict
    
    shapes_by_id: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in feed.shapes:
        shape_id = _optional_value(row, "shape_id")
        if shape_id:
            shapes_by_id[shape_id].append(row)
    
    for shape_id, rows in shapes_by_id.items():
        sorted_rows = sorted(
            rows,
            key=lambda r: _optional_float(_optional_value(r, "shape_pt_sequence")) or 0.0
        )
        
        if len(sorted_rows) < 2:
            errors.append(
                f"shapes.txt shape_id '{shape_id}' has fewer than 2 points (invalid LineString)"
            )
            continue
        
        for row in sorted_rows:
            lat_raw = _optional_value(row, "shape_pt_lat")
            lon_raw = _optional_value(row, "shape_pt_lon")
            lat = _optional_float(lat_raw)
            lon = _optional_float(lon_raw)
            
            if not _validate_coordinate(lat, lon, f"in shapes.txt shape_id '{shape_id}'"):
                if lat is not None and lon is not None:
                    errors.append(
                        f"shapes.txt shape_id '{shape_id}' has out-of-range coordinates: "
                        f"lat={lat}, lon={lon}"
                    )
    
    return errors


def _validate_arrival_departure_times(feed: GTFSFeed) -> List[str]:
    """Validate that arrival_time <= departure_time within each stop_time."""
    errors: List[str] = []
    
    from load_gtfs import _optional_value
    
    for row in feed.stop_times:
        trip_id = _optional_value(row, "trip_id")
        stop_id = _optional_value(row, "stop_id")
        stop_seq = _optional_value(row, "stop_sequence")
        
        arrival_str = _optional_value(row, "arrival_time")
        departure_str = _optional_value(row, "departure_time")
        
        if not arrival_str or not departure_str:
            continue

        # Ensure times are correctly formatted
        if not _validate_time_format(arrival_str, f"trip {trip_id} stop {stop_id} seq {stop_seq}"):
            errors.append(
                f"Invalid time format '{arrival_str}' in stop_times.txt trip_id '{trip_id}' stop_sequence '{stop_seq}'"
            )
            continue

        if not _validate_time_format(departure_str, f"trip {trip_id} stop {stop_id} seq {stop_seq}"):
            errors.append(
                f"Invalid time format '{departure_str}' in stop_times.txt trip_id '{trip_id}' stop_sequence '{stop_seq}'"
            )
            continue

        arrival_seconds = _parse_time_to_seconds(arrival_str)
        departure_seconds = _parse_time_to_seconds(departure_str)

        if arrival_seconds is not None and departure_seconds is not None:
            if arrival_seconds > departure_seconds:
                errors.append(
                    f"stop_times.txt has arrival_time > departure_time for trip_id '{trip_id}', "
                    f"stop_id '{stop_id}', sequence {stop_seq}: "
                    f"arrival={arrival_str}, departure={departure_str}"
                )
    
    return errors


def validate_extended_gtfs(feed: GTFSFeed) -> List[str]:
    """Validate a GTFS feed with extended checks beyond basic schema validation."""
    errors: List[str] = []
    
    # Run extended validations
    LOGGER.info("Running extended GTFS validation checks...")
    
    errors.extend(_validate_stop_time_sequence(feed))
    LOGGER.info(f"Stop time sequence validation: {len([e for e in errors if 'non-chronological' in e])} issues found")
    
    errors.extend(_validate_shapes_geometry(feed))
    LOGGER.info(f"Shapes geometry validation: {len([e for e in errors if 'fewer than 2 points' in e])} issues found")
    
    errors.extend(_validate_arrival_departure_times(feed))
    LOGGER.info(f"Arrival/departure time validation: {len([e for e in errors if 'arrival_time > departure_time' in e])} issues found")
    
    return errors


def validate_ngsi_ld_structure(entities: List[Dict[str, Any]]) -> List[str]:
    """
    Validate that NGSI-LD entities conform to the correct structure.
    
    Checks:
    - Each entity has id, type, and @context
    - Properties have {"type": "Property", "value": ...} structure
    - Relationships have {"type": "Relationship", "object": ...} structure
    - GeoProperties have {"type": "GeoProperty", "value": {"type": "Point|LineString", "coordinates": [...]}} structure
    - Proper type alignment (e.g., stopSequence should be integer)
    """
    errors: List[str] = []
    
    LOGGER.info(f"Validating NGSI-LD structure for {len(entities)} entities...")
    
    for i, entity in enumerate(entities):
        entity_type = entity.get("type", "Unknown")
        entity_id = entity.get("id", "no-id")
        
        # Check required fields
        if "id" not in entity:
            errors.append(f"Entity {i} ({entity_type}) missing 'id' field")
            continue
        if "type" not in entity:
            errors.append(f"Entity {entity_id} missing 'type' field")
            continue
        if "@context" not in entity:
            errors.append(f"Entity {entity_id} ({entity_type}) missing '@context'")
        
        # Validate @context format
        if "@context" in entity:
            context = entity["@context"]
            if not isinstance(context, (str, list)):
                errors.append(f"Entity {entity_id} (@context must be string or list, got {type(context).__name__})")
        
        # Validate properties and relationships
        for key, value in entity.items():
            if key in ("id", "type", "@context"):
                continue
            
            if not isinstance(value, dict):
                errors.append(f"Entity {entity_id} property '{key}' is not a dict (got {type(value).__name__})")
                continue
            
            value_type = value.get("type")
            
            if value_type == "Property":
                if "value" not in value:
                    errors.append(f"Entity {entity_id} property '{key}' missing 'value' field")
                # Type-specific checks
                if key == "stopSequence" and "value" in value:
                    if not isinstance(value["value"], int):
                        errors.append(
                            f"Entity {entity_id} property '{key}' should be integer, got {type(value['value']).__name__}"
                        )
                if key in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday") and "value" in value:
                    if not isinstance(value["value"], bool):
                        errors.append(
                            f"Entity {entity_id} property '{key}' should be boolean, got {type(value['value']).__name__}"
                        )
                if key in ("routeType", "wheelchairBoarding", "pickupType", "dropOffType") and "value" in value:
                    if value["value"] is not None and not isinstance(value["value"], int):
                        errors.append(
                            f"Entity {entity_id} property '{key}' should be integer or None, got {type(value['value']).__name__}"
                        )
            
            elif value_type == "Relationship":
                if "object" not in value:
                    errors.append(f"Entity {entity_id} relationship '{key}' missing 'object' field")
                if "object" in value and not isinstance(value["object"], str):
                    errors.append(
                        f"Entity {entity_id} relationship '{key}' object should be string (URN), got {type(value['object']).__name__}"
                    )
            
            elif value_type == "GeoProperty":
                if "value" not in value:
                    errors.append(f"Entity {entity_id} geop property '{key}' missing 'value' field")
                    continue
                geom = value["value"]
                if not isinstance(geom, dict):
                    errors.append(f"Entity {entity_id} geop '{key}' value should be dict, got {type(geom).__name__}")
                    continue
                geom_type = geom.get("type")
                if geom_type not in ("Point", "LineString"):
                    errors.append(f"Entity {entity_id} geop '{key}' has unsupported geometry type '{geom_type}'")
                if "coordinates" not in geom:
                    errors.append(f"Entity {entity_id} geop '{key}' missing 'coordinates'")
                    continue
                coords = geom["coordinates"]
                if geom_type == "Point":
                    if not isinstance(coords, list) or len(coords) != 2:
                        errors.append(
                            f"Entity {entity_id} geop '{key}' (Point) coordinates should be [lon, lat], got {coords}"
                        )
                    else:
                        lon, lat = coords
                        if not _validate_coordinate(lat, lon, f"in entity {entity_id} geop '{key}'"):
                            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                                errors.append(
                                    f"Entity {entity_id} geop '{key}' (Point) has out-of-range coordinates: lat={lat}, lon={lon}"
                                )
                elif geom_type == "LineString":
                    if not isinstance(coords, list) or len(coords) < 2:
                        errors.append(
                            f"Entity {entity_id} geop '{key}' (LineString) should have >=2 coordinate pairs, got {len(coords) if isinstance(coords, list) else '?'}"
                        )
                    else:
                        for coord_idx, coord in enumerate(coords):
                            if not isinstance(coord, list) or len(coord) != 2:
                                errors.append(
                                    f"Entity {entity_id} geop '{key}' (LineString) coordinate {coord_idx} should be [lon, lat], got {coord}"
                                )
                            else:
                                lon, lat = coord
                                if not _validate_coordinate(lat, lon, f"in entity {entity_id} geop '{key}' coord {coord_idx}"):
                                    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                                        errors.append(
                                            f"Entity {entity_id} geop '{key}' (LineString) coordinate {coord_idx} out of range: lat={lat}, lon={lon}"
                                        )
            
            else:
                errors.append(f"Entity {entity_id} attribute '{key}' has unknown type '{value_type}'")
    
    if errors:
        LOGGER.warning(f"NGSI-LD structure validation found {len(errors)} errors")
    else:
        LOGGER.info("NGSI-LD structure validation passed")
    
    return errors


def validate_gtfs(zip_path: str | Path, extended: bool = True) -> ValidationSummary:
    """
    Validate a GTFS ZIP feed and return a structured summary.
    
    Args:
        zip_path: Path to GTFS ZIP file
        extended: If True, run extended validation checks (time sequences, geometry, etc.)
    
    Returns:
        ValidationSummary with valid flag and list of error messages
    """
    LOGGER.info(f"Validating GTFS from {zip_path}")
    
    feed = read_gtfs_feed(zip_path)
    errors = validate_feed(feed)
    
    if extended:
        extended_errors = validate_extended_gtfs(feed)
        errors.extend(extended_errors)
    
    return ValidationSummary(valid=not errors, errors=errors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a GTFS ZIP feed for structure integrity and NGSI-LD conformance"
    )
    parser.add_argument("gtfs_zip", help="Path to the GTFS ZIP file")
    parser.add_argument(
        "--json", action="store_true", help="Print the result as JSON"
    )
    parser.add_argument(
        "--no-extended",
        action="store_true",
        help="Skip extended validation checks (time sequences, geometry, etc.)",
    )
    parser.add_argument(
        "--validate-ngsi-ld",
        action="store_true",
        help="Also validate generated NGSI-LD entities (requires transforming to entities)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging output",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s - %(name)s - %(message)s"
    )

    try:
        summary = validate_gtfs(args.gtfs_zip, extended=not args.no_extended)
        all_errors = list(summary.errors)
        
        # Optional NGSI-LD validation
        if args.validate_ngsi_ld:
            from load_gtfs import build_entities
            
            LOGGER.info("Running NGSI-LD entity structure validation...")
            feed = read_gtfs_feed(args.gtfs_zip)
            if summary.valid:  # Only validate entities if GTFS is valid
                entities = build_entities(feed)
                ngsi_ld_errors = validate_ngsi_ld_structure(entities)
                all_errors.extend(ngsi_ld_errors)
                summary.valid = not all_errors
                summary.errors = all_errors
            else:
                LOGGER.warning("Skipping NGSI-LD validation because GTFS validation failed")
        
        if args.json:
            print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
        else:
            if summary.valid:
                print("✓ GTFS feed is valid")
            else:
                print("✗ GTFS feed is invalid")
                for error in summary.errors:
                    print(f"  - {error}")
        return 0 if summary.valid else 2
    except GTFSValidationError as exc:
        print(str(exc))
        return 2
    except GTFSLoadError as exc:
        print(str(exc))
        return 1
    except Exception as exc:
        LOGGER.error(f"Unexpected error: {exc}", exc_info=True)
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
