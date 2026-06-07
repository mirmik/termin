"""Component editor extensions for tcgui inspector context tools."""

from __future__ import annotations

from typing import Callable, Protocol

from tcbase import log
from tcgui.widgets.widget import Widget


class ComponentEditorExtension(Protocol):
    """Editor-side context extension for one selected component."""

    def attach(self, editor, entity, component_ref) -> None:
        ...

    def detach(self) -> None:
        ...

    def build_panel(self) -> Widget | None:
        ...

    def build_left_panel(self) -> Widget | None:
        ...


ComponentEditorExtensionFactory = Callable[[], ComponentEditorExtension]

_factories: dict[str, ComponentEditorExtensionFactory] = {}


def register_component_editor_extension(
    component_type_name: str,
    factory: ComponentEditorExtensionFactory,
) -> None:
    if not component_type_name:
        log.error("[ComponentEditorExtension] empty component type name")
        return
    _factories[component_type_name] = factory


def create_component_editor_extension(component_type_name: str) -> ComponentEditorExtension | None:
    factory = _factories.get(component_type_name)
    if factory is None:
        return None
    try:
        return factory()
    except Exception as e:
        log.error(
            "[ComponentEditorExtension] failed to create extension for "
            f"'{component_type_name}': {e}"
        )
        return None


__all__ = [
    "ComponentEditorExtension",
    "create_component_editor_extension",
    "register_component_editor_extension",
]
