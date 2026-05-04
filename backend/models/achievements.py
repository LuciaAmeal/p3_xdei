"""
Gamification achievements model.

Defines predefined achievements for the gamification system.
Each achievement has a unique ID, display name, description, and required points.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

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


@dataclass
class Achievement:
    """
    Achievement entity for gamification.
    
    Represents a milestone or badge that users can unlock by visiting stops
    or accumulating points.
    """
    
    id: str  # e.g., "urn:ngsi-ld:Achievement:first-bus"
    display_name: str  # e.g., "First Bus"
    description: str  # e.g., "Take your first bus trip"
    required_points: int  # Minimum points needed to unlock
    icon: str = "🏅"  # Optional emoji or icon reference
    
    def to_ngsi_ld_dict(self) -> Dict[str, Any]:
        """Convert to NGSI-LD entity format."""
        return {
            "id": self.id,
            "type": "Achievement",
            "@context": NGSI_LD_CONTEXT,
            "displayName": _property(self.display_name),
            "description": _property(self.description),
            "requiredPoints": _property(self.required_points),
            "icon": _property(self.icon),
        }


# Predefined achievements
ACHIEVEMENTS = [
    Achievement(
        id=_entity_id("Achievement", "first-bus"),
        display_name="First Bus",
        description="Take your first bus trip",
        required_points=0,
        icon="🚌",
    ),
    Achievement(
        id=_entity_id("Achievement", "explorer"),
        display_name="Explorer",
        description="Visit 5 different stops",
        required_points=50,
        icon="🗺️",
    ),
    Achievement(
        id=_entity_id("Achievement", "vip-traveler"),
        display_name="VIP Traveler",
        description="Accumulate 200 points",
        required_points=200,
        icon="⭐",
    ),
    Achievement(
        id=_entity_id("Achievement", "commuter"),
        display_name="Commuter",
        description="Take 20 trips",
        required_points=100,
        icon="💼",
    ),
    Achievement(
        id=_entity_id("Achievement", "collector"),
        display_name="Collector",
        description="Unlock 5 achievements",
        required_points=300,
        icon="🏆",
    ),
]


def get_achievement_by_id(achievement_id: str) -> Achievement | None:
    """Get achievement by ID."""
    for achievement in ACHIEVEMENTS:
        if achievement.id == achievement_id:
            return achievement
    return None


def get_all_achievements() -> List[Achievement]:
    """Get all predefined achievements."""
    return ACHIEVEMENTS.copy()


def get_achievement_ids() -> List[str]:
    """Get all achievement IDs."""
    return [a.id for a in ACHIEVEMENTS]
