"""Native component-extension registry, host context and default composition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging

from termin.editor_core.component_editor_extension import (
    ComponentEditorExtension,
    ComponentExtensionPresentation,
    register_component_editor_extension,
)
from termin.gui_native import TcDocument


_logger = logging.getLogger(__name__)
NativeComponentExtensionProjector = Callable[
    [ComponentEditorExtension, TcDocument],
    ComponentExtensionPresentation,
]


@dataclass
class NativeComponentExtensionContext:
    engine: object
    document: TcDocument
    request_render: Callable[[], None]
    resource_manager: object
    viewport_geometry: object | None = None
    _click_interceptors: list[Callable[[object], bool]] = field(default_factory=list)
    _pointer_handlers: list[Callable[[object], bool]] = field(default_factory=list)
    _key_handlers: list[Callable[[object], bool]] = field(default_factory=list)
    _overlay_drawers: list[Callable[[], None]] = field(default_factory=list)
    _active_tools: int = 0
    on_viewport_tool_state_changed: Callable[[int], None] | None = None

    def add_viewport_click_interceptor(self, callback: Callable[[object], bool]) -> None:
        self._click_interceptors.append(callback)

    def remove_viewport_click_interceptor(self, callback: Callable[[object], bool]) -> None:
        self._remove_callback(self._click_interceptors, callback, "click interceptor")

    def add_viewport_key_handler(self, callback: Callable[[object], bool]) -> None:
        self._key_handlers.append(callback)

    def remove_viewport_key_handler(self, callback: Callable[[object], bool]) -> None:
        self._remove_callback(self._key_handlers, callback, "key handler")

    def add_viewport_pointer_handler(self, callback: Callable[[object], bool]) -> None:
        self._pointer_handlers.append(callback)

    def remove_viewport_pointer_handler(self, callback: Callable[[object], bool]) -> None:
        self._remove_callback(self._pointer_handlers, callback, "pointer handler")

    def add_viewport_overlay_drawer(self, callback: Callable[[], None]) -> None:
        self._overlay_drawers.append(callback)

    def remove_viewport_overlay_drawer(self, callback: Callable[[], None]) -> None:
        self._remove_callback(self._overlay_drawers, callback, "overlay drawer")

    def begin_viewport_tool(self) -> None:
        self._active_tools += 1
        self._notify_viewport_tool_state_changed()

    def end_viewport_tool(self) -> None:
        if self._active_tools <= 0:
            _logger.error("Native component extension viewport tool lifetime underflow")
            raise RuntimeError("viewport tool lifetime underflow")
        self._active_tools -= 1
        self._notify_viewport_tool_state_changed()

    def request_viewport_update(self) -> None:
        self.request_render()

    def world_ray_from_viewport_point(self, x: float, y: float):
        geometry = self._require_viewport_geometry()
        return geometry.world_ray_from_viewport_point(x, y)

    def project_world_point_to_viewport(self, point):
        geometry = self._require_viewport_geometry()
        return geometry.project_world_point_to_viewport(point)

    def world_point_on_entity_local_oxy_plane(self, x: float, y: float, entity):
        geometry = self._require_viewport_geometry()
        return geometry.world_point_on_entity_local_oxy_plane(x, y, entity)

    def dispatch_viewport_click(self, event: object) -> bool:
        return any(callback(event) for callback in reversed(tuple(self._click_interceptors)))

    def dispatch_viewport_key(self, event: object) -> bool:
        return any(callback(event) for callback in reversed(tuple(self._key_handlers)))

    def dispatch_viewport_pointer(self, event: object) -> bool:
        return any(callback(event) for callback in reversed(tuple(self._pointer_handlers)))

    def draw_viewport_overlays(self) -> bool:
        for callback in tuple(self._overlay_drawers):
            callback()
        return bool(self._overlay_drawers)

    @property
    def active_viewport_tools(self) -> int:
        return self._active_tools

    def _notify_viewport_tool_state_changed(self) -> None:
        if self.on_viewport_tool_state_changed is not None:
            self.on_viewport_tool_state_changed(self._active_tools)

    def _require_viewport_geometry(self):
        if self.viewport_geometry is None:
            _logger.error("Native component extension viewport geometry is not connected")
            raise RuntimeError("native viewport geometry is not connected")
        return self.viewport_geometry

    @staticmethod
    def _remove_callback(callbacks: list, callback: Callable, kind: str) -> None:
        try:
            callbacks.remove(callback)
        except ValueError:
            _logger.exception("Native component extension %s was not registered", kind)
            raise


class NativeComponentExtensionProjectorRegistry:
    def __init__(self, document: TcDocument) -> None:
        self._document = document
        self._projectors: dict[str, NativeComponentExtensionProjector] = {}

    def register(self, type_name: str, projector: NativeComponentExtensionProjector) -> None:
        if not type_name:
            _logger.error("Cannot register native extension projector with an empty type name")
            raise ValueError("component type name must not be empty")
        self._projectors[type_name] = projector

    def project(
        self,
        extension: ComponentEditorExtension,
        type_name: str,
    ) -> ComponentExtensionPresentation:
        projector = self._projectors.get(type_name)
        if projector is None:
            _logger.error("No native component extension projector registered for '%s'", type_name)
            raise KeyError(type_name)
        return projector(extension, self._document)


def register_native_component_extensions(
    registry: NativeComponentExtensionProjectorRegistry,
) -> None:
    from termin.editor_core.foliage_layer_editor_extension import FoliageLayerEditorExtension
    from termin.editor_core.procedural_mesh_editor_extension import (
        ProceduralMeshExtensionModel,
    )
    from termin.editor_native.foliage_extension import project_native_foliage_extension
    from termin.editor_native.procedural_mesh_extension import (
        project_native_procedural_mesh_extension,
    )

    register_component_editor_extension(
        "FoliageLayerComponent",
        FoliageLayerEditorExtension,
    )
    registry.register("FoliageLayerComponent", project_native_foliage_extension)
    register_component_editor_extension(
        "ProceduralMeshComponent",
        ProceduralMeshExtensionModel,
    )
    registry.register(
        "ProceduralMeshComponent",
        project_native_procedural_mesh_extension,
    )


__all__ = [
    "NativeComponentExtensionContext",
    "NativeComponentExtensionProjector",
    "NativeComponentExtensionProjectorRegistry",
    "register_native_component_extensions",
]
