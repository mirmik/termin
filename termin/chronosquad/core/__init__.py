"""
ChronoSquad Core - time-reversible game engine.

Core concepts:
- ChronoSphere: collection of timelines, manages current timeline and time flow
- Timeline: container for objects, can move forward/backward in time
- ObjectOfTimeline: game object with position and event cards
- ObjectTime: object's personal time (broken time + modifiers)
- EventCard/EventLine: events that trigger at specific time steps
- Animatronic: smooth movement interpolation
"""

from termin.geombase import Vec3, Quat, Pose3

from .event_line import EventCard, EventLine, TimeDirection
from .timeline import Timeline, GAME_FREQUENCY
from .object_of_timeline import ObjectOfTimeline
from .animatronic import (
    Animatronic,
    StaticAnimatronic,
    LinearMoveAnimatronic,
    CubicMoveAnimatronic,
    WaypointAnimatronic,
)
from .object_time import ObjectTime, TimeModifier, TimeFreeze, TimeHaste
from .chronosphere import ChronoSphere

__all__ = [
    # ChronoSphere
    "ChronoSphere",
    # Event system
    "EventCard",
    "EventLine",
    "TimeDirection",
    # Timeline
    "Timeline",
    "GAME_FREQUENCY",
    # Objects
    "ObjectOfTimeline",
    "Vec3",
    "Quat",
    "Pose3",
    # Object time
    "ObjectTime",
    "TimeModifier",
    "TimeFreeze",
    "TimeHaste",
    # Animatronics
    "Animatronic",
    "StaticAnimatronic",
    "LinearMoveAnimatronic",
    "CubicMoveAnimatronic",
    "WaypointAnimatronic",
]
