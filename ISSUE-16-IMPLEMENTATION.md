# Issue 16 Implementation: ML Dataset Generation

**Status:** ✅ COMPLETED  
**Date:** 2026-05-03  
**Scope:** Generate occupancy dataset from FIWARE (QuantumLeap + Orion) for ML training

## Overview

Implemented `scripts/generate_ml_dataset.py` — a production-ready Python script that:
- Extracts VehicleState occupancy history from QuantumLeap (7 days by default)
- Loads GTFS metadata (stops, trips, routes) from Orion-LD
- Engineers features for RandomForest training: route, stop, day, hour, prev_occupancy (lag1 + rolling3)
- Validates data quality and exports to CSV + JSON encoders
- Includes comprehensive CLI with customizable parameters

## Files Created/Modified

### 1. Backend Dependencies
**File:** `backend/requirements.txt`
- ✅ Added `scikit-learn>=1.4.0`, `joblib>=1.4.0`, `numpy>=1.26.0`
- Compatible with Python 3.12

### 2. Model Directory
**File:** `backend/models/.gitkeep`
- ✅ Created placeholder for trained models (Issue 17 will store `.pkl` here)

### 3. Main Pipeline
**File:** `scripts/generate_ml_dataset.py` (~600 lines)

#### Class: DatasetGenerator
```python
class DatasetGenerator:
    """Generates ML training datasets from FIWARE occupancy history."""
    
    def __init__(orion_client, ql_client, days_back=7, sample_size=None, impute_strategy="forward_fill")
    def load_metadata() -> None                     # Load GTFS from Orion
    def load_vehicle_history() -> List[Dict]       # Get history from QuantumLeap
    def generate_features() -> None                # Feature engineering
    def save_dataset(output_path: str) -> None     # Export CSV + encoders JSON
```

#### CLI Features
- `--days-back` (int, default=7): Historical period in days
- `--output` (str, default=/tmp/occupancy_dataset.csv): CSV output path
- `--sample-size` (int, optional): Max rows to sample
- `--impute` (choice, default=forward_fill): NaN handling strategy
- `--orion-url`, `--ql-url`: Service URLs
- `--fiware-service`, `--fiware-service-path`: FIWARE tenant headers

### 4. Unit Tests
**File:** `backend/tests/test_generate_ml_dataset.py` (450+ lines)

**Test Classes:**
- `TestDatasetGeneratorMetadata` (2 tests)
  - ✓ `test_load_metadata_success`: Loads stops, trips, routes, stop_times
  - ✓ `test_load_metadata_empty`: Handles empty metadata gracefully

- `TestDatasetGeneratorFeatures` (2 tests)
  - ✓ `test_resolve_trip_route_and_stops`: Maps trip → route + stops correctly
  - ✓ `test_parse_occupancy_history`: Parses QuantumLeap time series format

- `TestDatasetGeneratorPipeline` (2 tests)
  - ✓ `test_generate_features_small_dataset`: Full pipeline with mock data
  - ✓ `test_generate_features_creates_valid_records`: Validates feature ranges and distributions

- `TestDatasetGeneratorSerialization` (2 tests)
  - ✓ `test_save_dataset_creates_csv`: Exports valid CSV file
  - ✓ `test_save_dataset_creates_encoders_json`: Saves LabelEncoder mappings

- `TestDatasetGeneratorSampling` (1 test)
  - ✓ `test_generate_features_with_sampling`: `--sample-size` parameter works

**Results:** ✅ 9/9 PASSED in 1.36s (no warnings)

### 5. Documentation
**File:** `scripts/GENERATE_ML_DATASET_README.md`
- Usage examples
- Output file descriptions
- Troubleshooting guide
- Testing instructions

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    FIWARE Data Sources                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │   Orion-LD   │         │ QuantumLeap  │                  │
│  │   (Context   │         │   (Time      │                  │
│  │    Broker)   │         │   Series)    │                  │
│  │              │         │              │                  │
│  │ GtfsStop     │         │ VehicleState │                  │
│  │ GtfsRoute    │         │ .occupancy   │                  │
│  │ GtfsTrip     │         │ .trip        │                  │
│  │ GtfsStopTime │         │ (7 days)     │                  │
│  └──────────────┘         └──────────────┘                  │
│         │                        │                          │
└─────────┼────────────────────────┼──────────────────────────┘
          │                        │
          └────────────┬───────────┘
                       │
           ┌───────────▼───────────┐
           │  DatasetGenerator     │
           ├───────────────────────┤
           │ 1. Load metadata      │
           │ 2. Load history       │
           │ 3. Parse time series  │
           │ 4. Map trip→route     │
           │ 5. Engineer features  │
           │ 6. Validate quality   │
           │ 7. Export CSV+JSON    │
           └───────────┬───────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────▼─────┐ ┌─────▼─────┐  ┌─────▼──────────────┐
   │ CSV Data │ │ Encoders  │  │ Metadata/Stats    │
   │          │ │ (JSON)    │  │ (logged)          │
   │ Features │ │           │  │                   │
   │ + Target │ │ route:    │  │ - Row count       │
   │          │ │   {0:'r1'}│  │ - Feature ranges  │
   │ Cols:    │ │ stop:     │  │ - Target distrib  │
   │ route    │ │   {0:'s1'}│  │ - NaN counts      │
   │ stop     │ └───────────┘  └───────────────────┘
   │ day      │
   │ hour     │
   │ lag1     │
   │ rolling3 │
   │ occupancy│
   │ target   │
   └──────────┘
