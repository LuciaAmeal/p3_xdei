# Gamification Seed Script

## Overview

`seed_gamification.py` generates realistic test data for the gamification system and seeds it into Orion-LD. Creates three types of NGSI-LD entities:

- **Achievement** — Predefined badges/milestones (First Bus, Explorer, VIP Traveler, etc.)
- **UserProfile** — User gamification progress (points, visited stops, achievements, last activity)
- **RedeemedDiscount** — Discount codes redeemed by users (code, value, status, expiration)

All entities conform to NGSI-LD format with proper `@context`, Properties, and Relationships.

## Features

### Generated Data

**Users** (8-10 by default, configurable):
- Realistic Spanish names and surnames
- Email addresses (user_1@example.com, etc.)
- City/location from Spanish cities
- 50-500 random points
- 2-4 achievements per user
- 3-8 visited stops per user
- Recent activity timestamp

**Achievements** (5 predefined):
- First Bus (0 points to unlock)
- Explorer (50 points)
- VIP Traveler (200 points)
- Commuter (100 points)
- Collector (300 points)

**Redeemed Discounts** (60% of users get 2-3 each):
- Generated discount codes (DISC-001, DISC-002, etc.)
- 10-50 point values
- Redeemed within last 30 days
- Valid for next 30 days
- Status: active or expired

## Installation

### Prerequisites

```bash
# Python 3.10+
python --version

# Backend dependencies
pip install -r backend/requirements.txt
```

### Verify Installation

```bash
python scripts/seed_gamification.py --help
```

## Usage

### Basic Usage (8 users, dry-run preview)

```bash
python scripts/seed_gamification.py --dry-run
```

Output: JSON preview of all entities without uploading to Orion.

### Generate 10 Users and Upload to Orion

```bash
python scripts/seed_gamification.py --user-count 10
```

### Custom Orion URL and FIWARE Service

```bash
python scripts/seed_gamification.py \
  --user-count 5 \
  --orion-url http://my-orion:1026 \
  --fiware-service myservice \
  --fiware-service-path /myapp
```

### CLI Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--user-count` | int | 8 | Number of users to generate (1-100) |
| `--orion-url` | str | http://localhost:1026 | Orion-LD base URL |
| `--fiware-service` | str | (from config) | FIWARE-Service header |
| `--fiware-service-path` | str | (from config) | FIWARE-ServicePath header |
| `--dry-run` | flag | False | Print JSON without uploading to Orion |
| `--help` | flag | - | Show help message |

## Example Workflow

### 1. Check if Orion is running

```bash
curl -i http://localhost:1026/version
```

### 2. Preview seed data (no upload)

```bash
python scripts/seed_gamification.py --user-count 3 --dry-run
```

Output:
```
================================================================================
GAMIFICATION SEED DATA (NGSI-LD JSON-LD Format)
================================================================================

Achievements: 5
Users: 3
Discounts: 5
Total entities: 13

Example Achievement:
{
  "id": "urn:ngsi-ld:Achievement:first-bus",
  "type": "Achievement",
  "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
  "displayName": {
    "type": "Property",
    "value": "First Bus"
  },
  ...
}

Example UserProfile:
{
  "id": "urn:ngsi-ld:UserProfile:user-1",
  "type": "UserProfile",
  "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
  "displayName": {
    "type": "Property",
    "value": "Elena García"
  },
  "totalPoints": {
    "type": "Property",
    "value": 275
  },
  ...
}

Example RedeemedDiscount:
{
  "id": "urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
  "type": "RedeemedDiscount",
  "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
  "discountCode": {
    "type": "Property",
    "value": "DISC-001"
  },
  ...
}

================================================================================
```

### 3. Seed data (with upload)

```bash
python scripts/seed_gamification.py --user-count 8
```

Output:
```
================================================================================
SEED RESULTS
================================================================================
Achievements created: 5
Users created: 8
Discounts created: 14
Errors: 0
================================================================================

Seed complete: 27 entities created
```

### 4. Verify in Orion

```bash
# List all UserProfile entities
curl http://localhost:1026/ngsi-ld/v1/entities?type=UserProfile \
  -H "Accept: application/ld+json"

# Get a specific user
curl http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:UserProfile:user-1 \
  -H "Accept: application/ld+json"

# List all RedeemedDiscount entities
curl http://localhost:1026/ngsi-ld/v1/entities?type=RedeemedDiscount \
  -H "Accept: application/ld+json"
```

## Output Files

No files are created locally. All data is sent directly to Orion-LD.

### Logging

Enable debug logging to see detailed creation steps:

```bash
LOG_LEVEL=DEBUG python scripts/seed_gamification.py --user-count 5
```

## Entity Structure (NGSI-LD)

### Achievement

```json
{
  "id": "urn:ngsi-ld:Achievement:first-bus",
  "type": "Achievement",
  "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
  "displayName": {"type": "Property", "value": "First Bus"},
  "description": {"type": "Property", "value": "Take your first bus trip"},
  "requiredPoints": {"type": "Property", "value": 0},
  "icon": {"type": "Property", "value": "🚌"}
}
```

### UserProfile

