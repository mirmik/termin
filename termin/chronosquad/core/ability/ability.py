"""
Ability system for actors.

Matches original C# Ability/AbilityList implementation:
- Ability: base class with cooldown, use methods
- CooldownRecord: tracks cooldown state with start/finish steps
- AbilityList: manages abilities and cooldowns for an actor
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from termin.chronosquad.core.timeline import GAME_FREQUENCY

if TYPE_CHECKING:
    from termin.chronosquad.core.object_of_timeline import ObjectOfTimeline
    from termin.chronosquad.core.timeline import Timeline


@dataclass
class CooldownRecord:
    """
    Record of an active cooldown.

    Matches original C# CooldownRecord : BasicMultipleAction.
    """
    start_step: int
    finish_step: int
    ability_type: type

    def is_active_at(self, step: int) -> bool:
        """Check if cooldown is active at given step."""
        return self.start_step <= step <= self.finish_step

    def hash_code(self) -> int:
        """Hash for comparison."""
        return hash((self.ability_type.__name__, self.start_step, self.finish_step))


class CooldownList:
    """
    List of cooldown records with time-based promotion.

    Tracks which cooldowns are currently active.
    """

    def __init__(self):
        self._records: list[CooldownRecord] = []
        self._active: list[CooldownRecord] = []
        self._current_step: int = 0

    def add(self, record: CooldownRecord) -> None:
        """Add a cooldown record."""
        self._records.append(record)
        # Check if immediately active
        if record.is_active_at(self._current_step):
            self._active.append(record)

    def promote(self, step: int) -> None:
        """
        Promote to new step, updating active cooldowns.

        Matches original MultipleActionList.Promote behavior.
        """
        self._current_step = step
        self._active = [r for r in self._records if r.is_active_at(step)]

    def active_states(self) -> list[CooldownRecord]:
        """Return currently active cooldown records."""
        return self._active

    def has_active_cooldown(self, ability_type: type) -> bool:
        """Check if ability type has active cooldown."""
        for record in self._active:
            if record.ability_type == ability_type:
                return True
        return False

    def displayable_cooldown(self, ability_type: type, local_step: int) -> float:
        """
        Get remaining cooldown as 0.0-1.0 value.

        Returns 1.0 if no cooldown, 0.0 at start, approaching 1.0 as cooldown ends.
        Matches original AbilityList.DisplayableCooldown().
        """
        for record in self._active:
            if record.ability_type == ability_type:
                length = record.finish_step - record.start_step
                if length <= 0:
                    return 1.0
                current = local_step - record.start_step
                return 1.0 - (current / length)
        return 1.0

    def drop_to_current_state(self) -> None:
        """Remove cooldowns that haven't started yet."""
        self._records = [r for r in self._records if r.start_step <= self._current_step]
        self._active = [r for r in self._records if r.is_active_at(self._current_step)]

    def copy(self) -> CooldownList:
        """Create a copy of this cooldown list."""
        new_list = CooldownList()
        new_list._current_step = self._current_step
        new_list._records = [
            CooldownRecord(r.start_step, r.finish_step, r.ability_type)
            for r in self._records
        ]
        new_list._active = [r for r in new_list._records if r.is_active_at(self._current_step)]
        return new_list


class Ability:
    """
    Base class for abilities.

    Matches original C# Ability class:
    - Has cooldown (in steps)
    - Can be used on self, object, or environment
    - Checks and applies cooldowns via AbilityList
    """

    def __init__(self, cooldown: float = 3.0):
        """
        Initialize ability with cooldown.

        Args:
            cooldown: Cooldown time in seconds (default 3.0)
        """
        self._cooldown: int = int(cooldown * GAME_FREQUENCY)

    @property
    def cooldown(self) -> int:
        """Cooldown in steps."""
        return self._cooldown

    @property
    def cooldown_time(self) -> float:
        """Cooldown in seconds."""
        return self._cooldown / GAME_FREQUENCY

    def can_use_ability(self, target: ObjectOfTimeline) -> bool:
        """
        Check if ability can be used on target.

        Override in subclasses for specific checks.
        """
        return True

    def can_use(self, timeline: Timeline, ability_list: AbilityList) -> bool:
        """
        Check if ability can be used (not on cooldown).

        Matches original Ability.CanUse().
        """
        return not ability_list.has_active_cooldown(type(self))

    def _apply_cooldown(self, ability_list: AbilityList) -> None:
        """Apply cooldown after ability use."""
        if self._cooldown > 0:
            local_step = ability_list.actor.local_step
            ability_list.add_cooldown(
                type(self),
                local_step,
                local_step + self._cooldown
            )

    def use_self_impl(self, timeline: Timeline, ability_list: AbilityList) -> None:
        """
        Implementation of self-targeted ability.

        Override in subclasses.
        """
        pass

    def use_on_object_impl(
        self,
        target: ObjectOfTimeline,
        timeline: Timeline,
        ability_list: AbilityList,
    ) -> None:
        """
        Implementation of object-targeted ability.

        Override in subclasses.
        """
        pass

    def use_on_environment_impl(
        self,
        target_position,  # ReferencedPoint
        timeline: Timeline,
        ability_list: AbilityList,
        private_parameters=None,
    ) -> None:
        """
        Implementation of environment-targeted ability.

        Override in subclasses.
        """
        pass

    def use_self(
        self,
        timeline: Timeline,
        ability_list: AbilityList,
        ignore_cooldown: bool = False,
    ) -> None:
        """
        Use ability on self.

        Matches original Ability.UseSelf().
        """
        if not ignore_cooldown and not self.can_use(timeline, ability_list):
            return
        self.use_self_impl(timeline, ability_list)
        self._apply_cooldown(ability_list)

    def use_on_object(
        self,
        target: ObjectOfTimeline,
        timeline: Timeline,
        ability_list: AbilityList,
        ignore_cooldown: bool = False,
    ) -> None:
        """
        Use ability on target object.

        Matches original Ability.UseOnObject().
        """
        if not ignore_cooldown and not self.can_use(timeline, ability_list):
            return
        self.use_on_object_impl(target, timeline, ability_list)
        self._apply_cooldown(ability_list)

    def use_on_environment(
        self,
        target_position,  # ReferencedPoint
        timeline: Timeline,
        ability_list: AbilityList,
        private_parameters=None,
        ignore_cooldown: bool = False,
    ) -> None:
        """
        Use ability on environment position.

        Matches original Ability.UseOnEnvironment().
        """
        if not ignore_cooldown and not self.can_use(timeline, ability_list):
            return
        self.use_on_environment_impl(target_position, timeline, ability_list, private_parameters)
        self._apply_cooldown(ability_list)

    def set_parameter(self, name: str, value: float) -> None:
        """Set ability parameter. Override in subclasses."""
        pass

    def hook_install(self, owner: ObjectOfTimeline) -> None:
        """Called when ability is added to owner. Override in subclasses."""
        pass

    def info(self) -> str:
        """Debug info."""
        return f"{type(self).__name__}(cooldown={self.cooldown_time:.1f}s)"


