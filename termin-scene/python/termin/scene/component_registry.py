"""Python component class registry."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from tcbase import log

if TYPE_CHECKING:
    from termin.scene import Component


class ComponentClassRegistry:
    """Registry of Python component classes by class name."""

    def __init__(self) -> None:
        self.classes: dict[str, type["Component"]] = {}

    def register(self, name: str, cls: type["Component"]) -> None:
        self.classes[name] = cls
        try:
            from termin_modules.module_context import record_app_component
        except ModuleNotFoundError as exc:
            if exc.name not in ("termin_modules", "termin_modules.module_context"):
                log.error("Failed to load module ownership context", exc_info=True)
            return
        except Exception:
            log.error("Failed to load module ownership context", exc_info=True)
            return

        try:
            record_app_component(name)
        except Exception:
            log.error(f"Failed to record module ownership for component class {name}", exc_info=True)

    def unregister(self, name: str) -> None:
        if name in self.classes:
            del self.classes[name]

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
                cls = getattr(module, class_name)
                self.register(class_name, cls)
                registered.append(class_name)
            except AttributeError:
                log.error(
                    f"Builtin component module {module_name} does not expose {class_name}",
                    exc_info=True,
                )
            except Exception as e:
                log.warning(f"Failed to register component {class_name} from {module_name}: {e}")

        return registered
