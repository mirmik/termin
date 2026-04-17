"""Platform-specific windowing glue."""

from termin.visualization.platform.input_manager import DisplayInputRouter
from termin.visualization.platform.backends import (
    Action,
    BackendWindow,
    Key,
    MouseButton,
    WindowBackend,
)

__all__ = [
    "DisplayInputRouter",
    "Action",
    "BackendWindow",
    "Key",
    "MouseButton",
    "WindowBackend",
]