T = TypeVar("T", bound=Ability)


class AbilityList:
    """
    List of abilities for an actor.

    Matches original C# AbilityList:
    - Manages list of Ability instances
    - Tracks cooldowns via CooldownList
    - Provides methods to get, use abilities
    """

    def __init__(self, owner: ObjectOfTimeline):
        self._owner = owner
        self._abilities: list[Ability] = []
        self._cooldowns: CooldownList = CooldownList()
        self._prevent_ability_add: bool = False

    @property
    def actor(self) -> ObjectOfTimeline:
        """Get owner actor. Matches original Actor() method."""
        return self._owner

    @property
    def object(self) -> ObjectOfTimeline:
        """Get owner object. Matches original Object() method."""
        return self._owner

    def actor_name(self) -> str:
        """Get actor name. Matches original ActorName()."""
        return self._owner.name

    def add_cooldown(self, ability_type: type, start: int, finish: int) -> None:
        """
        Add a cooldown record.

        Matches original IAbilityListPanel.AddCooldown().
        """
        self._cooldowns.add(CooldownRecord(start, finish, ability_type))

    def has_active_cooldown(self, ability_type: type) -> bool:
        """Check if ability type has active cooldown."""
        return self._cooldowns.has_active_cooldown(ability_type)

    def displayable_cooldown(self, ability_type: type) -> float:
        """Get remaining cooldown as 0.0-1.0 value."""
        return self._cooldowns.displayable_cooldown(ability_type, self._owner.local_step)

    def get_cooldown_percent(self, ability_type: type) -> float:
        """
        Get cooldown percent (0-100).

        Matches original AbilityList.GetCooldownPercent().
        """
        if not self.contains(ability_type):
            return 100.0
        value = self.displayable_cooldown(ability_type) * 100.0
        return min(value, 100.0)

    def promote_cooldowns(self) -> None:
        """
        Update cooldowns to current step.

        Matches original AbilityList.PromoteCooldowns().
        """
        self._cooldowns.promote(self._owner.local_step)

    def drop_to_current_state(self, step: int) -> None:
        """
        Drop future cooldowns.

        Matches original AbilityList.DropToCurrentState().
        """
        self._cooldowns.drop_to_current_state()

    def _add_ability(self, ability: Ability) -> None:
        """Internal add without prevent check."""
        self._abilities.append(ability)
        ability.hook_install(self._owner)

    def add_or_change(self, ability: Ability) -> Ability:
        """
        Add ability or replace existing of same type.

        Matches original AbilityList.AddOrChange().
        """
        ability_type = type(ability)
        idx = self._index_of_ability(ability_type)
        if idx >= 0:
            self._abilities[idx] = ability
            return ability
        else:
            if not self._prevent_ability_add:
                self._add_ability(ability)
            return ability

    def _index_of_ability(self, ability_type: type) -> int:
        """Find index of ability by type."""
        for i, ability in enumerate(self._abilities):
            if type(ability) == ability_type:
                return i
        return -1

    def contains(self, ability_type: type) -> bool:
        """Check if ability of given type exists."""
        return self._index_of_ability(ability_type) >= 0

    def get_ability(self, ability_type: type[T]) -> T | None:
        """
        Get ability by type.

        Matches original AbilityList.GetAbility<T>().
        """
        for ability in self._abilities:
            if isinstance(ability, ability_type):
                return ability
        return None

    def can_use(self, ability_type: type[T], timeline: Timeline) -> bool:
        """
        Check if ability can be used (exists and not on cooldown).

        Matches original AbilityList.CanUse<T>().
        """
        ability = self.get_ability(ability_type)
        if ability is None:
            return False
        return ability.can_use(timeline, self)

    def copy(self, new_owner: ObjectOfTimeline) -> AbilityList:
        """
        Create a copy for new owner.

        Matches original AbilityList.Copy().
        """
        new_list = AbilityList(new_owner)
        new_list._cooldowns = self._cooldowns.copy()
        # Copy abilities (not deep copy - abilities are typically stateless)
        for ability in self._abilities:
            new_list._add_ability(ability)
        new_list._prevent_ability_add = True
        return new_list

    def info(self) -> str:
        """Debug info."""
        lines = [f"AbilityList for {self._owner.name}:"]
        for ability in self._abilities:
            cooldown = self.displayable_cooldown(type(ability))
            lines.append(f"  {ability.info()} (cooldown: {cooldown:.1%})")
        return "\n".join(lines)
