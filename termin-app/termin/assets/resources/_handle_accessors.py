"""HandleAccessors class for unified resource access."""

from typing import Any, Callable, List, Optional, Tuple


class HandleAccessors:
    """
    Unified accessors for handle-based resource types.

    Provides a consistent interface for listing, getting, and finding
    resources by name/handle for use in generic selector widgets.
    """

    def __init__(
        self,
        list_names: Callable[[], list[str]],
        get_by_name: Callable[[str], Any],
        find_name: Callable[[Any], Optional[str]],
        find_uuid: Callable[[str], Optional[str]],
        allow_none: bool = True,
    ):
        self.list_names = list_names
        self.get_by_name = get_by_name
        self.find_name = find_name
        self.find_uuid = find_uuid
        self.allow_none = allow_none

    def list_items(self) -> List[Tuple[str, Optional[str]]]:
        """Return list of (name, uuid) tuples for all items."""
        result = []
        for name in self.list_names():
            uuid = self.find_uuid(name)
            result.append((name, uuid))
        return result
