"""
ChronoSquad Core - time-reversible game engine.

Core concepts:
- ChronoSphere: collection of timelines, manages current timeline and time flow
- Timeline: container for objects, can move forward/backward in time
- ObjectOfTimeline: game object with position and event cards
- ObjectTime: object's personal time (broken time + modifiers)
- EventCard/EventLine: events that trigger at specific time steps
- Animatronic: smooth movement interpolation
- CommandBuffer: manages actor commands (MovingCommand, etc.)
"""

from termin.geombase import Vec3, Quat, Pose3

from .event_line import EventCard, EventLine, TimeDirection
from .timeline import Timeline, GAME_FREQUENCY
from .object_of_timeline import ObjectOfTimeline, AnimatronicAnimationTask
from .animatronic import (
    AnimationType,
    Animatronic,
    StaticAnimatronic,
    LinearMoveAnimatronic,
    CubicMoveAnimatronic,
    WaypointAnimatronic,
    MovingAnimatronic,
    ANIMATION_DURATIONS,
    get_animation_duration,
)
from .object_time import ObjectTime, TimeModifier, TimeFreeze, TimeHaste
from .chronosphere import ChronoSphere
from .commands.actor_command import ActorCommand
from .command_buffer import CommandBuffer
from .commands.moving_command import MovingCommand, WalkingType
from .unit_path import UnitPath, UnitPathPoint, UnitPathPointType, BracedCoordinates
from .ability.ability import Ability, AbilityList, CooldownRecord, CooldownList
from .ability.blink_ability import BlinkAbility

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
    "AnimatronicAnimationTask",
    "Vec3",
    "Quat",
    "Pose3",
    # Object time
    "ObjectTime",
    "TimeModifier",
    "TimeFreeze",
    "TimeHaste",
    # Animatronics
    "AnimationType",
    "Animatronic",
    "StaticAnimatronic",
    "LinearMoveAnimatronic",
    "CubicMoveAnimatronic",
    "WaypointAnimatronic",
    "MovingAnimatronic",
    "ANIMATION_DURATIONS",
    "get_animation_duration",
    # Command system
    "ActorCommand",
    "CommandBuffer",
    "MovingCommand",
    "WalkingType",
    # Pathfinding
    "UnitPath",
    "UnitPathPoint",
    "UnitPathPointType",
    "BracedCoordinates",
    # Ability system
    "Ability",
    "AbilityList",
    "CooldownRecord",
    "CooldownList",
    "BlinkAbility",
]
