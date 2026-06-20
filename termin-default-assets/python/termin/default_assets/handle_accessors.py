"""Handle selector accessors for default Termin resources."""

from __future__ import annotations

from typing import Any, Callable, Optional


class HandleAccessors:
    """
    Unified accessors for handle-based resource types.

    Provides a consistent interface for listing, resolving and reverse-looking
    resources by name/handle for generic selector widgets.
    """

    def __init__(
        self,
        list_names: Callable[[], list[str]],
        get_by_name: Callable[[str], Any],
        find_name: Callable[[Any], Optional[str]],
        find_uuid: Callable[[str], Optional[str]],
        create_item: Callable[[], tuple[str, Optional[str]] | None] | None = None,
        allow_none: bool = True,
    ) -> None:
        self.list_names = list_names
        self.get_by_name = get_by_name
        self.find_name = find_name
        self.find_uuid = find_uuid
        self.create_item = create_item
        self.allow_none = allow_none

    def list_items(self) -> list[tuple[str, Optional[str]]]:
        """Return list of ``(name, uuid)`` tuples for all items."""
        result = []
        for name in self.list_names():
            uuid = self.find_uuid(name)
            result.append((name, uuid))
        return result


__all__ = ["HandleAccessors"]
