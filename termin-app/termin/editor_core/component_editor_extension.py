"""Toolkit-neutral component editor extension registry and session lifetime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Protocol


_logger = logging.getLogger(__name__)


class ComponentEditorExtension(Protocol):
    """Editor-side context extension for one selected component."""

    def attach(self, editor: object, entity: object, component_ref: object) -> None: ...

    def detach(self) -> None: ...


ComponentEditorExtensionFactory = Callable[[], ComponentEditorExtension]


@dataclass(frozen=True)
class ComponentExtensionPresentation:
    """Opaque frontend-owned projections produced outside the core lifecycle."""

    right_panel: object | None = None
    left_panel: object | None = None


ComponentExtensionPresenter = Callable[
    [ComponentEditorExtension, str],
    ComponentExtensionPresentation,
]
ComponentExtensionPresentationHandler = Callable[
    [str, ComponentExtensionPresentation],
    None,
]


class ComponentEditorExtensionRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ComponentEditorExtensionFactory] = {}

    def register(
        self,
        component_type_name: str,
        factory: ComponentEditorExtensionFactory,
    ) -> None:
        if not component_type_name:
            _logger.error("Cannot register component editor extension with an empty type name")
            raise ValueError("component type name must not be empty")
        self._factories[component_type_name] = factory

    def create(self, component_type_name: str) -> ComponentEditorExtension | None:
        factory = self._factories.get(component_type_name)
        if factory is None:
            return None
        try:
            return factory()
        except Exception:
            _logger.exception(
                "Failed to create component editor extension for '%s'",
                component_type_name,
            )
            raise


_registry = ComponentEditorExtensionRegistry()


def register_component_editor_extension(
    component_type_name: str,
    factory: ComponentEditorExtensionFactory,
) -> None:
    _registry.register(component_type_name, factory)


def create_component_editor_extension(component_type_name: str) -> ComponentEditorExtension | None:
    return _registry.create(component_type_name)


class ComponentEditorExtensionSession:
    """Own exactly one attached extension and its frontend presentation."""

    def __init__(
        self,
        *,
        editor: Callable[[], object],
        presenter: ComponentExtensionPresenter,
        present: ComponentExtensionPresentationHandler,
        clear_presentation: Callable[[], None],
        registry: ComponentEditorExtensionRegistry | None = None,
    ) -> None:
        self._editor = editor
        self._presenter = presenter
        self._present = present
        self._clear_presentation = clear_presentation
        self._registry = registry or _registry
        self._active_extension: ComponentEditorExtension | None = None
        self._active_type_name = ""

    @property
    def active_type_name(self) -> str:
        return self._active_type_name

    def select_component(self, entity: object, component_ref: object, type_name: str) -> None:
        self.clear()
        extension = self._registry.create(type_name)
        if extension is None:
            return
        try:
            extension.attach(self._editor(), entity, component_ref)
            presentation = self._presenter(extension, type_name)
            self._present(type_name, presentation)
        except Exception:
            _logger.exception("Failed to attach component editor extension for '%s'", type_name)
            try:
                extension.detach()
            except Exception:
                _logger.exception(
                    "Failed to detach component editor extension after attach failure for '%s'",
                    type_name,
                )
            self._clear_presentation()
            raise
        self._active_extension = extension
        self._active_type_name = type_name

    def clear(self) -> None:
        extension = self._active_extension
        type_name = self._active_type_name
        self._active_extension = None
        self._active_type_name = ""
        detach_error: Exception | None = None
        if extension is not None:
            try:
                extension.detach()
            except Exception as error:
                detach_error = error
                _logger.exception("Failed to detach component editor extension for '%s'", type_name)
        self._clear_presentation()
        if detach_error is not None:
            raise detach_error


__all__ = [
    "ComponentEditorExtension",
    "ComponentEditorExtensionFactory",
    "ComponentEditorExtensionRegistry",
    "ComponentEditorExtensionSession",
    "ComponentExtensionPresentation",
    "create_component_editor_extension",
    "register_component_editor_extension",
]
