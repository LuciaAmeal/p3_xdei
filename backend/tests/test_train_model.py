from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from train_model import FEATURE_COLUMNS, TARGET_COLUMN, TrainingError, load_training_dataset, save_training_artifacts, train_model


def _make_training_frame(rows: int = 30) -> pd.DataFrame:
    data = []
    for index in range(rows):
        route_encoded = index % 3
        stop_encoded = index % 4
        hour = index % 24
        day = index % 7
        lag = 20 + index * 0.5
        rolling = 22 + index * 0.4
        occupancy = 25 + route_encoded * 4 + stop_encoded * 2 + day + hour * 0.1 + lag * 0.2 + rolling * 0.1
        data.append(
            {
                "route": f"urn:ngsi-ld:GtfsRoute:r{route_encoded}",
                "stop": f"urn:ngsi-ld:GtfsStop:s{stop_encoded}",
                "route_encoded": route_encoded,
                "stop_encoded": stop_encoded,
                "day": day,
                "hour": hour,
                "prev_occupancy_lag1": lag,
                "prev_occupancy_rolling5min": rolling,
                "occupancy": occupancy,
                "target": occupancy,
                "timestamp": f"2026-05-03T{hour:02d}:00:00Z",
            }
        )
    return pd.DataFrame(data)


def test_load_training_dataset_rejects_missing_columns(tmp_path):
    frame = _make_training_frame().drop(columns=[TARGET_COLUMN])
    dataset_path = tmp_path / "occupancy.csv"
    frame.to_csv(dataset_path, index=False)

    with pytest.raises(TrainingError):
        load_training_dataset(dataset_path)


def test_train_model_and_save_artifacts(tmp_path):
    frame = _make_training_frame()
    dataset_path = tmp_path / "occupancy.csv"
    frame.to_csv(dataset_path, index=False)

    encoder_path = tmp_path / "occupancy_encoders.json"
    encoder_path.write_text(
        json.dumps({"routes": ["r0", "r1", "r2"], "stops": ["s0", "s1", "s2", "s3"]}),
        encoding="utf-8",
    )

    dataset = load_training_dataset(dataset_path)
    estimator, metrics, feature_importances = train_model(dataset, test_size=0.25, random_state=7, n_estimators=25)

    assert hasattr(estimator, "predict")
    assert metrics.train_rows > 0
    assert metrics.test_rows > 0
    assert set(feature_importances["feature"]) == set(FEATURE_COLUMNS)

    model_output_path = tmp_path / "models" / "occupancy_model.pkl"
    artifacts = save_training_artifacts(
        estimator,
        metrics,
        feature_importances,
        dataset_path=dataset_path,
        model_output_path=model_output_path,
        encoders_path=encoder_path,
    )

    assert artifacts["model"].exists()
    assert artifacts["metadata"].exists()
    assert artifacts["feature_importances"].exists()

    metadata = json.loads(artifacts["metadata"].read_text(encoding="utf-8"))
    assert metadata["modelVersion"] == "randomforest-v1"
    assert metadata["featureColumns"] == FEATURE_COLUMNS
    assert metadata["encodersPath"] == str(encoder_path)
    assert metadata["metrics"]["train_rows"] == metrics.train_rows


def test_main_writes_model_and_metadata(tmp_path, capsys):
    frame = _make_training_frame()
    dataset_path = tmp_path / "occupancy.csv"
    frame.to_csv(dataset_path, index=False)
    (tmp_path / "occupancy_encoders.json").write_text(
        json.dumps({"routes": ["r0"], "stops": ["s0"]}),
        encoding="utf-8",
    )

    model_output_path = tmp_path / "artifacts" / "occupancy_model.pkl"
    from train_model import main

    exit_code = main(
        [
            "--dataset",
            str(dataset_path),
            "--model-output",
            str(model_output_path),
            "--encoders",
            str(tmp_path / "occupancy_encoders.json"),
            "--n-estimators",
            "20",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Model saved to" in captured.out
    assert model_output_path.exists()
    assert model_output_path.with_name("occupancy_model_metadata.json").exists()