# ML Dataset Generation Pipeline

## Overview

`generate_ml_dataset.py` extracts occupancy history from FIWARE (QuantumLeap + Orion) and generates a feature-engineered dataset suitable for training occupancy prediction models.

## Features Generated

- **route**: Route ID (LabelEncoded)
- **stop**: Stop ID (LabelEncoded)
- **day**: Day of week (0-6)
- **hour**: Hour of day (0-23)
- **prev_occupancy_lag1**: Previous occupancy value (t-1)
- **prev_occupancy_rolling5min**: 3-record rolling mean of occupancy
- **target**: Occupancy at target timestamp (label)

## Installation

```bash
pip install -r backend/requirements.txt
```

## Usage

### Basic: Generate 7 days of history

```bash
python scripts/generate_ml_dataset.py --output /tmp/occupancy.csv
```

### With sampling (limit to 10000 records)

```bash
python scripts/generate_ml_dataset.py \
  --days-back 14 \
  --output /tmp/occupancy.csv \
  --sample-size 10000
```

### Custom FIWARE services

```bash
python scripts/generate_ml_dataset.py \
  --output /tmp/occupancy.csv \
  --fiware-service myservice \
  --fiware-service-path /myapp \
  --orion-url http://my-orion:1026 \
  --ql-url http://my-quantumleap:8668
```

### Handle missing values

- `--impute forward_fill` (default): Fill NaN with last valid value
- `--impute drop`: Remove rows with NaN
- `--impute mean`: Fill with column mean

```bash
python scripts/generate_ml_dataset.py \
  --output /tmp/occupancy.csv \
  --impute mean
```

## Output Files

1. **occupancy.csv**: Main dataset with all features and target
   - Columns: route, stop, route_encoded, stop_encoded, day, hour, prev_occupancy_lag1, prev_occupancy_rolling5min, occupancy, target, timestamp
   - ~5000-50000+ rows depending on --days-back and history availability

2. **occupancy_encoders.json**: LabelEncoder mappings
   - Required for later predictions (routes and stops encoding)

## Dataset Quality Checks

The pipeline validates:
- Occupancy ranges [0-100]
- No NaN in critical features
- Target distribution variance
- Record count statistics

## Example: End-to-End Workflow

```bash
# 1. Generate dataset (7 days)
python scripts/generate_ml_dataset.py --output /tmp/occupancy.csv

# 2. Inspect data
head -5 /tmp/occupancy.csv
wc -l /tmp/occupancy.csv

# 3. Train model (Issue 17 - train_model.py)
python scripts/train_model.py \
  --dataset /tmp/occupancy.csv \
  --model-output backend/models/occupancy_model.pkl
```

## Troubleshooting

**No data found**
- Check QuantumLeap is running and has VehicleState records
- Verify FIWARE-Service and FIWARE-ServicePath match seed data

**Encoding error with routes/stops**
- Ensure Orion returns GtfsRoute, GtfsTrip, GtfsStopTime metadata
- Check `--fiware-service` and `--fiware-service-path`

**Memory issues with large datasets**
- Use `--sample-size N` to limit output rows
- Reduce `--days-back` value

## Architecture Notes

- Uses **QuantumLeap** (time series API) for historical occupancy data
- Uses **Orion-LD** (context broker) for GTFS metadata
- Features are pre-normalized for RandomForest (no scaling needed)
- Encoders saved separately for inference pipeline

## Testing

```bash
pytest backend/tests/test_generate_ml_dataset.py -v
```

All 9 tests validate:
- Metadata loading
- Feature engineering
- Data serialization
- Sampling behavior
