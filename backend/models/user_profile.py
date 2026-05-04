"""
Gamification user profile and redeemed discount models.

Defines NGSI-LD entities for UserProfile and RedeemedDiscount.
Includes helper methods to serialize to NGSI-LD JSON-LD format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)

# Standard NGSI-LD context for gamification entities
NGSI_LD_CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"


def _entity_id(entity_type: str, raw_id: str) -> str:
    """Create NGSI-LD entity ID from type and raw ID."""
    return f"urn:ngsi-ld:{entity_type}:{raw_id}"


def _property(value: Any) -> Dict[str, Any]:
    """Create NGSI-LD Property."""
    return {"type": "Property", "value": value}


def _relationship(target_id: str) -> Dict[str, Any]:
    """Create NGSI-LD Relationship."""
    return {"type": "Relationship", "object": target_id}


@dataclass
class RedeemedDiscount:
    """
    RedeemedDiscount entity.
    
    Records a redeemed discount by a user: discount code, value, redemption date,
    expiration date, and status.
    """
    
    id: str  # e.g., "urn:ngsi-ld:RedeemedDiscount:user-1-discount-1"
    discount_code: str  # e.g., "DISC-001"
    discount_value: int  # Points value of discount (e.g., 25)
    redeemed_at: str  # ISO 8601 timestamp when redeemed
    valid_until: str  # ISO 8601 timestamp when expires
    status: str  # "active" or "expired"
    belongs_to_user: str = ""  # User profile ID (Relationship)
    
    def to_ngsi_ld_dict(self) -> Dict[str, Any]:
        """Convert to NGSI-LD entity format."""
        entity: Dict[str, Any] = {
            "id": self.id,
            "type": "RedeemedDiscount",
            "@context": NGSI_LD_CONTEXT,
            "discountCode": _property(self.discount_code),
            "discountValue": _property(self.discount_value),
            "redeemedAt": _property(self.redeemed_at),
            "validUntil": _property(self.valid_until),
            "status": _property(self.status),
        }
        
        if self.belongs_to_user:
            entity["belongsToUser"] = _relationship(self.belongs_to_user)
        
        return entity


@dataclass
class UserProfile:
    """
    UserProfile entity.
    
    Stores user gamification progress: accumulated points, visited stops,
    unlocked achievements, last activity timestamp, and redeemed discounts.
    """
    
    id: str  # e.g., "urn:ngsi-ld:UserProfile:user-1"
    display_name: str  # e.g., "Elena García"
    total_points: int = 0  # Accumulated points
    visited_stops: List[str] = field(default_factory=list)  # GtfsStop IDs visited
    achievements: List[str] = field(default_factory=list)  # Achievement IDs unlocked
    last_activity_at: str = ""  # ISO 8601 timestamp
    redeemed_discounts: List[str] = field(default_factory=list)  # RedeemedDiscount IDs
    email: Optional[str] = None  # Optional user email
    city: Optional[str] = None  # Optional city/location
    
    def to_ngsi_ld_dict(self) -> Dict[str, Any]:
        """Convert to NGSI-LD entity format."""
        entity: Dict[str, Any] = {
            "id": self.id,
            "type": "UserProfile",
            "@context": NGSI_LD_CONTEXT,
            "displayName": _property(self.display_name),
            "totalPoints": _property(self.total_points),
            "visitedStops": _property(self.visited_stops),
            "achievements": _property(self.achievements),
        }
        
        if self.last_activity_at:
            entity["lastActivityAt"] = _property(self.last_activity_at)
        
        if self.redeemed_discounts:
            entity["redeemedDiscounts"] = _property(self.redeemed_discounts)
        
        if self.email:
            entity["email"] = _property(self.email)
        
        if self.city:
            entity["city"] = _property(self.city)
        
        return entity
    
    def add_achievement(self, achievement_id: str) -> None:
        """Add an achievement if not already present."""
        if achievement_id not in self.achievements:
            self.achievements.append(achievement_id)
            logger.debug(f"Added achievement {achievement_id} to {self.id}")
    
    def add_visited_stop(self, stop_id: str) -> None:
        """Add a visited stop if not already present."""
        if stop_id not in self.visited_stops:
            self.visited_stops.append(stop_id)
            logger.debug(f"Added visited stop {stop_id} to {self.id}")
    
    def add_redeemed_discount(self, discount_id: str) -> None:
        """Add a redeemed discount."""
        self.redeemed_discounts.append(discount_id)
        logger.debug(f"Added redeemed discount {discount_id} to {self.id}")
    
    def add_points(self, points: int) -> None:
        """Add points to user total."""
        self.total_points += points
        logger.debug(f"Added {points} points to {self.id}, total now {self.total_points}")
