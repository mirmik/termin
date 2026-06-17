"""Python component class registry."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from tcbase import log
from termin.scene.class_scanner import scan_paths

if TYPE_CHECKING:
    from termin.scene import Component


class ComponentClassRegistry:
    """Registry of Python component classes by class name."""

    def __init__(self) -> None:
        self.classes: dict[str, type["Component"]] = {}

    def register(self, name: str, cls: type["Component"]) -> None:
        self.classes[name] = cls

    def get(self, name: str) -> type["Component"] | None:
        return self.classes.get(name)

    def list_names(self) -> list[str]:
        return sorted(self.classes.keys())

    def register_builtins(self, specs: list[tuple[str, str]]) -> list[str]:
        """Register component classes from (module, class) specs."""
        registered: list[str] = []
        for module_name, class_name in specs:
            if class_name in self.classes:
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.classes[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                log.warning(f"Failed to register component {class_name} from {module_name}: {e}")

        return registered

    def scan(self, paths: list[str]) -> list[str]:
        """Scan directories, modules or files and register component classes."""
        return scan_paths(paths, self.classes, "_dynamic_components_")
