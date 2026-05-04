"""
Tests for NGSI-LD gamification entities (UserProfile, RedeemedDiscount, Achievement).

Tests that gamification entities conform to:
- NGSI-LD core structure (id, type, @context)
- Property/Relationship format
- Type alignment and valid ranges
- Relational integrity
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from models.achievements import Achievement, ACHIEVEMENTS, get_achievement_by_id
from models.user_profile import RedeemedDiscount, UserProfile
from validate_gtfs import validate_ngsi_ld_structure


# ============================================================================
# Achievement Entity Tests
# ============================================================================


class TestAchievementNGSILD:
    """Test Achievement entity structure."""
    
    def test_achievement_to_ngsi_ld_structure(self):
        """Achievement must have correct NGSI-LD structure."""
        achievement = ACHIEVEMENTS[0]
        entity = achievement.to_ngsi_ld_dict()
        
        assert "id" in entity
        assert "type" in entity
        assert "@context" in entity
        assert entity["type"] == "Achievement"
    
    def test_achievement_id_format(self):
        """Achievement ID must follow urn:ngsi-ld:Achievement:* format."""
        achievement = ACHIEVEMENTS[0]
        entity = achievement.to_ngsi_ld_dict()
        
        assert entity["id"].startswith("urn:ngsi-ld:Achievement:")
    
    def test_achievement_required_properties(self):
        """Achievement must have displayName, description, requiredPoints."""
        achievement = ACHIEVEMENTS[0]
        entity = achievement.to_ngsi_ld_dict()
        
        assert "displayName" in entity
        assert "description" in entity
        assert "requiredPoints" in entity
        assert "icon" in entity
    
    def test_achievement_properties_are_property_type(self):
        """All achievement properties must have Property type."""
        achievement = ACHIEVEMENTS[0]
        entity = achievement.to_ngsi_ld_dict()
        
        for key in ["displayName", "description", "requiredPoints", "icon"]:
            assert entity[key].get("type") == "Property"
            assert "value" in entity[key]
    
    def test_achievement_points_is_integer(self):
        """requiredPoints must be an integer."""
        achievement = ACHIEVEMENTS[0]
        entity = achievement.to_ngsi_ld_dict()
        
        required_points = entity["requiredPoints"]["value"]
        assert isinstance(required_points, int)
        assert required_points >= 0
    
    def test_all_achievements_pass_validation(self):
        """All predefined achievements must pass NGSI-LD validation."""
        entities = [a.to_ngsi_ld_dict() for a in ACHIEVEMENTS]
        errors = validate_ngsi_ld_structure(entities)
        
        assert errors == [], f"NGSI-LD validation errors:\n" + "\n".join(errors)
    
    def test_achievement_lookup(self):
        """Can retrieve achievement by ID."""
        achievement = ACHIEVEMENTS[0]
        looked_up = get_achievement_by_id(achievement.id)
        
        assert looked_up is not None
        assert looked_up.id == achievement.id
        assert looked_up.display_name == achievement.display_name
    
    def test_achievement_nonexistent_lookup(self):
        """Looking up nonexistent achievement returns None."""
        result = get_achievement_by_id("urn:ngsi-ld:Achievement:nonexistent")
        assert result is None


# ============================================================================
# UserProfile Entity Tests
# ============================================================================


class TestUserProfileNGSILD:
    """Test UserProfile entity structure and validation."""
    
    def test_userprofile_base_structure(self):
        """UserProfile must have id, type, @context."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
        )
        entity = user.to_ngsi_ld_dict()
        
        assert entity["id"] == "urn:ngsi-ld:UserProfile:user-1"
        assert entity["type"] == "UserProfile"
        assert entity["@context"] is not None
    
    def test_userprofile_required_properties(self):
        """UserProfile must have displayName and totalPoints."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            total_points=150,
        )
        entity = user.to_ngsi_ld_dict()
        
        assert "displayName" in entity
        assert "totalPoints" in entity
        assert "visitedStops" in entity
        assert "achievements" in entity
    
    def test_userprofile_properties_format(self):
        """UserProfile properties must be Property type."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            total_points=150,
        )
        entity = user.to_ngsi_ld_dict()
        
        assert entity["displayName"]["type"] == "Property"
        assert entity["totalPoints"]["type"] == "Property"
        assert entity["visitedStops"]["type"] == "Property"
        assert entity["achievements"]["type"] == "Property"
    
    def test_userprofile_points_range(self):
        """totalPoints should be non-negative integer."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            total_points=350,
        )
        entity = user.to_ngsi_ld_dict()
        
        points = entity["totalPoints"]["value"]
        assert isinstance(points, int)
        assert points >= 0
    
    def test_userprofile_optional_properties(self):
        """Optional properties (email, city) should be included when set."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            email="elena@example.com",
            city="Madrid",
        )
        entity = user.to_ngsi_ld_dict()
        
        assert "email" in entity
        assert "city" in entity
        assert entity["email"]["value"] == "elena@example.com"
        assert entity["city"]["value"] == "Madrid"
    
    def test_userprofile_visited_stops_format(self):
        """visitedStops must be a list of stop IDs."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            visited_stops=["urn:ngsi-ld:GtfsStop:s1", "urn:ngsi-ld:GtfsStop:s2"],
        )
        entity = user.to_ngsi_ld_dict()
        
        stops = entity["visitedStops"]["value"]
        assert isinstance(stops, list)
        assert len(stops) == 2
        assert all(s.startswith("urn:ngsi-ld:GtfsStop:") for s in stops)
    
    def test_userprofile_achievements_format(self):
        """achievements must be a list of achievement IDs."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            achievements=[ACHIEVEMENTS[0].id, ACHIEVEMENTS[1].id],
        )
        entity = user.to_ngsi_ld_dict()
        
        achievements = entity["achievements"]["value"]
        assert isinstance(achievements, list)
        assert len(achievements) == 2
        assert all(a.startswith("urn:ngsi-ld:Achievement:") for a in achievements)
    
    def test_userprofile_last_activity_timestamp(self):
        """lastActivityAt should be ISO 8601 when set."""
        now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            last_activity_at=now,
        )
        entity = user.to_ngsi_ld_dict()
        
        assert "lastActivityAt" in entity
        assert entity["lastActivityAt"]["value"] == now
    
    def test_userprofile_add_achievement(self):
        """add_achievement should add achievement if not present."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
        )
        
        achievement_id = ACHIEVEMENTS[0].id
        user.add_achievement(achievement_id)
        
        assert achievement_id in user.achievements
        assert len(user.achievements) == 1
        
        # Adding same achievement again should not duplicate
        user.add_achievement(achievement_id)
        assert len(user.achievements) == 1
    
    def test_userprofile_add_visited_stop(self):
        """add_visited_stop should add stop if not present."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
        )
        
        stop_id = "urn:ngsi-ld:GtfsStop:s1"
        user.add_visited_stop(stop_id)
        
        assert stop_id in user.visited_stops
        assert len(user.visited_stops) == 1
        
        # Adding same stop again should not duplicate
        user.add_visited_stop(stop_id)
        assert len(user.visited_stops) == 1
    
    def test_userprofile_add_points(self):
        """add_points should increase total_points."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            total_points=100,
        )
        
        user.add_points(50)
        assert user.total_points == 150
    
    def test_userprofile_pass_ngsi_ld_validation(self):
        """UserProfile must pass NGSI-LD validation."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            total_points=200,
            visited_stops=["urn:ngsi-ld:GtfsStop:s1"],
            achievements=[ACHIEVEMENTS[0].id],
        )
        
        entities = [user.to_ngsi_ld_dict()]
        errors = validate_ngsi_ld_structure(entities)
        
        assert errors == [], f"NGSI-LD validation errors:\n" + "\n".join(errors)


