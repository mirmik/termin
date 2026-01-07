from typing import TYPE_CHECKING 
from termin.geombase import Vec3
from termin.chronosquad.core.event_line import EventCard
from termin.chronosquad.core.timeline import Timeline

class BlindEffect(EventCard[Timeline]):
    """
    Visual effect that blinds the actor for a duration.

    Matches original BlindEffect class:
    - On start, applies blind effect to actor
    - On end, removes blind effect from actor
    """

    def __init__(self, start_step:int, finish_step:int, position: Vec3):
        """
        Initialize BlindEffect.

        Args:
            start_step: Timeline step to start the effect
            finish_step: Timeline step to end the effect
            position: Position of the effect in world coordinates
        """
        super().__init__(start_step, finish_step)
        self._position = position

        