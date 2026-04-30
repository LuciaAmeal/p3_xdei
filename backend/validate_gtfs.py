"""
GTFS validator.

Provides a standalone CLI for checking GTFS ZIP structure and integrity before
running the loader.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from load_gtfs import GTFSLoadError, GTFSValidationError, read_gtfs_feed, validate_feed


@dataclass
class ValidationSummary:
    valid: bool
    errors: List[str]

    def as_dict(self) -> dict:
        return {"valid": self.valid, "errors": self.errors}


def validate_gtfs(zip_path: str | Path) -> ValidationSummary:
    """Validate a GTFS ZIP feed and return a structured summary."""

    feed = read_gtfs_feed(zip_path)
    errors = validate_feed(feed)
    return ValidationSummary(valid=not errors, errors=errors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a GTFS ZIP feed")
    parser.add_argument("gtfs_zip", help="Path to the GTFS ZIP file")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        summary = validate_gtfs(args.gtfs_zip)
        if args.json:
            print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
        else:
            if summary.valid:
                print("GTFS feed is valid")
            else:
                print("GTFS feed is invalid")
                for error in summary.errors:
                    print(f"- {error}")
        return 0 if summary.valid else 2
    except GTFSValidationError as exc:
        print(str(exc))
        return 2
    except GTFSLoadError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
