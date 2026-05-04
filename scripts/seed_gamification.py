#!/usr/bin/env python3
"""
Gamification data seed script.

Generates realistic test data for UserProfile and RedeemedDiscount entities
and seeds them into Orion-LD. Includes predefined achievements.

Usage:
    python seed_gamification.py --user-count 8 --orion-url http://localhost:1026
    python seed_gamification.py --user-count 5 --dry-run  # Preview JSON without uploading
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from clients.orion import OrionClient, OrionClientError
from config import settings
from models.achievements import ACHIEVEMENTS, Achievement
from models.user_profile import RedeemedDiscount, UserProfile
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Realistic Spanish names and cities
FIRST_NAMES = [
    "Elena", "Carlos", "María", "José", "Ana", "Juan",
    "Rosa", "Pedro", "Carmen", "Miguel", "Isabel", "Diego"
]

LAST_NAMES = [
    "García", "López", "Rodríguez", "Martínez", "Pérez", "Gómez",
    "Sánchez", "Fernández", "Torres", "Ramírez", "Ruiz", "Moreno"
]

SPANISH_CITIES = [
    "Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao",
    "Zaragoza", "Alicante", "Córdoba", "Murcia", "Palma"
]


class GamificationSeedError(Exception):
    """Base exception for seed errors."""


class GamificationSeeder:
    """Generates and seeds gamification test data into Orion-LD."""
    
    def __init__(
        self,
        orion_client: OrionClient,
        user_count: int = 8,
        dry_run: bool = False,
    ):
        """
        Initialize seeder.
        
        Args:
            orion_client: Orion-LD client for entity creation
            user_count: Number of users to generate
            dry_run: If True, print JSON without sending to Orion
        """
        self.orion_client = orion_client
        self.user_count = max(1, min(user_count, 100))  # Clamp to 1-100
        self.dry_run = dry_run
        self.generated_users: List[UserProfile] = []
        self.generated_discounts: List[RedeemedDiscount] = []
        self.generated_achievements: List[Achievement] = []
    
    def generate_users(self) -> List[UserProfile]:
        """Generate realistic user profiles."""
        logger.info(f"Generating {self.user_count} user profiles...")
        
        users: List[UserProfile] = []
        for i in range(self.user_count):
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            display_name = f"{first_name} {last_name}"
            city = random.choice(SPANISH_CITIES)
            email = f"user_{i+1}@example.com"
            
            user = UserProfile(
                id=f"urn:ngsi-ld:UserProfile:user-{i+1}",
                display_name=display_name,
                email=email,
                city=city,
                total_points=random.randint(50, 500),
                last_activity_at=self._random_recent_timestamp(),
            )
            
            # Add random achievements (2-4 per user)
            num_achievements = random.randint(2, 4)
            sampled_achievements = random.sample(ACHIEVEMENTS, min(num_achievements, len(ACHIEVEMENTS)))
            user.achievements = [a.id for a in sampled_achievements]
            
            # Add random visited stops (3-8 per user)
            num_stops = random.randint(3, 8)
            user.visited_stops = [
                f"urn:ngsi-ld:GtfsStop:s{j+1}"
                for j in range(num_stops)
            ]
            
            users.append(user)
        
        self.generated_users = users
        logger.info(f"Generated {len(users)} users with achievements and stops")
        return users
    
    def generate_discounts(self) -> List[RedeemedDiscount]:
        """Generate redeemed discounts for selected users."""
        logger.info("Generating redeemed discounts...")
        
        discounts: List[RedeemedDiscount] = []
        
        # 60% of users get 2-3 discounts
        eligible_users = random.sample(
            self.generated_users,
            max(1, int(len(self.generated_users) * 0.6))
        )
        
        discount_counter = 1
        for user in eligible_users:
            num_discounts = random.randint(2, 3)
            for j in range(num_discounts):
                discount = RedeemedDiscount(
                    id=f"urn:ngsi-ld:RedeemedDiscount:user-{user.id.split('-')[-1]}-discount-{j+1}",
                    discount_code=f"DISC-{discount_counter:03d}",
                    discount_value=random.randint(10, 50),
                    redeemed_at=self._random_past_timestamp(days=30),
                    valid_until=self._random_future_timestamp(days=30),
                    status=random.choice(["active", "expired"]),
                    belongs_to_user=user.id,
                )
                discounts.append(discount)
                discount_counter += 1
                # Add discount ID to user's redeemed_discounts
                user.add_redeemed_discount(discount.id)
        
        self.generated_discounts = discounts
        logger.info(f"Generated {len(discounts)} redeemed discounts")
        return discounts
    
    def prepare_seed_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Prepare all seed data as NGSI-LD entities."""
        logger.info("Preparing seed data as NGSI-LD entities...")
        
        entities = {
            "achievements": [],
            "users": [],
            "discounts": [],
        }
        
        # Add achievements
        for achievement in ACHIEVEMENTS:
            entities["achievements"].append(achievement.to_ngsi_ld_dict())
        
        # Add users
        for user in self.generated_users:
            entities["users"].append(user.to_ngsi_ld_dict())
        
        # Add discounts
        for discount in self.generated_discounts:
            entities["discounts"].append(discount.to_ngsi_ld_dict())
        
        return entities
    
    def seed_to_orion(self) -> Dict[str, Any]:
        """Upload seed data to Orion-LD."""
        if self.dry_run:
            logger.info("DRY RUN: Would create entities but not uploading to Orion")
        else:
            logger.info("Uploading entities to Orion-LD...")
        
        result = {
            "achievements_created": 0,
            "users_created": 0,
            "discounts_created": 0,
            "errors": [],
        }
        
        # Create achievements
        for achievement in ACHIEVEMENTS:
            if self.dry_run:
                logger.debug(f"[DRY RUN] Would create Achievement: {achievement.id}")
                result["achievements_created"] += 1
            else:
                try:
                    entity_dict = achievement.to_ngsi_ld_dict()
                    self.orion_client.create_entity(entity_dict)
                    result["achievements_created"] += 1
                    logger.debug(f"Created Achievement: {achievement.id}")
                except OrionClientError as e:
                    error_msg = f"Failed to create Achievement {achievement.id}: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
        
        # Create users
        for user in self.generated_users:
            if self.dry_run:
                logger.debug(f"[DRY RUN] Would create UserProfile: {user.id}")
                result["users_created"] += 1
            else:
                try:
                    entity_dict = user.to_ngsi_ld_dict()
                    self.orion_client.create_entity(entity_dict)
                    result["users_created"] += 1
                    logger.debug(f"Created UserProfile: {user.id}")
                except OrionClientError as e:
                    error_msg = f"Failed to create UserProfile {user.id}: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
        
        # Create discounts
        for discount in self.generated_discounts:
            if self.dry_run:
                logger.debug(f"[DRY RUN] Would create RedeemedDiscount: {discount.id}")
                result["discounts_created"] += 1
            else:
                try:
                    entity_dict = discount.to_ngsi_ld_dict()
                    self.orion_client.create_entity(entity_dict)
                    result["discounts_created"] += 1
                    logger.debug(f"Created RedeemedDiscount: {discount.id}")
                except OrionClientError as e:
                    error_msg = f"Failed to create RedeemedDiscount {discount.id}: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
        
        return result
    
    def print_json_preview(self, seed_data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Print JSON preview of all entities."""
        print("\n" + "=" * 80)
        print("GAMIFICATION SEED DATA (NGSI-LD JSON-LD Format)")
        print("=" * 80 + "\n")
        
        # Print summary
        print(f"Achievements: {len(seed_data['achievements'])}")
        print(f"Users: {len(seed_data['users'])}")
        print(f"Discounts: {len(seed_data['discounts'])}")
        print(f"Total entities: {sum(len(v) for v in seed_data.values())}\n")
        
        # Print first user and discount as examples
        if seed_data['achievements']:
            print("Example Achievement:")
            print(json.dumps(seed_data['achievements'][0], indent=2))
            print()
        
        if seed_data['users']:
            print("Example UserProfile:")
            print(json.dumps(seed_data['users'][0], indent=2))
            print()
        
        if seed_data['discounts']:
            print("Example RedeemedDiscount:")
            print(json.dumps(seed_data['discounts'][0], indent=2))
            print()
        
        print("=" * 80 + "\n")
    
    @staticmethod
    def _random_recent_timestamp() -> str:
        """Generate a recent timestamp (within last 7 days)."""
        days_ago = random.randint(0, 7)
        dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return dt.isoformat(timespec='seconds').replace('+00:00', 'Z')
    
    @staticmethod
    def _random_past_timestamp(days: int = 30) -> str:
        """Generate a timestamp in the past."""
        days_ago = random.randint(1, days)
        dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return dt.isoformat(timespec='seconds').replace('+00:00', 'Z')
    
    @staticmethod
    def _random_future_timestamp(days: int = 30) -> str:
        """Generate a timestamp in the future."""
        days_ahead = random.randint(1, days)
        dt = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        return dt.isoformat(timespec='seconds').replace('+00:00', 'Z')


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed Orion-LD with gamification test data (UserProfile, RedeemedDiscount, Achievement)"
    )
    parser.add_argument(
        "--user-count",
        type=int,
        default=8,
        help="Number of users to generate (default: 8)"
    )
    parser.add_argument(
        "--orion-url",
        default=settings.orion.url,
        help=f"Orion-LD base URL (default: {settings.orion.url})"
    )
    parser.add_argument(
        "--fiware-service",
        default=settings.fiware.service,
        help=f"FIWARE-Service header (default: {settings.fiware.service})"
    )
    parser.add_argument(
        "--fiware-service-path",
        default=settings.fiware.servicepath,
        help=f"FIWARE-ServicePath header (default: {settings.fiware.servicepath})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON without uploading to Orion"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize Orion client
        fiware_headers = {
            "Fiware-Service": args.fiware_service,
            "Fiware-ServicePath": args.fiware_service_path,
        }
        orion_client = OrionClient(
            base_url=args.orion_url,
            fiware_headers=fiware_headers,
        )
        
        # Initialize seeder
        seeder = GamificationSeeder(
            orion_client=orion_client,
            user_count=args.user_count,
            dry_run=args.dry_run,
        )
        
        # Generate data
        logger.info(f"Starting gamification seed process (dry_run={args.dry_run})...")
        seeder.generate_users()
        seeder.generate_discounts()
        seed_data = seeder.prepare_seed_data()
        
        # Print preview
        seeder.print_json_preview(seed_data)
        
        # Upload to Orion
        result = seeder.seed_to_orion()
        
        # Print results
        print("\n" + "=" * 80)
        print("SEED RESULTS")
        print("=" * 80)
        print(f"Achievements created: {result['achievements_created']}")
        print(f"Users created: {result['users_created']}")
        print(f"Discounts created: {result['discounts_created']}")
        print(f"Errors: {len(result['errors'])}")
        
        if result['errors']:
            print("\nErrors:")
            for error in result['errors']:
                print(f"  - {error}")
        
        print("=" * 80 + "\n")
        
        total_created = (
            result['achievements_created'] +
            result['users_created'] +
            result['discounts_created']
        )
        logger.info(f"Seed complete: {total_created} entities created")
        
        return 0 if len(result['errors']) == 0 else 1
    
    except GamificationSeedError as e:
        logger.error(f"Seed failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
