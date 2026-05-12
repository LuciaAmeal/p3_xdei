import requests
import random
import time
from datetime import datetime, timedelta, timezone

CRATE_URL = "http://crate:4200/_sql"

def run_query(sql, args=None, is_bulk=False):
    payload = {"stmt": sql}
    if args:
        if is_bulk:
            payload["bulk_args"] = args
        else:
            payload["args"] = args
    response = requests.post(CRATE_URL, json=payload)
    if response.status_code != 200:
        print(f"Query failed: {response.text}")
    response.raise_for_status()
    return response.json()

def seed_data():
    table_name = '"doc"."mtsmartgondor_gardens_vehiclestate"'
    print(f"Ensuring table {table_name} is fresh...")
    # Drop and recreate for schema updates during development
    drop_table_sql = f"DROP TABLE IF EXISTS {table_name}"
    try:
        run_query(drop_table_sql)
    except:
        pass

    # Table creation SQL (mirroring QuantumLeap's structure)
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        "entityid" STRING,
        "entitytype" STRING,
        "time_index" TIMESTAMP WITH TIME ZONE,
        "fiwareservicepath" STRING,
        "destination" STRING,
        "delayseconds" INTEGER,
        "occupancy" INTEGER,
        "speedkmh" REAL,
        "heading" REAL,
        "status" STRING,
        "currentposition" GEO_POINT
    )
    """
    try:
        run_query(create_table_sql)
    except Exception as e:
        print(f"Note: Table might already exist or creation failed: {e}")

    print("Generating synthetic data for the last 7 days...")
    vehicles = [f"urn:ngsi-ld:VehicleState:bus_{i}" for i in range(1, 11)]
    # Assign destinations to vehicles
    dest_map = {v: ("Universidad" if i % 2 == 0 else "Hospitales") for i, v in enumerate(vehicles)}
    now = datetime.now(timezone.utc)
    
    records = []
    for day in range(7):
        for hour in range(24):
            for minute in range(0, 60, 15): # Every 15 minutes (less density for 7 days)
                ts = now - timedelta(days=day, hours=hour, minutes=minute)
                ts_ms = int(ts.timestamp() * 1000)
            
            for v_id in vehicles:
                destination = dest_map[v_id]
                # Variation in occupancy based on destination and time
                # More occupancy for University in morning, etc. (simplified)
                base_occ = 60 if destination == "Universidad" and 7 <= ts.hour <= 10 else 20
                delay = random.randint(-60, 300)
                occ = min(100, max(0, base_occ + random.randint(-15, 40)))
                speed = random.uniform(20.0, 50.0)
                
                # Random location around A Coruña
                lon = -8.4115 + random.uniform(-0.01, 0.01)
                lat = 43.3623 + random.uniform(-0.01, 0.01)
                
                records.append([
                    v_id, "VehicleState", ts_ms, "/gardens",
                    destination, delay, occ, speed, random.uniform(0, 360),
                    "in_transit", [lon, lat]
                ])
                
                if len(records) >= 100:
                    insert_sql = f"INSERT INTO {table_name} (entityid, entitytype, time_index, fiwareservicepath, destination, delayseconds, occupancy, speedkmh, heading, status, currentposition) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    run_query(insert_sql, records, is_bulk=True)
                    records = []
    
    if records:
        insert_sql = f"INSERT INTO {table_name} (entityid, entitytype, time_index, fiwareservicepath, destination, delayseconds, occupancy, speedkmh, heading, status, currentposition) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        run_query(insert_sql, records, is_bulk=True)

    print("Seeding completed successfully.")

if __name__ == "__main__":
    # Wait a bit for Crate to be ready
    time.sleep(5)
    seed_data()
