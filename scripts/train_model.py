#!/usr/bin/env python3
"""Train an occupancy prediction model from the engineered dataset.

This script consumes the CSV produced by ``generate_ml_dataset.py``, trains a
RandomForest regressor, and persists the fitted estimator plus lightweight
metadata for downstream inference.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence, Tuple

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, train_test_split

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from utils.logger import setup_logger

logger = setup_logger(__name__)


FEATURE_COLUMNS = [
    "route_encoded",
    "stop_encoded",
    "day",
    "hour",
    "prev_occupancy_lag1",
    "prev_occupancy_rolling5min",
]
TARGET_COLUMN = "occupancy"
DEFAULT_MODEL_VERSION = "randomforest-v1"


class TrainingError(Exception):
    """Base exception for model training failures."""


@dataclass(frozen=True)
class TrainingMetrics:
    """Evaluation metrics for the fitted model."""

    mae: float
    rmse: float
    r2: float
    train_rows: int
    test_rows: int


def load_training_dataset(dataset_path: str | Path) -> pd.DataFrame:
    """Load and validate the engineered dataset."""
    path = Path(dataset_path)
    if not path.exists():
        raise TrainingError(f"Dataset not found: {path}")

    try:
        df = pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - surfaced to CLI
        raise TrainingError(f"Unable to read dataset {path}: {exc}") from exc

    if df.empty:
        raise TrainingError("Dataset is empty")

    required_columns = set(FEATURE_COLUMNS + [TARGET_COLUMN])
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise TrainingError(f"Dataset is missing required columns: {', '.join(missing_columns)}")

    return df


def _prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Select and clean the training frame."""
    frame = df[FEATURE_COLUMNS + [TARGET_COLUMN]].copy()
    frame = frame.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])
    if frame.empty:
        raise TrainingError("No valid rows remain after dropping missing values")
    return frame


def _build_estimator(random_state: int, n_estimators: int, max_depth: Optional[int]) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=random_state,
        n_jobs=-1,
    )


def train_model(
    df: pd.DataFrame,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
    n_estimators: int = 200,
    max_depth: Optional[int] = None,
    grid_search: bool = False,
) -> Tuple[RandomForestRegressor, TrainingMetrics, pd.DataFrame]:
    """Train a RandomForest model and return the fitted estimator and metrics."""
    frame = _prepare_training_frame(df)

    if len(frame) < 2:
        raise TrainingError("Dataset needs at least 2 rows for train/test split")

    X = frame[FEATURE_COLUMNS]
    y = frame[TARGET_COLUMN]

    test_fraction = min(max(test_size, 0.1), 0.5)
    if len(frame) < 10:
        test_fraction = min(test_fraction, 0.5)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_fraction,
        random_state=random_state,
    )

    base_estimator = _build_estimator(random_state, n_estimators, max_depth)

    if grid_search:
        param_grid = {
            "n_estimators": [100, 200],
            "max_depth": [None, 12],
            "min_samples_split": [2, 5],
            "min_samples_leaf": [1, 2],
        }
        search = GridSearchCV(
            estimator=base_estimator,
            param_grid=param_grid,
            scoring="neg_mean_absolute_error",
            cv=3,
            n_jobs=-1,
            refit=True,
        )
        search.fit(X_train, y_train)
        estimator = search.best_estimator_
        best_params = dict(search.best_params_)
    else:
        estimator = base_estimator.fit(X_train, y_train)
        best_params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
        }

    predictions = estimator.predict(X_test)
    mse = mean_squared_error(y_test, predictions)
    rmse = mse ** 0.5
    metrics = TrainingMetrics(
        mae=float(mean_absolute_error(y_test, predictions)),
        rmse=float(rmse),
        r2=float(r2_score(y_test, predictions)),
        train_rows=int(len(X_train)),
        test_rows=int(len(X_test)),
    )

    importance_frame = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "importance": estimator.feature_importances_,
        }
    ).sort_values("importance", ascending=False)

    setattr(
        estimator,
        "training_metadata",
        {"bestParams": best_params, "metrics": asdict(metrics)},
    )

    return estimator, metrics, importance_frame


def _default_encoder_path(dataset_path: Path) -> Path:
    return dataset_path.with_name(f"{dataset_path.stem}_encoders.json")