# ============================================================================
# RedeemedDiscount Entity Tests
# ============================================================================


class TestRedeemedDiscountNGSILD:
    """Test RedeemedDiscount entity structure."""
    
    def test_redeemed_discount_base_structure(self):
        """RedeemedDiscount must have id, type, @context."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        
        discount = RedeemedDiscount(
            id="urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
            discount_code="DISC-001",
            discount_value=25,
            redeemed_at=now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            valid_until=future.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            status="active",
        )
        entity = discount.to_ngsi_ld_dict()
        
        assert entity["id"] == "urn:ngsi-ld:RedeemedDiscount:user-1-discount-1"
        assert entity["type"] == "RedeemedDiscount"
        assert entity["@context"] is not None
    
    def test_redeemed_discount_required_properties(self):
        """RedeemedDiscount must have all required properties."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        
        discount = RedeemedDiscount(
            id="urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
            discount_code="DISC-001",
            discount_value=25,
            redeemed_at=now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            valid_until=future.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            status="active",
        )
        entity = discount.to_ngsi_ld_dict()
        
        assert "discountCode" in entity
        assert "discountValue" in entity
        assert "redeemedAt" in entity
        assert "validUntil" in entity
        assert "status" in entity
    
    def test_redeemed_discount_properties_format(self):
        """All properties must be Property type."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        
        discount = RedeemedDiscount(
            id="urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
            discount_code="DISC-001",
            discount_value=25,
            redeemed_at=now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            valid_until=future.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            status="active",
        )
        entity = discount.to_ngsi_ld_dict()
        
        for key in ["discountCode", "discountValue", "redeemedAt", "validUntil", "status"]:
            assert entity[key]["type"] == "Property"
            assert "value" in entity[key]
    
    def test_redeemed_discount_value_is_integer(self):
        """discountValue must be a positive integer."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        
        discount = RedeemedDiscount(
            id="urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
            discount_code="DISC-001",
            discount_value=50,
            redeemed_at=now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            valid_until=future.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            status="active",
        )
        entity = discount.to_ngsi_ld_dict()
        
        value = entity["discountValue"]["value"]
        assert isinstance(value, int)
        assert value > 0
    
    def test_redeemed_discount_status_valid_values(self):
        """status must be 'active' or 'expired'."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        
        for status_value in ["active", "expired"]:
            discount = RedeemedDiscount(
                id="urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
                discount_code="DISC-001",
                discount_value=25,
                redeemed_at=now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
                valid_until=future.isoformat(timespec='seconds').replace('+00:00', 'Z'),
                status=status_value,
            )
            entity = discount.to_ngsi_ld_dict()
            
            assert entity["status"]["value"] in ["active", "expired"]
    
    def test_redeemed_discount_belongs_to_user_relationship(self):
        """belongsToUser should be a Relationship when set."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        
        discount = RedeemedDiscount(
            id="urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
            discount_code="DISC-001",
            discount_value=25,
            redeemed_at=now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            valid_until=future.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            status="active",
            belongs_to_user="urn:ngsi-ld:UserProfile:user-1",
        )
        entity = discount.to_ngsi_ld_dict()
        
        assert "belongsToUser" in entity
        assert entity["belongsToUser"]["type"] == "Relationship"
        assert entity["belongsToUser"]["object"] == "urn:ngsi-ld:UserProfile:user-1"
    
    def test_redeemed_discount_valid_until_after_redeemed_at(self):
        """validUntil should be after redeemedAt."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        
        discount = RedeemedDiscount(
            id="urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
            discount_code="DISC-001",
            discount_value=25,
            redeemed_at=now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            valid_until=future.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            status="active",
        )
        entity = discount.to_ngsi_ld_dict()
        
        redeemed_at = entity["redeemedAt"]["value"]
        valid_until = entity["validUntil"]["value"]
        
        assert redeemed_at < valid_until
    
    def test_redeemed_discount_pass_ngsi_ld_validation(self):
        """RedeemedDiscount must pass NGSI-LD validation."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        
        discount = RedeemedDiscount(
            id="urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
            discount_code="DISC-001",
            discount_value=25,
            redeemed_at=now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            valid_until=future.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            status="active",
            belongs_to_user="urn:ngsi-ld:UserProfile:user-1",
        )
        
        entities = [discount.to_ngsi_ld_dict()]
        errors = validate_ngsi_ld_structure(entities)
        
        assert errors == [], f"NGSI-LD validation errors:\n" + "\n".join(errors)


