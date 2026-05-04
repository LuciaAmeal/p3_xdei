"""Prediction service for stop occupancy estimation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Tuple

from utils.logger import setup_logger

logger = setup_logger(__name__)

try:
    import joblib  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    joblib = None


class PredictionServiceError(Exception):
    """Base exception for prediction service failures."""


class PredictionValidationError(PredictionServiceError):
    """Raised when the request payload is invalid."""


class PredictionNotFoundError(PredictionServiceError):
    """Raised when the requested stop cannot be resolved."""


class PredictionDependencyError(PredictionServiceError):
    """Raised when upstream FIWARE data sources fail."""


@dataclass
class CacheEntry:
    value: Dict[str, Any]
    expires_at: float


class TTLCache:
    def __init__(self, ttl_seconds: int, max_entries: int = 256):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self._entries: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._entries.get(key)
        if entry is None:
            return None

        if entry.expires_at <= time.monotonic():
            self._entries.pop(key, None)
            return None

        return entry.value

    def set(self, key: str, value: Dict[str, Any]) -> None:
        if len(self._entries) >= self.max_entries:
            expired_keys = [cache_key for cache_key, entry in self._entries.items() if entry.expires_at <= time.monotonic()]
            for cache_key in expired_keys:
                self._entries.pop(cache_key, None)

        if len(self._entries) >= self.max_entries:
            oldest_key = next(iter(self._entries), None)
            if oldest_key is not None:
                self._entries.pop(oldest_key, None)

        self._entries[key] = CacheEntry(value=value, expires_at=time.monotonic() + self.ttl_seconds)


def _normalize_history_value(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("type") == "Point":
            coordinates = value.get("coordinates")
            if isinstance(coordinates, list) and len(coordinates) >= 2:
                return [coordinates[0], coordinates[1]]

        if "object" in value and isinstance(value["object"], str):
            return value["object"]

        if "value" in value and not isinstance(value["value"], (dict, list)):
            return value["value"]

    return value


def _is_vehicle_state_entity_id(entity_id: str) -> bool:
    if not isinstance(entity_id, str):
        return False

    parts = entity_id.split(":")
    return len(parts) >= 4 and parts[2] == "VehicleState"


def _entity_suffix(entity_id: str) -> str:
    return entity_id.rsplit(":", 1)[-1]


def _parse_iso_datetime(raw_value: Optional[str]) -> datetime:
    if raw_value in (None, ""):
        return datetime.now(timezone.utc)

    normalized = raw_value.strip()
    if not normalized:
        return datetime.now(timezone.utc)

    candidate = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_history_records(series_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    timestamps = series_data.get("index")
    attributes = series_data.get("attributes")

    if not isinstance(timestamps, list) or not isinstance(attributes, list):
        return []

    records: List[Dict[str, Any]] = []
    for position, timestamp in enumerate(timestamps):
        record: Dict[str, Any] = {"timestamp": timestamp}

        for attribute in attributes:
            if not isinstance(attribute, dict):
                continue

            attr_name = attribute.get("attrName") or attribute.get("name")
            if not attr_name:
                continue

            values = attribute.get("values")
            if isinstance(values, list):
                if position < len(values):
                    record[attr_name] = _normalize_history_value(values[position])
            elif position == 0:
                record[attr_name] = _normalize_history_value(values)

        records.append(record)

    return records


def _safe_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


class StopCrowdPredictor:
    """Estimate occupancy for a stop using Orion-LD and QuantumLeap data."""

    def __init__(
        self,
        orion_client,
        ql_client,
        cache_ttl_seconds: int = 900,
        model_path: Optional[str] = None,
        model_version: str = "heuristic-v1",
        default_horizon_minutes: int = 30,
        history_window_days: int = 14,
    ):
        self.orion_client = orion_client
        self.ql_client = ql_client
        self.cache = TTLCache(cache_ttl_seconds)
        self.model_path = model_path
        self.model_version = model_version
        self.default_horizon_minutes = max(1, int(default_horizon_minutes))
        self.history_window_days = max(1, int(history_window_days))
        self._model = None
        self._model_metadata = self._load_model_metadata(model_path)
        if self._model_metadata:
            # If metadata contains explicit version use it, otherwise use file stem
            self.model_version = self._model_metadata.get("modelVersion") or self._model_metadata.get("version") or self.model_version
        # Attempt to load binary model if provided
        if model_path:
            self._try_load_model(model_path)

    def predict(
        self,
        stop_id: str,
        target_datetime: Optional[str] = None,
        horizon_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        canonical_stop_id = self._normalize_stop_id(stop_id)
        if not canonical_stop_id:
            raise PredictionValidationError("stopId is required")

        horizon = self.default_horizon_minutes if horizon_minutes is None else int(horizon_minutes)
        if horizon < 1:
            raise PredictionValidationError("horizonMinutes must be at least 1")

        target_dt = _parse_iso_datetime(target_datetime)
        cache_key = self._cache_key(canonical_stop_id, target_dt, horizon)
        cached_prediction = self.cache.get(cache_key)
        if cached_prediction is not None:
            logger.debug("Prediction cache hit for %s", cache_key)
            return cached_prediction
        logger.debug("Prediction cache miss for %s", cache_key)

        stop_entity = self._resolve_stop_entity(canonical_stop_id)
        if stop_entity is None:
            raise PredictionNotFoundError(f"Stop not found: {canonical_stop_id}")

        served_trip_ids, served_route_ids = self._resolve_served_trip_ids(stop_entity)
        current_samples = self._collect_current_occupancy(served_trip_ids)
        historical_samples = self._collect_historical_occupancy(served_trip_ids, target_dt)

        predicted_occupancy, confidence = self._estimate_prediction(
            served_trip_ids=served_trip_ids,
            served_route_ids=served_route_ids,
            current_samples=current_samples,
            historical_samples=historical_samples,
            horizon_minutes=horizon,
        )

        prediction = {
            "stopId": stop_entity["id"],
            "stopName": self._attribute_value(stop_entity, "stopName"),
            "predictedOccupancy": predicted_occupancy,
            "confidence": confidence,
            "validFrom": _format_iso_z(target_dt),
            "validTo": _format_iso_z(target_dt + timedelta(minutes=horizon)),
            "modelVersion": self.model_version,
            "horizonMinutes": horizon,
            "tripIds": served_trip_ids,
            "routeIds": served_route_ids,
            "sampleCount": len(historical_samples),
            "currentSampleCount": len(current_samples),
        }

        self.cache.set(cache_key, prediction)
        return prediction

    def predict_series(
        self,
        stop_id: str,
        target_datetime: Optional[str] = None,
        prediction_horizon_minutes: Optional[int] = None,
        series_horizon_minutes: Optional[int] = 120,
        series_step_minutes: Optional[int] = 15,
    ) -> Dict[str, Any]:
        canonical_stop_id = self._normalize_stop_id(stop_id)
        if not canonical_stop_id:
            raise PredictionValidationError("stopId is required")

        summary_horizon = self.default_horizon_minutes if prediction_horizon_minutes is None else int(prediction_horizon_minutes)
        if summary_horizon < 1:
            raise PredictionValidationError("horizonMinutes must be at least 1")

        series_horizon = 120 if series_horizon_minutes is None else int(series_horizon_minutes)
        if series_horizon < 1:
            raise PredictionValidationError("seriesHorizonMinutes must be at least 1")

        step_minutes = 15 if series_step_minutes is None else int(series_step_minutes)
        if step_minutes < 1:
            raise PredictionValidationError("seriesStepMinutes must be at least 1")

        step_minutes = min(step_minutes, series_horizon)
        target_dt = _parse_iso_datetime(target_datetime)
        summary_prediction = self.predict(
            stop_id=canonical_stop_id,
            target_datetime=_format_iso_z(target_dt),
            horizon_minutes=summary_horizon,
        )

        series: List[Dict[str, Any]] = []
        for offset_minutes in range(0, series_horizon + 1, step_minutes):
            point_dt = target_dt + timedelta(minutes=offset_minutes)
            point_prediction = self.predict(
                stop_id=canonical_stop_id,
                target_datetime=_format_iso_z(point_dt),
                horizon_minutes=step_minutes,
            )
            series.append(
                {
                    "timestamp": _format_iso_z(point_dt),
                    "predictedOccupancy": point_prediction["predictedOccupancy"],
                    "confidence": point_prediction["confidence"],
                    "validFrom": point_prediction["validFrom"],
                    "validTo": point_prediction["validTo"],
                    "horizonMinutes": point_prediction["horizonMinutes"],
                }
            )

        return {
            **summary_prediction,
            "predictionHorizonMinutes": summary_horizon,
            "seriesHorizonMinutes": series_horizon,
            "seriesStepMinutes": step_minutes,
            "series": series,
        }

    def _try_load_model(self, model_path: Optional[str]) -> None:
        if not model_path:
            return

        path = Path(model_path)
        if not path.exists():
            logger.info("No prediction model found at %s", path)
            return

        try:
            if joblib is not None and path.suffix.lower() in (".pkl", ".joblib"):
                logger.info("Loading prediction model from %s using joblib", path)
                self._model = joblib.load(str(path))
            else:
                # Fallback to pickle
                logger.info("Loading prediction model from %s using pickle", path)
                import pickle

                with path.open("rb") as fh:
                    self._model = pickle.load(fh)

            # Try to infer version from model object if possible
            version = None
            if isinstance(self._model, dict):
                version = self._model.get("modelVersion") or self._model.get("version")
            else:
                version = getattr(self._model, "version", None)

            if version:
                self.model_version = version
                self._model_metadata = self._model_metadata or {"modelVersion": version}

            logger.info("Prediction model loaded, version=%s", self.model_version)
        except Exception as exc:  # pragma: no cover - optional runtime error
            logger.warning("Failed to load prediction model from %s: %s", model_path, exc)
            self._model = None

    def _cache_key(self, stop_id: str, target_dt: datetime, horizon_minutes: int) -> str:
        return json.dumps(
            {
                "stopId": stop_id,
                "targetDateTime": _format_iso_z(target_dt),
                "horizonMinutes": horizon_minutes,
                "modelVersion": self.model_version,
            },
            sort_keys=True,
        )

    def _load_model_metadata(self, model_path: Optional[str]) -> Optional[Dict[str, Any]]:
        if not model_path:
            return None

        path = Path(model_path)
        if not path.exists():
            logger.warning("Prediction model path not found: %s", path)
            return None

        if path.suffix.lower() == ".json":
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Unable to load prediction model metadata from %s: %s", path, exc)
                return None

        return {"modelVersion": path.stem}

    def _normalize_stop_id(self, stop_id: str) -> Optional[str]:
        if not isinstance(stop_id, str):
            return None

        normalized = stop_id.strip()
        return normalized or None

    def _attribute_value(self, entity: Dict[str, Any], name: str, default: Any = None) -> Any:
        attribute = entity.get(name)
        if isinstance(attribute, dict):
            return attribute.get("value", default)
        return default

    def _entity_matches_stop(self, entity_id: str, stop_id: str) -> bool:
        return entity_id == stop_id or _entity_suffix(entity_id) == _entity_suffix(stop_id)

    def _resolve_stop_entity(self, stop_id: str) -> Optional[Dict[str, Any]]:
        try:
            stops = self.orion_client.get_entities(entity_type="GtfsStop", limit=500)
        except Exception as exc:  # pragma: no cover - mapped to caller
            raise PredictionDependencyError(f"Unable to load stops: {exc}") from exc

        for stop in stops:
            if not isinstance(stop, dict):
                continue

            entity_id = stop.get("id")
            if entity_id and self._entity_matches_stop(entity_id, stop_id):
                return stop

        return None

    def _resolve_served_trip_ids(self, stop_entity: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        stop_entity_id = stop_entity.get("id")
        if not stop_entity_id:
            return [], []

        try:
            stop_times = self.orion_client.get_entities(entity_type="GtfsStopTime", limit=500)
            trips = self.orion_client.get_entities(entity_type="GtfsTrip", limit=500)
        except Exception as exc:  # pragma: no cover - mapped to caller
            raise PredictionDependencyError(f"Unable to load trip context: {exc}") from exc

        trip_lookup = {
            trip["id"]: trip
            for trip in trips
            if isinstance(trip, dict) and trip.get("id")
        }

        served_trip_ids: List[str] = []
        served_route_ids: List[str] = []

        for stop_time in stop_times:
            if not isinstance(stop_time, dict):
                continue

            stop_ref = self._relationship_object(stop_time, "hasStop")
            if not stop_ref or not self._entity_matches_stop(stop_ref, stop_entity_id):
                continue

            trip_ref = self._relationship_object(stop_time, "hasTrip")
            if trip_ref and trip_ref not in served_trip_ids:
                served_trip_ids.append(trip_ref)

            trip_entity = trip_lookup.get(trip_ref or "")
            if trip_entity:
                route_ref = self._relationship_object(trip_entity, "hasRoute")
                if route_ref and route_ref not in served_route_ids:
                    served_route_ids.append(route_ref)

        return served_trip_ids, served_route_ids

    def _relationship_object(self, entity: Dict[str, Any], name: str) -> Optional[str]:
        attribute = entity.get(name)
        if isinstance(attribute, dict):
            object_id = attribute.get("object")
            if isinstance(object_id, str):
                return object_id
        return None

    def _collect_current_occupancy(self, served_trip_ids: Sequence[str]) -> List[float]:
        if not served_trip_ids:
            return []

        try:
            vehicles = self.orion_client.get_entities(entity_type="VehicleState", limit=500)
        except Exception as exc:  # pragma: no cover - mapped to caller
            raise PredictionDependencyError(f"Unable to load current vehicles: {exc}") from exc

        samples: List[float] = []
        for vehicle in vehicles:
            if not isinstance(vehicle, dict):
                continue

            trip_ref = self._relationship_object(vehicle, "trip")
            if trip_ref not in served_trip_ids:
                continue

            occupancy = _safe_number(self._attribute_value(vehicle, "occupancy"))
            if occupancy is not None:
                samples.append(occupancy)

        return samples

    def _collect_historical_occupancy(self, served_trip_ids: Sequence[str], target_dt: datetime) -> List[float]:
        if not served_trip_ids:
            return []

        try:
            available_entities = self.ql_client.get_available_entities()
        except Exception as exc:  # pragma: no cover - mapped to caller
            raise PredictionDependencyError(f"Unable to load historical entities: {exc}") from exc

        if isinstance(available_entities, dict):
            available_entities = available_entities.get("entities", [])

        vehicle_entity_ids = [
            entity_id
            for entity_id in available_entities
            if isinstance(entity_id, str) and _is_vehicle_state_entity_id(entity_id)
        ]

        if not vehicle_entity_ids:
            return []

        from_date = _format_iso_z(target_dt - timedelta(days=self.history_window_days))
        to_date = _format_iso_z(target_dt)

        samples: List[float] = []
        for entity_id in vehicle_entity_ids[:50]:
            try:
                series_data = self.ql_client.get_time_series(
                    entity_id,
                    attrs=["occupancy", "trip", "status"],
                    from_date=from_date,
                    to_date=to_date,
                    limit=200,
                    offset=0,
                )
            except Exception:
                continue

            if not isinstance(series_data, dict):
                continue

            for record in _extract_history_records(series_data):
                if not isinstance(record, dict):
                    continue

                trip_ref = record.get("trip")
                if trip_ref not in served_trip_ids:
                    continue

                occupancy = _safe_number(record.get("occupancy"))
                if occupancy is not None:
                    samples.append(occupancy)

        return samples

    def _estimate_prediction(
        self,
        served_trip_ids: Sequence[str],
        served_route_ids: Sequence[str],
        current_samples: Sequence[float],
        historical_samples: Sequence[float],
        horizon_minutes: int,
    ) -> Tuple[int, float]:
        historical_mean = mean(historical_samples) if historical_samples else None
        current_mean = mean(current_samples) if current_samples else None

        if historical_mean is not None and current_mean is not None:
            predicted = (historical_mean * 0.7) + (current_mean * 0.3)
        elif current_mean is not None:
            predicted = current_mean
        elif historical_mean is not None:
            predicted = historical_mean
        else:
            service_density = len(served_trip_ids) + len(served_route_ids)
            predicted = 12.0 + (service_density * 4.0) + min(12.0, horizon_minutes / 4.0)

        predicted = max(0.0, min(100.0, predicted))
        predicted_occupancy = int(round(predicted))

        sample_count = len(historical_samples)
        confidence = 0.35 + min(0.4, sample_count * 0.025)
        if current_samples:
            confidence += 0.1
        if served_trip_ids:
            confidence += 0.05
        confidence = max(0.2, min(0.95, confidence))

        return predicted_occupancy, round(confidence, 2)