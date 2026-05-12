import requests
import json
import time

BASE_URL = "http://localhost:8000/api"
USER_ID = "admin"
DISPLAY_NAME = "Administrador"

STOPS = [
    "urn:ngsi-ld:GtfsStop:s1",
    "urn:ngsi-ld:GtfsStop:s2",
    "urn:ngsi-ld:GtfsStop:s3",
    "urn:ngsi-ld:GtfsStop:s4",
    "urn:ngsi-ld:GtfsStop:s5",
    "urn:ngsi-ld:GtfsStop:s6"
]

def seed_gamification():
    print(f"Seeding gamification data for user: {USER_ID}")
    
    headers = {
        "X-User-Id": USER_ID,
        "Content-Type": "application/json"
    }
    
    # Record trips to all stops to unlock all zones
    for i, stop_id in enumerate(STOPS):
        payload = {
            "userId": USER_ID,
            "displayName": DISPLAY_NAME,
            "tripId": f"trip_seed_{i}",
            "stopId": stop_id,
            "pointsOverride": 100 # Give enough points to reach >500
        }
        
        try:
            response = requests.post(f"{BASE_URL}/user/record-trip", json=payload, headers=headers)
            if response.status_code == 200:
                profile = response.json()
                print(f"Successfully recorded trip to {stop_id}. Points: {profile.get('totalPoints')}")
            else:
                print(f"Failed to record trip to {stop_id}: {response.text}")
        except Exception as e:
            print(f"Error recording trip: {e}")
        
        time.sleep(0.5)

    # Check the final profile
    try:
        response = requests.get(f"{BASE_URL}/user/{USER_ID}/profile", headers=headers)
        if response.status_code == 200:
            profile = response.json()
            print("\nFinal Profile Stats:")
            print(f"Display Name: {profile.get('displayName')}")
            print(f"Total Points: {profile.get('totalPoints')}")
            print(f"Visited Stops: {len(profile.get('visitedStops', []))}")
            print(f"Achievements: {', '.join(profile.get('achievements', []))}")
        else:
            print(f"Failed to fetch profile: {response.text}")
    except Exception as e:
        print(f"Error fetching profile: {e}")

if __name__ == "__main__":
    seed_gamification()