```

## Features Generated

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `route` | string (encoded) | 0-N_routes | Route ID (LabelEncoded) |
| `stop` | string (encoded) | 0-N_stops | Stop ID (LabelEncoded) |
| `day` | int | 0-6 | Day of week (Monday=0, Sunday=6) |
| `hour` | int | 0-23 | Hour of day (UTC) |
| `prev_occupancy_lag1` | float | 0-100 | Occupancy at t-1 |
| `prev_occupancy_rolling5min` | float | 0-100 | 3-record rolling mean |
| `occupancy` | float | 0-100 | Raw occupancy value |
| `target` | float | 0-100 | **Label** (same as occupancy) |

## Quality Assurance

### Data Validation
- ✅ Occupancy range [0, 100]
- ✅ No NaN in critical features (after imputation)
- ✅ Timestamp parsing (ISO8601 format)
- ✅ Entity ID resolution (NGSI-LD format)
- ✅ Relationship mapping (trip→route, trip→stops)

### Imputation Strategies
1. **forward_fill** (default): Use last valid value per route-stop group
2. **drop**: Remove rows with NaN (conservative, smaller dataset)
3. **mean**: Fill with column mean (less group-aware)

### Test Coverage
- Metadata loading and caching
- Time series parsing (QuantumLeap format)
- Feature engineering correctness
- CSV serialization
- JSON encoder mapping
- Sampling functionality

## Usage

### Installation
```bash
cd /home/elena/xdei/p3_xdei
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Generate Dataset (Default: 7 days)
```bash
python scripts/generate_ml_dataset.py \
  --output /tmp/occupancy.csv
```

### With Options
```bash
python scripts/generate_ml_dataset.py \
  --days-back 14 \
  --output /tmp/occupancy.csv \
  --sample-size 10000 \
  --impute mean \
  --fiware-service myservice
```

### Run Tests
```bash
pytest backend/tests/test_generate_ml_dataset.py -v
```

## Integration with Issue 17 (train_model.py)

The generated dataset is designed for Issue 17 (RandomForest training):

1. **Input:** `/tmp/occupancy.csv` (from Issue 16)
2. **Processing:** 
   - Load dataset and encoders
   - Split into train/test
   - Train RandomForest on features: `[route_encoded, stop_encoded, day, hour, prev_occupancy_lag1, prev_occupancy_rolling5min]`
   - Target: `occupancy`
3. **Output:** `/backend/models/occupancy_model.pkl`

## Integration with Issue 18 (Prediction Endpoint)

Issue 18 will load the trained model and use it in the `/api/predict` endpoint:

```
Request:
{
  "stopId": "urn:ngsi-ld:GtfsStop:s1",
  "dateTime": "2026-05-03T14:30:00Z",
  "horizonMinutes": 30
}

Response:
{
  "predictedOccupancy": 65,
  "confidence": 0.92,
  "modelVersion": "randomforest-v1"
}
```

## Known Limitations & Future Work

1. **Horizon Distance:** Currently uses same timestamp as target (t=0). Issue 18 will add horizon offset.
2. **Rolling Window:** Uses 3-record window instead of time-based (5min) due to irregular sampling.
3. **Categorical Encoding:** Uses LabelEncoder (ordinal). Consider OneHotEncoder if cardinality is very high.
4. **Imbalanced Classes:** No explicit class balancing (check target distribution in validation logs).

## Deployment Checklist

- ✅ Script created and tested
- ✅ Dependencies added to requirements.txt
- ✅ Models directory created
- ✅ Unit tests (9/9 passing)
- ✅ CLI with help and examples
- ✅ Documentation (README + inline docstrings)
- ✅ Encoder saving (for Issue 17 inference)
- ⏳ Integration test (will run with real FIWARE in CI/CD)
- ⏳ Performance tuning (batch processing for large datasets)

## References

- **QuantumLeap API:** `backend/clients/quantumleap.py` → `get_time_series()`
- **Orion API:** `backend/clients/orion.py` → `get_entities()`
- **Prediction Service:** `backend/prediction_service.py` (current heuristic baseline)
- **Test Patterns:** `backend/tests/test_prediction_service.py` (fixtures, stubs)
- **Data Model:** `data_model.md` (VehicleState, GtfsStop, GtfsTrip, GtfsRoute, StopCrowdPrediction)

---

**Issue 16 Ready for Merge** ✅

Next: Issue 17 (train_model.py) will consume this dataset and generate occupancy_model.pkl