```json
{
  "id": "urn:ngsi-ld:UserProfile:user-1",
  "type": "UserProfile",
  "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
  "displayName": {"type": "Property", "value": "Elena García"},
  "totalPoints": {"type": "Property", "value": 275},
  "visitedStops": {"type": "Property", "value": ["urn:ngsi-ld:GtfsStop:s1", ...]},
  "achievements": {"type": "Property", "value": ["urn:ngsi-ld:Achievement:first-bus", ...]},
  "lastActivityAt": {"type": "Property", "value": "2026-05-02T14:30:15Z"},
  "redeemedDiscounts": {"type": "Property", "value": ["urn:ngsi-ld:RedeemedDiscount:...", ...]},
  "email": {"type": "Property", "value": "user_1@example.com"},
  "city": {"type": "Property", "value": "Madrid"}
}
```

### RedeemedDiscount

```json
{
  "id": "urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
  "type": "RedeemedDiscount",
  "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
  "discountCode": {"type": "Property", "value": "DISC-001"},
  "discountValue": {"type": "Property", "value": 25},
  "redeemedAt": {"type": "Property", "value": "2026-04-28T10:15:30Z"},
  "validUntil": {"type": "Property", "value": "2026-05-28T10:15:30Z"},
  "status": {"type": "Property", "value": "active"},
  "belongsToUser": {"type": "Relationship", "object": "urn:ngsi-ld:UserProfile:user-1"}
}
```

## Troubleshooting

### "Connection refused" or "Connection error"

**Cause:** Orion-LD is not running or unreachable.

**Solution:**
```bash
# Verify Orion is running
curl http://localhost:1026/version

# If not running, start it
docker-compose up orion

# Or specify custom URL
python scripts/seed_gamification.py --orion-url http://my-host:1026
```

### "FIWARE-Service mismatch"

**Cause:** FIWARE-Service or FIWARE-ServicePath headers don't match Orion configuration.

**Solution:**
```bash
# Check your docker-compose FIWARE_SERVICE setting
docker-compose config | grep FIWARE

# Use matching headers
python scripts/seed_gamification.py \
  --fiware-service my_service \
  --fiware-service-path /my_path
```

### "409 Conflict" errors

**Cause:** Entities already exist in Orion (duplicate seed run).

**Solution:**
```bash
# Option 1: Clean up existing data in Orion first
curl -X DELETE http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:UserProfile:user-1

# Option 2: Use different user counts or dry-run first
python scripts/seed_gamification.py --user-count 5 --dry-run
```

### No data appears in Orion after seeding

**Cause:** Entities were created but not visible (permission/service path issue).

**Solution:**
1. Verify entity was created:
   ```bash
   curl http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:UserProfile:user-1 \
     -H "Fiware-Service: $(docker-compose config | grep FIWARE_SERVICE=)" \
     -H "Fiware-ServicePath: $(docker-compose config | grep FIWARE_SERVICE_PATH=)"
   ```

2. Check logs:
   ```bash
   docker-compose logs orion | grep -i "user-1\|error"
   ```

## Testing

Run unit tests for gamification entities:

```bash
pytest backend/tests/test_ngsi_ld_gamification.py -v
```

Expected output:
```
backend/tests/test_ngsi_ld_gamification.py::TestAchievementNGSILD::test_achievement_to_ngsi_ld_structure PASSED
backend/tests/test_ngsi_ld_gamification.py::TestAchievementNGSILD::test_achievement_id_format PASSED
...
backend/tests/test_ngsi_ld_gamification.py::TestGamificationRelationships::test_redeemed_discount_belongs_to_user PASSED

===================== 30 passed in 0.75s =====================
```

## NGSI-LD Validation

All generated entities conform to NGSI-LD specification:
- ✅ Required fields: `id`, `type`, `@context`
- ✅ Properties: `{"type": "Property", "value": ...}`
- ✅ Relationships: `{"type": "Relationship", "object": "..."}`
- ✅ Entity ID format: `urn:ngsi-ld:Type:id`
- ✅ Timestamps: ISO 8601 with Z suffix (UTC)

## Architecture Notes

- **NGSI-LD Context**: Standard ETSI context `https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld`
- **OrionClient**: Uses retry logic with exponential backoff (max 3 attempts)
- **Dataclasses**: `Achievement`, `UserProfile`, `RedeemedDiscount` with `.to_ngsi_ld_dict()` serialization
- **Randomization**: User names, cities, points, stop counts, discount values are randomized
- **No persistence**: All data lives in Orion-LD; script is stateless

## Related Issues

- **Issue 23**: Next phase — implement endpoints (`GET /api/user/{id}/profile`, `POST /api/user/record-trip`, `POST /api/user/redeem`)
- **Issue 24**: Implement UI for gamification panel (achievements, points, redeem button)
- **Issue 27**: JWT authentication for user endpoints

## Future Enhancements

1. **Bulk operations**: Batch entity creation instead of individual POST requests
2. **Relationship linking**: Validate that referenced GtfsStop entities exist before creating
3. **Custom achievement definitions**: Load achievements from YAML config
4. **Interactive mode**: Prompt user for parameters instead of CLI args
5. **Backup/restore**: Export and reimport gamification state from Orion
