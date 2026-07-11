"""Toolkit-neutral inspector models for displays, viewports, and render targets."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
import logging
from typing import Any

from termin.editor_core.material_texture_sources import MaterialTextureSourceCatalog
from termin.editor_core.signal import Signal


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InspectorChoice:
    label: str
    value: Any


@dataclass(frozen=True)
class DisplayInspectorSnapshot:
    display: Any = None
    name: str = ""
    surface_type: str = "—"
    size: tuple[int, int] | None = None
    viewport_count: int = 0
    editor_only: bool = False
    debug_identity: str = "—"

    @property
    def has_display(self) -> bool:
        return self.display is not None


class DisplayInspectorController:
    def __init__(self, *, changed: Callable[[], None] | None = None) -> None:
        self._display = None
        self._changed = changed
        self.snapshot_changed = Signal()
        self._snapshot = DisplayInspectorSnapshot()

    @property
    def snapshot(self) -> DisplayInspectorSnapshot:
        return self._snapshot

    def set_target(self, display) -> DisplayInspectorSnapshot:
        self._display = display
        return self.refresh()

    def refresh(self) -> DisplayInspectorSnapshot:
        display = self._display
        if display is None:
            return self._publish(DisplayInspectorSnapshot())
        try:
            size = tuple(int(value) for value in display.get_size())
        except Exception:
            _logger.exception("Display inspector failed to query display size")
            size = None
        surface_type = "—" if display.surface is None else type(display.surface).__name__
        return self._publish(
            DisplayInspectorSnapshot(
                display=display,
                name=display.name or "",
                surface_type=surface_type,
                size=size,
                viewport_count=len(display.viewports),
                editor_only=bool(display.editor_only),
                debug_identity=f"0x{int(display.tc_display_ptr):X}",
            )
        )

    def set_name(self, value: str) -> DisplayInspectorSnapshot:
        display = self._require_target()
        normalized = value.strip()
        if not normalized:
            _logger.error("Display inspector rejected an empty name")
            raise ValueError("display name cannot be empty")
        display.name = normalized
        return self._commit()

    def set_editor_only(self, value: bool) -> DisplayInspectorSnapshot:
        self._require_target().editor_only = bool(value)
        return self._commit()

    def _require_target(self):
        if self._display is None:
            _logger.error("Display inspector has no target")
            raise RuntimeError("display inspector has no target")
        return self._display

    def _commit(self) -> DisplayInspectorSnapshot:
        if self._changed is not None:
            self._changed()
        return self.refresh()

    def _publish(self, snapshot: DisplayInspectorSnapshot) -> DisplayInspectorSnapshot:
        self._snapshot = snapshot
        self.snapshot_changed.emit(snapshot)
        return snapshot


@dataclass(frozen=True)
class ViewportInspectorSnapshot:
    viewport: Any = None
    name: str = ""
    enabled: bool = False
    displays: tuple[InspectorChoice, ...] = ()
    display_index: int = -1
    display_editable: bool = False
    scenes: tuple[InspectorChoice, ...] = ()
    scene_index: int = -1
    input_modes: tuple[str, ...] = ("none", "simple", "editor")
    input_mode_index: int = 0
    block_input_in_editor: bool = False
    rect: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    depth: int = 0
    render_targets: tuple[InspectorChoice, ...] = ()
    render_target_index: int = 0

    @property
    def has_viewport(self) -> bool:
        return self.viewport is not None


class ViewportInspectorController:
    def __init__(
        self,
        *,
        displays: Callable[[Any], Iterable[Any]],
        scenes: Callable[[], Iterable[Any]],
        render_targets: Callable[[], Iterable[Any]],
        owner_display: Callable[[Any], Any | None],
        move_viewport: Callable[[Any, Any, Any], None],
        can_move_viewport: Callable[[Any], bool],
        changed: Callable[[], None] | None = None,
    ) -> None:
        self._displays = displays
        self._scenes = scenes
        self._render_targets = render_targets
        self._owner_display = owner_display
        self._move_viewport = move_viewport
        self._can_move_viewport = can_move_viewport
        self._changed = changed
        self._viewport = None
        self.snapshot_changed = Signal()
        self._snapshot = ViewportInspectorSnapshot()

    @property
    def snapshot(self) -> ViewportInspectorSnapshot:
        return self._snapshot

    def set_target(self, viewport) -> ViewportInspectorSnapshot:
        self._viewport = viewport
        return self.refresh()

    def refresh(self) -> ViewportInspectorSnapshot:
        viewport = self._viewport
        if viewport is None:
            return self._publish(ViewportInspectorSnapshot())
        displays = tuple(self._displays(viewport))
        scenes = tuple(self._scenes())
        targets = tuple(self._render_targets())
        owner = self._find_owner(viewport, displays)
        modes = ViewportInspectorSnapshot.input_modes
        mode = viewport.input_mode or "none"
        return self._publish(
            ViewportInspectorSnapshot(
                viewport=viewport,
                name=viewport.name or "<unnamed>",
                enabled=bool(viewport.enabled),
                displays=tuple(InspectorChoice(display.name or f"Display {index}", display)
                               for index, display in enumerate(displays)),
                display_index=_identity_index(displays, owner, _display_identity),
                display_editable=self._can_move_viewport(viewport),
                scenes=tuple(InspectorChoice(scene.name or f"Scene {index}", scene)
                             for index, scene in enumerate(scenes)),
                scene_index=_identity_index(scenes, viewport.scene, _scene_identity),
                input_mode_index=modes.index(mode) if mode in modes else 0,
                block_input_in_editor=bool(viewport.block_input_in_editor),
                rect=tuple(float(value) for value in viewport.rect),
                depth=int(viewport.depth),
                render_targets=(InspectorChoice("(None)", None),) + tuple(
                    InspectorChoice(target.name or f"RenderTarget {target.index}:{target.generation}", target)
                    for target in targets
                ),
                render_target_index=1 + _identity_index(targets, viewport.render_target, _target_identity)
                if viewport.render_target is not None else 0,
            )
        )

    def set_enabled(self, value: bool) -> ViewportInspectorSnapshot:
        self._require_target().enabled = bool(value)
        return self._commit()

    def set_display(self, index: int) -> ViewportInspectorSnapshot:
        viewport = self._require_target()
        if not self._can_move_viewport(viewport):
            _logger.error("Viewport inspector cannot move an editor-owned viewport")
            raise ValueError("editor-owned viewport cannot move between displays")
        choices = self._snapshot.displays
        if not 0 <= index < len(choices):
            raise IndexError("display choice index out of range")
        previous = self._find_owner(
            viewport,
            tuple(choice.value for choice in choices),
        )
        target = choices[index].value
        if previous is not None and _display_identity(previous) != _display_identity(target):
            self._move_viewport(viewport, previous, target)
        return self._commit()

    def set_scene(self, index: int) -> ViewportInspectorSnapshot:
        choices = self._snapshot.scenes
        if not 0 <= index < len(choices):
            raise IndexError("scene choice index out of range")
        self._require_target().scene = choices[index].value
        return self._commit()

    def set_input_mode(self, index: int) -> ViewportInspectorSnapshot:
        modes = self._snapshot.input_modes
        if not 0 <= index < len(modes):
            raise IndexError("input mode index out of range")
        self._require_target().input_mode = modes[index]
        return self._commit()

    def set_block_input_in_editor(self, value: bool) -> ViewportInspectorSnapshot:
        self._require_target().block_input_in_editor = bool(value)
        return self._commit()

    def set_rect(self, value: Iterable[float]) -> ViewportInspectorSnapshot:
        rect = tuple(float(component) for component in value)
        if len(rect) != 4:
            raise ValueError("viewport rect requires four components")
        self._require_target().rect = rect
        return self._commit()

    def set_depth(self, value: int) -> ViewportInspectorSnapshot:
        self._require_target().depth = int(value)
        return self._commit()

    def set_render_target(self, index: int) -> ViewportInspectorSnapshot:
        choices = self._snapshot.render_targets
        if not 0 <= index < len(choices):
            raise IndexError("render target choice index out of range")
        self._require_target().render_target = choices[index].value
        return self._commit()

    def _require_target(self):
        if self._viewport is None:
            _logger.error("Viewport inspector has no target")
            raise RuntimeError("viewport inspector has no target")
        return self._viewport

    def _find_owner(self, viewport, displays: tuple[Any, ...]):
        owner = self._owner_display(viewport)
        if owner is not None:
            return owner
        viewport_identity = viewport._viewport_handle()
        return next(
            (
                display
                for display in displays
                if any(
                    candidate._viewport_handle() == viewport_identity
                    for candidate in display.viewports
                )
            ),
            None,
        )

    def _commit(self) -> ViewportInspectorSnapshot:
        if self._changed is not None:
            self._changed()
        return self.refresh()

    def _publish(self, snapshot: ViewportInspectorSnapshot) -> ViewportInspectorSnapshot:
        self._snapshot = snapshot
        self.snapshot_changed.emit(snapshot)
        return snapshot


TARGET_KINDS = (("texture_2d", "Texture 2D"), ("xr_stereo", "XR Stereo"))
COLOR_FORMATS = (
    ("rgba16f", "RGBA16F"), ("rgba8", "RGBA8"), ("rgb8", "RGB8"),
    ("rg8", "RG8"), ("r8", "R8"), ("r16f", "R16F"),
    ("r32f", "R32F"), ("rgb16f", "RGB16F"),
)
DEPTH_FORMATS = (("depth32f", "Depth 32F"), ("depth24", "Depth 24"))


@dataclass(frozen=True)
class PipelineParameterSnapshot:
    slot: str
    choices: tuple[InspectorChoice, ...]
    selected_index: int


@dataclass(frozen=True)
class RenderTargetInspectorSnapshot:
    render_target: Any = None
    name: str = ""
    enabled: bool = False
    kind_choices: tuple[InspectorChoice, ...] = tuple(InspectorChoice(label, value) for value, label in TARGET_KINDS)
    kind_index: int = 0
    scenes: tuple[InspectorChoice, ...] = (InspectorChoice("(None)", None),)
    scene_index: int = 0
    source_label: str = "Camera"
    sources: tuple[InspectorChoice, ...] = (InspectorChoice("(None)", None),)
    source_index: int = 0
    pipelines: tuple[InspectorChoice, ...] = (InspectorChoice("(None)", None),)
    pipeline_index: int = 0
    dynamic_resolution: bool = True
    color_formats: tuple[InspectorChoice, ...] = tuple(InspectorChoice(label, value) for value, label in COLOR_FORMATS)
    color_format_index: int = 0
    depth_formats: tuple[InspectorChoice, ...] = tuple(InspectorChoice(label, value) for value, label in DEPTH_FORMATS)
    depth_format_index: int = 0
    clear_color_enabled: bool = False
    clear_color_value: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    clear_depth_enabled: bool = False
    clear_depth_value: float = 1.0
    width: int = 512
    height: int = 512
    layer_mask: int = 0
    layer_names: tuple[str, ...] = ()
    pipeline_parameters: tuple[PipelineParameterSnapshot, ...] = ()

    @property
    def has_target(self) -> bool:
        return self.render_target is not None

    @property
    def is_texture_target(self) -> bool:
        return self.has_target and self.kind_choices[self.kind_index].value == "texture_2d"


class RenderTargetInspectorController:
    def __init__(
        self,
        resource_manager,
        *,
        scenes: Callable[[], Iterable[Any]],
        layer_names: Callable[[], Iterable[str]],
        create_default_pipeline: Callable[[], Any],
        changed: Callable[[], None] | None = None,
    ) -> None:
        self._resource_manager = resource_manager
        self._scenes = scenes
        self._layer_names = layer_names
        self._create_default_pipeline = create_default_pipeline
        self._changed = changed
        self._render_target = None
        self._fallback_scene = None
        self._texture_sources = MaterialTextureSourceCatalog(resource_manager, scene_getter=scenes)
        self.snapshot_changed = Signal()
        self._snapshot = RenderTargetInspectorSnapshot()

    @property
    def snapshot(self) -> RenderTargetInspectorSnapshot:
        return self._snapshot

    def set_target(self, render_target, fallback_scene=None) -> RenderTargetInspectorSnapshot:
        self._render_target = render_target
        self._fallback_scene = fallback_scene
        return self.refresh()

    def refresh(self) -> RenderTargetInspectorSnapshot:
        target = self._render_target
        if target is None:
            return self._publish(RenderTargetInspectorSnapshot())
        scenes = tuple(self._scenes())
        scene_choices = (InspectorChoice("(None)", None),) + tuple(
            InspectorChoice(scene.name or f"Scene {index}", scene)
            for index, scene in enumerate(scenes)
        )
        sources = self._render_sources(target)
        pipeline_choices = self._pipeline_choices()
        kind_index = _value_index(TARGET_KINDS, target.kind)
        color_index = _value_index(COLOR_FORMATS, target.color_format)
        depth_index = _value_index(DEPTH_FORMATS, target.depth_format)
        current_source = target.xr_origin if target.kind == "xr_stereo" else target.camera
        snapshot = RenderTargetInspectorSnapshot(
            render_target=target,
            name=target.name or "<unnamed>",
            enabled=bool(target.enabled),
            kind_index=kind_index,
            scenes=scene_choices,
            scene_index=1 + _identity_index(scenes, target.scene, _scene_identity)
            if target.scene is not None else 0,
            source_label="XR Origin" if target.kind == "xr_stereo" else "Camera",
            sources=(InspectorChoice("(None)", None),) + sources,
            source_index=1 + _identity_index(tuple(choice.value for choice in sources), current_source, id)
            if current_source is not None else 0,
            pipelines=pipeline_choices,
            pipeline_index=self._pipeline_index(pipeline_choices, target.pipeline),
            dynamic_resolution=bool(target.dynamic_resolution),
            color_format_index=color_index,
            depth_format_index=depth_index,
            clear_color_enabled=bool(target.clear_color_enabled),
            clear_color_value=tuple(float(value) for value in target.clear_color_value),
            clear_depth_enabled=bool(target.clear_depth_enabled),
            clear_depth_value=float(target.clear_depth_value),
            width=int(target.width),
            height=int(target.height),
            layer_mask=int(target.layer_mask),
            layer_names=tuple(self._layer_names()),
        )
        return self._publish(
            replace(snapshot, pipeline_parameters=self._pipeline_parameters(snapshot))
        )

    def set_enabled(self, value: bool):
        self._require_target().enabled = bool(value)
        return self._commit()

    def set_kind(self, index: int):
        self._require_target().kind = self._choice(self._snapshot.kind_choices, index, "kind")
        return self._commit()

    def set_scene(self, index: int):
        self._require_target().scene = self._choice(self._snapshot.scenes, index, "scene")
        return self._commit()

    def set_source(self, index: int):
        target = self._require_target()
        value = self._choice(self._snapshot.sources, index, "render source")
        if target.kind == "xr_stereo":
            target.xr_origin = value
        else:
            target.camera = value
        return self._commit()

    def set_pipeline(self, index: int):
        target = self._require_target()
        choice = self._snapshot.pipelines[index] if 0 <= index < len(self._snapshot.pipelines) else None
        if choice is None:
            raise IndexError("pipeline choice index out of range")
        target.pipeline = self._create_default_pipeline() if choice.value == "__default__" else choice.value
        return self._commit()

    def set_dynamic_resolution(self, value: bool):
        self._require_target().dynamic_resolution = bool(value)
        return self._commit()

    def set_color_format(self, index: int):
        self._require_target().color_format = self._choice(self._snapshot.color_formats, index, "color format")
        return self._commit()

    def set_depth_format(self, index: int):
        self._require_target().depth_format = self._choice(self._snapshot.depth_formats, index, "depth format")
        return self._commit()

    def set_clear_color_enabled(self, value: bool):
        self._require_target().clear_color_enabled = bool(value)
        return self._commit()

    def set_clear_color_value(self, value: Iterable[float]):
        color = tuple(float(component) for component in value)
        if len(color) != 4:
            raise ValueError("clear color requires four components")
        self._require_target().clear_color_value = color
        return self._commit()

    def set_clear_depth_enabled(self, value: bool):
        self._require_target().clear_depth_enabled = bool(value)
        return self._commit()

    def set_clear_depth_value(self, value: float):
        self._require_target().clear_depth_value = float(value)
        return self._commit()

    def set_size(self, width: int, height: int):
        if width <= 0 or height <= 0:
            raise ValueError("render target dimensions must be positive")
        target = self._require_target()
        target.width = int(width)
        target.height = int(height)
        return self._commit()

    def set_layer_mask(self, value: int):
        self._require_target().layer_mask = int(value)
        return self._commit()

    def set_pipeline_parameter(self, slot: str, index: int):
        parameter = next((item for item in self._snapshot.pipeline_parameters if item.slot == slot), None)
        if parameter is None or not 0 <= index < len(parameter.choices):
            raise IndexError("pipeline parameter choice index out of range")
        choice = parameter.choices[index]
        target = self._require_target()
        params = dict(target.pipeline_params)
        if choice.value is None:
            params.pop(slot, None)
        else:
            tag, name = choice.value
            if tag == "file":
                asset = self._resource_manager.get_texture_asset(name)
                if asset is None:
                    _logger.error("Pipeline parameter texture asset not found: %s", name)
                    raise ValueError(f"unknown texture asset '{name}'")
                params[slot] = f"file:{asset.uuid}"
            else:
                params[slot] = name
        target.pipeline_params = params
        return self._commit()

    def _render_sources(self, target) -> tuple[InspectorChoice, ...]:
        scene = target.scene if target.scene is not None else self._fallback_scene
        if scene is None:
            return ()
        if target.kind == "xr_stereo":
            from termin.render_components import XrOriginComponent
            component_type = XrOriginComponent
            fallback = "XR Origin"
        else:
            from termin.render_components.camera import CameraComponent
            component_type = CameraComponent
            fallback = "Camera"
        result = []
        for entity in scene.entities:
            component = entity.get_component(component_type)
            if component is not None:
                result.append(InspectorChoice(entity.name or entity.uuid or fallback, component))
        return tuple(result)

    def _pipeline_choices(self) -> tuple[InspectorChoice, ...]:
        choices = [InspectorChoice("(None)", None), InspectorChoice("(Default)", "__default__")]
        for name in self._resource_manager.list_pipeline_names():
            pipeline = self._resource_manager.get_pipeline(name)
            if pipeline is not None:
                choices.append(InspectorChoice(name, pipeline))
        return tuple(choices)

    @staticmethod
    def _pipeline_index(choices: tuple[InspectorChoice, ...], pipeline) -> int:
        if pipeline is None:
            return 0
        name = pipeline.name or ""
        for index, choice in enumerate(choices):
            if choice.label == name:
                return index
        return 1 if name == "Default" else 0

    def _pipeline_parameters(self, snapshot: RenderTargetInspectorSnapshot) -> tuple[PipelineParameterSnapshot, ...]:
        target = snapshot.render_target
        if target is None or target.pipeline is None or snapshot.pipeline_index <= 1:
            return ()
        pipeline_name = snapshot.pipelines[snapshot.pipeline_index].label
        asset = self._resource_manager.get_pipeline_asset(pipeline_name)
        if asset is None:
            asset = self._resource_manager.get_scene_pipeline_asset(pipeline_name)
        if asset is None:
            return ()
        choices = [InspectorChoice("Default", None)]
        choices.extend(
            InspectorChoice(source.label, (source.tag, source.name))
            for source in self._texture_sources.choices()
            if source.tag != "default"
        )
        result = []
        for slot in asset.external_params:
            current = target.pipeline_params.get(slot, "")
            selected = 0
            if current.startswith("file:"):
                asset_value = self._resource_manager.get_texture_asset_by_uuid(current[5:])
                if asset_value is not None:
                    selected = next((index for index, choice in enumerate(choices)
                                     if choice.value == ("file", asset_value.name)), 0)
            elif current:
                selected = next((index for index, choice in enumerate(choices)
                                 if choice.value is not None and choice.value[1] == current), 0)
            result.append(PipelineParameterSnapshot(slot, tuple(choices), selected))
        return tuple(result)

    def _require_target(self):
        if self._render_target is None:
            _logger.error("Render target inspector has no target")
            raise RuntimeError("render target inspector has no target")
        return self._render_target

    def _commit(self) -> RenderTargetInspectorSnapshot:
        if self._changed is not None:
            self._changed()
        return self.refresh()

    def _publish(self, snapshot: RenderTargetInspectorSnapshot) -> RenderTargetInspectorSnapshot:
        self._snapshot = snapshot
        self.snapshot_changed.emit(snapshot)
        return snapshot

    @staticmethod
    def _choice(choices: tuple[InspectorChoice, ...], index: int, label: str):
        if not 0 <= index < len(choices):
            raise IndexError(f"{label} choice index out of range")
        return choices[index].value


def _identity_index(values: tuple[Any, ...], target: Any, identity: Callable[[Any], Any]) -> int:
    if target is None:
        return -1
    target_identity = identity(target)
    return next((index for index, value in enumerate(values) if identity(value) == target_identity), -1)


def _display_identity(display) -> int:
    return int(display.tc_display_ptr)


def _scene_identity(scene) -> tuple[int, int]:
    handle = scene.scene_handle()
    return int(handle.index), int(handle.generation)


def _target_identity(target) -> tuple[int, int]:
    return int(target.index), int(target.generation)


def _value_index(entries: tuple[tuple[str, str], ...], value: str) -> int:
    return next((index for index, entry in enumerate(entries) if entry[0] == value), 0)


__all__ = [
    "COLOR_FORMATS",
    "DEPTH_FORMATS",
    "TARGET_KINDS",
    "DisplayInspectorController",
    "DisplayInspectorSnapshot",
    "InspectorChoice",
    "PipelineParameterSnapshot",
    "RenderTargetInspectorController",
    "RenderTargetInspectorSnapshot",
    "ViewportInspectorController",
    "ViewportInspectorSnapshot",
]