# ============================================================================
# Relationship Tests
# ============================================================================


class TestGamificationRelationships:
    """Test relationships between gamification entities."""
    
    def test_userprofile_references_achievements(self):
        """UserProfile should reference valid Achievement IDs."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            achievements=[ACHIEVEMENTS[0].id, ACHIEVEMENTS[1].id],
        )
        
        for achievement_id in user.achievements:
            assert get_achievement_by_id(achievement_id) is not None
    
    def test_userprofile_references_stops(self):
        """UserProfile should reference valid GtfsStop IDs."""
        user = UserProfile(
            id="urn:ngsi-ld:UserProfile:user-1",
            display_name="Elena García",
            visited_stops=["urn:ngsi-ld:GtfsStop:s1", "urn:ngsi-ld:GtfsStop:s2"],
        )
        
        for stop_id in user.visited_stops:
            assert stop_id.startswith("urn:ngsi-ld:GtfsStop:")
    
    def test_redeemed_discount_belongs_to_user(self):
        """RedeemedDiscount should reference a UserProfile."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        
        discount = RedeemedDiscount(
            id="urn:ngsi-ld:RedeemedDiscount:user-1-discount-1",
            discount_code="DISC-001",
            discount_value=25,
            redeemed_at=now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            valid_until=future.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            status="active",
            belongs_to_user="urn:ngsi-ld:UserProfile:user-1",
        )
        
        entity = discount.to_ngsi_ld_dict()
        assert entity["belongsToUser"]["object"].startswith("urn:ngsi-ld:UserProfile:")
