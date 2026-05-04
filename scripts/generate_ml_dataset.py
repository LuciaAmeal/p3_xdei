#!/usr/bin/env python3
"""
ML Dataset Generation Pipeline.

Extracts occupancy history from QuantumLeap, maps entities via Orion,
and generates a feature-engineered dataset for occupancy prediction model training.

Usage:
    python generate_ml_dataset.py --days-back 7 --output /tmp/occupancy.csv
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sklearn.preprocessing import LabelEncoder

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from clients.orion import OrionClient, OrionClientError
from clients.quantumleap import QuantumLeapClient, QuantumLeapError
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DatasetGenerationError(Exception):
    """Base exception for dataset generation failures."""


class DatasetGenerator:
    """
    Generates ML training datasets from FIWARE occupancy history.
    
    Workflow:
    1. Load GTFS metadata (stops, trips, routes) from Orion
    2. Get VehicleState historical data from QuantumLeap
    3. Map vehicles -> trips -> routes and stops
    4. Engineer features: route, stop, day, hour, prev_occupancy (lag1, rolling5min)
    5. Validate and export to CSV
    """

    def __init__(
        self,
        orion_client: OrionClient,
        ql_client: QuantumLeapClient,
        days_back: int = 7,
        sample_size: Optional[int] = None,
        impute_strategy: str = "forward_fill",
    ):
        """
        Initialize dataset generator.

        Args:
            orion_client: Orion-LD client for metadata
            ql_client: QuantumLeap client for historical data
            days_back: Number of days of history to extract
            sample_size: Max rows to include (None = all)
            impute_strategy: How to handle NaN values ("forward_fill", "drop", "mean")
        """
        self.orion_client = orion_client
        self.ql_client = ql_client
        self.days_back = days_back
        self.sample_size = sample_size
        self.impute_strategy = impute_strategy

        # Data caches
        self._stops: Dict[str, Dict[str, Any]] = {}
        self._trips: Dict[str, Dict[str, Any]] = {}
        self._routes: Dict[str, Dict[str, Any]] = {}
        self._stop_times: List[Dict[str, Any]] = []

        # Feature encoders
        self.route_encoder = LabelEncoder()
        self.stop_encoder = LabelEncoder()

        # Generated dataset
        self.dataset: Optional[pd.DataFrame] = None

    def _entity_id_suffix(self, entity_id: str) -> str:
        """Extract suffix from NGSI-LD entity ID (e.g., 's1' from 'urn:ngsi-ld:GtfsStop:s1')."""
        return entity_id.rsplit(":", 1)[-1] if ":" in entity_id else entity_id

    def _extract_relationship_id(self, relationship: Dict[str, Any]) -> Optional[str]:
        """Extract entity ID from NGSI-LD relationship object."""
        if isinstance(relationship, dict):
            return relationship.get("object")
        return None

    def load_metadata(self) -> None:
        """Load GTFS metadata from Orion-LD."""
        logger.info("Loading GTFS metadata from Orion...")

        try:
            # Load stops
            stops = self.orion_client.get_entities(entity_type="GtfsStop", limit=1000)
            self._stops = {s["id"]: s for s in stops}
            logger.info(f"Loaded {len(self._stops)} stops")

            # Load trips
            trips = self.orion_client.get_entities(entity_type="GtfsTrip", limit=1000)
            self._trips = {t["id"]: t for t in trips}
            logger.info(f"Loaded {len(self._trips)} trips")

            # Load routes
            routes = self.orion_client.get_entities(entity_type="GtfsRoute", limit=1000)
            self._routes = {r["id"]: r for r in routes}
            logger.info(f"Loaded {len(self._routes)} routes")

            # Load stop times
            self._stop_times = self.orion_client.get_entities(entity_type="GtfsStopTime", limit=10000)
            logger.info(f"Loaded {len(self._stop_times)} stop times")

        except OrionClientError as e:
            raise DatasetGenerationError(f"Failed to load metadata from Orion: {e}") from e

    def _resolve_trip_route_and_stops(self, trip_id: str) -> Tuple[Optional[str], List[str]]:
        """
        Resolve route for a trip and get all stops served by that trip.

        Returns:
            (route_id, [stop_ids])
        """
        trip = self._trips.get(trip_id)
        if not trip:
            return None, []

        # Extract route relationship
        route_rel = trip.get("hasRoute", {})
        route_id = self._extract_relationship_id(route_rel)

        # Get stops for this trip from stop_times
        stops = []
        for st in self._stop_times:
            st_trip = self._extract_relationship_id(st.get("hasTrip", {}))
            if st_trip == trip_id:
                stop_id = self._extract_relationship_id(st.get("hasStop", {}))
                if stop_id:
                    stops.append(stop_id)

        return route_id, stops

    def load_vehicle_history(self) -> List[Dict[str, Any]]:
        """
        Load VehicleState occupancy history from QuantumLeap.

        Returns:
            List of vehicle history records with timestamps and occupancy values
        """
        logger.info("Loading vehicle occupancy history from QuantumLeap...")

        try:
            # Get list of available entities
            available_entities = self.ql_client.get_available_entities()
            vehicle_ids = [e for e in available_entities if "VehicleState" in e]
            logger.info(f"Found {len(vehicle_ids)} vehicles with historical data")

            # Set time window
            to_date = datetime.now(timezone.utc)
            from_date = to_date - timedelta(days=self.days_back)
            from_iso = from_date.isoformat().replace("+00:00", "Z")
            to_iso = to_date.isoformat().replace("+00:00", "Z")

            logger.info(f"Querying occupancy history from {from_iso} to {to_iso}")

            histories = []
            for vehicle_id in vehicle_ids:
                try:
                    # Query occupancy + trip attributes
                    response = self.ql_client.get_time_series(
                        entity_id=vehicle_id,
                        attrs=["occupancy", "trip"],
                        from_date=from_iso,
                        to_date=to_iso,
                        limit=10000,
                    )

                    histories.append((vehicle_id, response))
                except QuantumLeapError as e:
                    logger.warning(f"Failed to load history for {vehicle_id}: {e}")
                    continue

            logger.info(f"Loaded history for {len(histories)} vehicles")
            return histories

        except QuantumLeapError as e:
            raise DatasetGenerationError(f"Failed to load history from QuantumLeap: {e}") from e

    def _parse_occupancy_history(self, response: Dict[str, Any]) -> Tuple[List[str], List[int], List[str]]:
        """
        Parse QuantumLeap time series response into timestamps, occupancy values, and trip values.

        Returns:
            (timestamps, occupancies, trip_ids)
        """
        timestamps = response.get("index", [])
        attributes = response.get("attributes", [])

        occupancies = []
        trip_ids = []

        for attr in attributes:
            attr_name = attr.get("attrName")
            values = attr.get("values", [])

            if attr_name == "occupancy":
                occupancies = [v.get("value") if isinstance(v, dict) else v for v in values]
            elif attr_name == "trip":
                trip_ids = []
                for v in values:
                    if isinstance(v, dict):
                        trip_id = v.get("object")
                    else:
                        trip_id = v
                    trip_ids.append(trip_id)

        return timestamps, occupancies, trip_ids

    def generate_features(self) -> None:
        """
        Generate feature-engineered dataset from vehicle history.

        Features:
        - route: encoded route ID
        - stop: encoded stop ID
        - day: day of week (0-6)
        - hour: hour of day (0-23)
        - prev_occupancy_lag1: previous occupancy value (t-1)
        - prev_occupancy_rolling5min: 3-record rolling mean occupancy
        - target: occupancy value (label)
        """
        logger.info("Generating features from vehicle history...")

        records = []

        try:
            histories = self.load_vehicle_history()

            for vehicle_id, response in histories:
                timestamps, occupancies, trip_ids = self._parse_occupancy_history(response)

                if not timestamps or not occupancies:
                    logger.debug(f"No occupancy data for {vehicle_id}")
                    continue

                # For each occupancy observation, infer route and stops
                for i, (timestamp, occupancy, trip_id) in enumerate(
                    zip(timestamps, occupancies, trip_ids)
                ):
                    if occupancy is None:
                        continue

                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        route_id, stop_ids = self._resolve_trip_route_and_stops(trip_id)

                        if not route_id or not stop_ids:
                            continue

                        # For each stop in the trip, create a record
                        for stop_id in stop_ids:
                            record = {
                                "timestamp": timestamp,
                                "route": route_id,
                                "stop": stop_id,
                                "day": dt.weekday(),
                                "hour": dt.hour,
                                "occupancy": float(occupancy),
                                "vehicle_id": vehicle_id,
                            }
                            records.append(record)
                    except (ValueError, AttributeError) as e:
                        logger.debug(f"Failed to parse record for {vehicle_id}: {e}")
                        continue

            logger.info(f"Generated {len(records)} raw records from vehicle history")

            # Convert to DataFrame
            df = pd.DataFrame(records)
            if df.empty:
                raise DatasetGenerationError("No valid records generated from vehicle history")

            # Sort by timestamp to calculate lags
            df = df.sort_values("timestamp")

            # Engineer lag and rolling features per (route, stop) group
            df["prev_occupancy_lag1"] = df.groupby(["route", "stop"])["occupancy"].shift(1)
            
            # For rolling window, use a simpler 3-record rolling mean (instead of time-based)
            df["prev_occupancy_rolling5min"] = (
                df.groupby(["route", "stop"])["occupancy"]
                .rolling(window=3, min_periods=1)
                .mean()
                .reset_index(drop=True)
            )

            # Drop rows with NaN in features (first observation, etc.)
            if self.impute_strategy == "drop":
                df = df.dropna(subset=["prev_occupancy_lag1", "prev_occupancy_rolling5min"])
            elif self.impute_strategy == "forward_fill":
                df["prev_occupancy_lag1"] = df.groupby(["route", "stop"])["prev_occupancy_lag1"].ffill()
                df["prev_occupancy_rolling5min"] = df.groupby(["route", "stop"])["prev_occupancy_rolling5min"].ffill()
            elif self.impute_strategy == "mean":
                df["prev_occupancy_lag1"].fillna(df["prev_occupancy_lag1"].mean(), inplace=True)
                df["prev_occupancy_rolling5min"].fillna(df["prev_occupancy_rolling5min"].mean(), inplace=True)

            # Encode categorical features
            unique_routes = sorted(df["route"].unique())
            unique_stops = sorted(df["stop"].unique())

            self.route_encoder.fit(unique_routes)
            self.stop_encoder.fit(unique_stops)

            df["route_encoded"] = self.route_encoder.transform(df["route"])
            df["stop_encoded"] = self.stop_encoder.transform(df["stop"])

            # Final feature set for modeling
            df["target"] = df["occupancy"]
            df = df[
                [
                    "route",
                    "stop",
                    "route_encoded",
                    "stop_encoded",
                    "day",
                    "hour",
                    "prev_occupancy_lag1",
                    "prev_occupancy_rolling5min",
                    "occupancy",
                    "target",
                    "timestamp",
                ]
            ]

            # Sample if requested
            if self.sample_size and len(df) > self.sample_size:
                df = df.sample(n=self.sample_size, random_state=42)
                logger.info(f"Sampled {self.sample_size} records")

            # Validate
            self._validate_dataset(df)

            self.dataset = df
            logger.info(f"Generated feature set with {len(df)} rows and {df.shape[1]} columns")

        except Exception as e:
            raise DatasetGenerationError(f"Feature engineering failed: {e}") from e

    def _validate_dataset(self, df: pd.DataFrame) -> None:
        """Validate dataset quality."""
        logger.info("Validating dataset...")

        # Check for NaN in critical features
        critical_cols = ["route_encoded", "stop_encoded", "day", "hour", "prev_occupancy_lag1", "target"]
        nan_counts = df[critical_cols].isna().sum()
        if nan_counts.sum() > 0:
            logger.warning(f"NaN values found: {nan_counts.to_dict()}")

        # Check occupancy ranges
        if (df["occupancy"] < 0).any() or (df["occupancy"] > 100).any():
            logger.warning("Occupancy values outside [0, 100] range detected")

        # Check target distribution
        logger.info(f"Target occupancy stats:\n{df['target'].describe()}")

    def save_dataset(self, output_path: str) -> None:
        """Save generated dataset to CSV."""
        if self.dataset is None:
            raise DatasetGenerationError("No dataset generated. Call generate_features() first.")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save dataset
        self.dataset.to_csv(output_file, index=False)
        logger.info(f"Dataset saved to {output_file}")

        # Save encoders for later use in training
        encoder_path = output_file.parent / f"{output_file.stem}_encoders.json"
        encoders = {
            "routes": list(self.route_encoder.classes_),
            "stops": list(self.stop_encoder.classes_),
        }
        with open(encoder_path, "w") as f:
            json.dump(encoders, f, indent=2)
        logger.info(f"Encoders saved to {encoder_path}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate ML training dataset from occupancy history",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 7-day dataset to /tmp/occupancy.csv
  python generate_ml_dataset.py --days-back 7 --output /tmp/occupancy.csv
  
  # Generate with sampling and custom imputation
  python generate_ml_dataset.py --days-back 14 --output /tmp/occupancy.csv \\
    --sample-size 5000 --impute mean
""",
    )

    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="Number of days of history to extract (default: 7)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/occupancy_dataset.csv",
        help="Output CSV file path (default: /tmp/occupancy_dataset.csv)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Max rows to sample (default: None = all rows)",
    )
    parser.add_argument(
        "--impute",
        choices=["forward_fill", "drop", "mean"],
        default="forward_fill",
        help="Strategy for handling NaN values (default: forward_fill)",
    )
    parser.add_argument(
        "--orion-url",
        type=str,
        default="http://localhost:1026",
        help="Orion-LD base URL (default: http://localhost:1026)",
    )
    parser.add_argument(
        "--ql-url",
        type=str,
        default="http://localhost:8668",
        help="QuantumLeap base URL (default: http://localhost:8668)",
    )
    parser.add_argument(
        "--fiware-service",
        type=str,
        default="default",
        help="FIWARE Service header (default: default)",
    )
    parser.add_argument(
        "--fiware-service-path",
        type=str,
        default="/",
        help="FIWARE Service Path header (default: /)",
    )

    args = parser.parse_args()

    # Setup clients with FIWARE headers
    fiware_headers = {
        "Fiware-Service": args.fiware_service,
        "Fiware-ServicePath": args.fiware_service_path,
    }

    orion_client = OrionClient(
        base_url=args.orion_url,
        fiware_headers=fiware_headers,
    )
    ql_client = QuantumLeapClient(
        base_url=args.ql_url,
        fiware_headers=fiware_headers,
    )

    # Generate dataset
    try:
        generator = DatasetGenerator(
            orion_client=orion_client,
            ql_client=ql_client,
            days_back=args.days_back,
            sample_size=args.sample_size,
            impute_strategy=args.impute,
        )

        logger.info(f"Starting dataset generation for {args.days_back} days of history")
        generator.load_metadata()
        generator.generate_features()
        generator.save_dataset(args.output)

        logger.info("Dataset generation completed successfully!")
        print(f"\n✓ Dataset saved to: {args.output}")
        if generator.dataset is not None:
            print(f"  Shape: {generator.dataset.shape}")
            print(f"  Columns: {list(generator.dataset.columns)}")

    except DatasetGenerationError as e:
        logger.error(f"Dataset generation failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