def save_training_artifacts(
    estimator: RandomForestRegressor,
    metrics: TrainingMetrics,
    feature_importances: pd.DataFrame,
    *,
    dataset_path: str | Path,
    model_output_path: str | Path,
    model_version: str = DEFAULT_MODEL_VERSION,
    random_state: int = 42,
    test_size: float = 0.2,
    encoders_path: str | Path | None = None,
) -> dict[str, Path]:
    """Persist the fitted model and its metadata sidecars."""
    model_path = Path(model_output_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_path = model_path.with_name(f"{model_path.stem}_metadata.json")
    feature_importances_path = model_path.with_name(f"{model_path.stem}_feature_importances.csv")

    joblib.dump(estimator, model_path)
    feature_importances.to_csv(feature_importances_path, index=False)

    dataset_path = Path(dataset_path)
    resolved_encoders_path = Path(encoders_path) if encoders_path is not None else _default_encoder_path(dataset_path)
    metadata = {
        "modelVersion": model_version,
        "modelType": "RandomForestRegressor",
        "trainedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "datasetPath": str(dataset_path),
        "encodersPath": str(resolved_encoders_path) if resolved_encoders_path.exists() else None,
        "featureColumns": FEATURE_COLUMNS,
        "targetColumn": TARGET_COLUMN,
        "randomState": random_state,
        "testSize": test_size,
        "metrics": asdict(metrics),
        "featureImportancesPath": str(feature_importances_path),
        "bestParams": getattr(estimator, "training_metadata", {}).get("bestParams", {}),
    }

    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    logger.info("Model saved to %s", model_path)
    logger.info("Metadata saved to %s", metadata_path)
    logger.info("Feature importances saved to %s", feature_importances_path)

    return {
        "model": model_path,
        "metadata": metadata_path,
        "feature_importances": feature_importances_path,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a RandomForest model from the engineered occupancy dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/train_model.py \
    --dataset /tmp/occupancy.csv \
    --model-output backend/models/occupancy_model.pkl

  python scripts/train_model.py \
    --dataset /tmp/occupancy.csv \
    --model-output backend/models/occupancy_model.pkl \
    --grid-search
""",
    )
    parser.add_argument("--dataset", required=True, help="Input CSV produced by generate_ml_dataset.py")
    parser.add_argument(
        "--model-output",
        default="backend/models/occupancy_model.pkl",
        help="Output path for the trained model pickle",
    )
    parser.add_argument(
        "--encoders",
        default=None,
        help="Optional encoders JSON produced alongside the dataset",
    )
    parser.add_argument("--test-size", type=float, default=0.2, help="Fraction of data reserved for testing")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for split and model")
    parser.add_argument("--n-estimators", type=int, default=200, help="Number of trees for the default model")
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Maximum tree depth for the default model",
    )
    parser.add_argument(
        "--grid-search",
        action="store_true",
        help="Run a small GridSearchCV instead of the fixed-parameter baseline",
    )
    parser.add_argument(
        "--model-version",
        default=DEFAULT_MODEL_VERSION,
        help="Model version written to metadata for downstream consumers",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        dataset = load_training_dataset(args.dataset)
        estimator, metrics, feature_importances = train_model(
            dataset,
            test_size=args.test_size,
            random_state=args.random_state,
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            grid_search=args.grid_search,
        )

        artifacts = save_training_artifacts(
            estimator,
            metrics,
            feature_importances,
            dataset_path=args.dataset,
            model_output_path=args.model_output,
            model_version=args.model_version,
            random_state=args.random_state,
            test_size=args.test_size,
            encoders_path=args.encoders,
        )

        logger.info(
            "Training completed: mae=%.4f rmse=%.4f r2=%.4f",
            metrics.mae,
            metrics.rmse,
            metrics.r2,
        )
        print(f"\n✓ Model saved to: {artifacts['model']}")
        print(f"  Metadata: {artifacts['metadata']}")
        print(f"  Feature importances: {artifacts['feature_importances']}")
        print(
            "  Metrics: "
            f"mae={metrics.mae:.4f}, rmse={metrics.rmse:.4f}, r2={metrics.r2:.4f}, "
            f"train_rows={metrics.train_rows}, test_rows={metrics.test_rows}"
        )
        return 0

    except TrainingError as exc:
        logger.error("Training failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - CLI safety net
        logger.exception("Unexpected error during training")
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())