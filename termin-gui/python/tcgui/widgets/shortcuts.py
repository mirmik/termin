"""Global keyboard shortcut registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tcbase import Key, Mods


@dataclass(frozen=True, slots=True)
class ShortcutKey:
    """Immutable key+modifiers identifier for a shortcut."""
    key: Key
    mods: int

    def __hash__(self) -> int:
        return hash((self.key, self.mods))

    def __eq__(self, other) -> bool:
        if not isinstance(other, ShortcutKey):
            return NotImplemented
        return self.key == other.key and self.mods == other.mods


class ShortcutRegistry:
    """Registry mapping key combinations to callbacks.

    Usage::

        registry = ShortcutRegistry()
        registry.add(Key.S, Mods.CTRL.value, save_file)
        if registry.try_dispatch(key, mods):
            return True
    """

    def __init__(self):
        self._shortcuts: dict[ShortcutKey, Callable[[], None]] = {}

    def add(self, key: Key, mods: int, callback: Callable[[], None]) -> None:
        """Register a global shortcut. Overwrites existing binding."""
        self._shortcuts[ShortcutKey(key, mods)] = callback

    def remove(self, key: Key, mods: int) -> bool:
        """Unregister a shortcut. Returns True if it existed."""
        sk = ShortcutKey(key, mods)
        if sk in self._shortcuts:
            del self._shortcuts[sk]
            return True
        return False

    def try_dispatch(self, key: Key, mods: int) -> bool:
        """If a shortcut matches, call its callback and return True."""
        cb = self._shortcuts.get(ShortcutKey(key, mods))
        if cb is not None:
            cb()
            return True
        return False

    @staticmethod
    def parse_shortcut_string(text: str) -> tuple[Key, int]:
        """Parse a human-readable string like ``'Ctrl+Shift+S'`` into (Key, mods).

        Supported modifiers: Ctrl, Shift, Alt.
        The last token is the key name.
        """
        parts = [p.strip() for p in text.split("+")]
        mods = 0
        for mod_str in parts[:-1]:
            low = mod_str.lower()
            if low == "ctrl":
                mods |= Mods.CTRL.value
            elif low == "shift":
                mods |= Mods.SHIFT.value
            elif low == "alt":
                mods |= Mods.ALT.value

        key_name = parts[-1]
        # Single letter: A-Z
        if len(key_name) == 1 and key_name.isalpha():
            return Key[key_name.upper()], mods
        # Named keys
        return Key[key_name.upper()], mods
