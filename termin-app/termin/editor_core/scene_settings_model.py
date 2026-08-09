"""Toolkit-neutral models for scene layers, shadows and render properties."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

from termin.editor_core.editor_commands import ScenePropertyEditCommand, SkyboxTypeEditCommand
from termin.geombase import SrgbColor
from termin.render import debug_geometry_types, scene_render_mount, scene_render_state


_NAME_COUNT = 64
SKYBOX_TYPES = ("gradient", "solid", "none")
SHADOW_METHODS = ("Hard", "PCF", "Poisson")


def _color(value, *, alpha: bool) -> tuple[float, ...]:
    result = (float(value[0]), float(value[1]), float(value[2]))
    return result + (float(value[3]),) if alpha else result


def _srgb_color(value, *, alpha: bool) -> SrgbColor:
    components = _color(value, alpha=alpha)
    if alpha:
        return SrgbColor(*components)
    return SrgbColor(*components, 1.0)


def _render_state(scene):
    state = scene_render_state(scene)
    if state.shadow_settings is None:
        state.ambient_intensity = state.ambient_intensity
    return state


@dataclass(frozen=True)
class SceneNamesSnapshot:
    layers: tuple[str, ...]
    flags: tuple[str, ...]


class SceneNamesController:
    def __init__(self, scene) -> None:
        self._scene = scene

    def set_scene(self, scene) -> SceneNamesSnapshot | None:
        self._scene = scene
        return None if scene is None else self.load()

    def load(self) -> SceneNamesSnapshot:
        return SceneNamesSnapshot(
            tuple(str(self._scene.layer_names.get(index, "")) for index in range(_NAME_COUNT)),
            tuple(str(self._scene.flag_names.get(index, "")) for index in range(_NAME_COUNT)),
        )

    def save(self, snapshot: SceneNamesSnapshot) -> SceneNamesSnapshot:
        if len(snapshot.layers) != _NAME_COUNT or len(snapshot.flags) != _NAME_COUNT:
            raise ValueError("scene layers and flags must contain exactly 64 names")
        normalized = SceneNamesSnapshot(
            tuple(name.strip() for name in snapshot.layers),
            tuple(name.strip() for name in snapshot.flags),
        )
        for index, name in enumerate(normalized.layers):
            self._scene.set_layer_name(index, name)
        for index, name in enumerate(normalized.flags):
            self._scene.set_flag_name(index, name)
        return normalized


@dataclass(frozen=True)
class ShadowSettingsSnapshot:
    method: int
    softness: float
    bias: float


class ShadowSettingsController:
    def __init__(self, scene, *, mirror_scenes=(), on_changed: Callable[[], None] | None = None) -> None:
        self._scene = scene
        self._mirror_scenes = tuple(item for item in mirror_scenes if item is not None and item is not scene)
        self._on_changed = on_changed

    def set_scene(self, scene, *, mirror_scenes=()) -> ShadowSettingsSnapshot | None:
        self._scene = scene
        self._mirror_scenes = tuple(
            item for item in mirror_scenes if item is not None and item is not scene
        )
        return None if scene is None else self.load()

    def load(self) -> ShadowSettingsSnapshot:
        settings = _render_state(self._scene).shadow_settings
        return ShadowSettingsSnapshot(int(settings.method), float(settings.softness), float(settings.bias))

    def apply(self, snapshot: ShadowSettingsSnapshot) -> ShadowSettingsSnapshot:
        validated = self.validate(snapshot)
        state = _render_state(self._scene)
        settings = state.shadow_settings
        settings.method = validated.method
        settings.softness = validated.softness
        settings.bias = validated.bias
        state.shadow_settings = settings
        for mirror_scene in self._mirror_scenes:
            _render_state(mirror_scene).shadow_settings = settings
        if self._on_changed is not None:
            self._on_changed()
        return validated

    @staticmethod
    def validate(snapshot: ShadowSettingsSnapshot) -> ShadowSettingsSnapshot:
        method = int(snapshot.method)
        softness = float(snapshot.softness)
        bias = float(snapshot.bias)
        if not 0 <= method < len(SHADOW_METHODS):
            raise ValueError("shadow method index is out of range")
        if not 0.0 <= softness <= 10.0:
            raise ValueError("shadow softness must be in range 0..10")
        if not 0.0 <= bias <= 0.05:
            raise ValueError("shadow receiver bias must be in range 0..0.05")
        return ShadowSettingsSnapshot(method, softness, bias)


@dataclass(frozen=True)
class ScenePipelineSnapshot:
    name: str
    uuid: str
    valid: bool


@dataclass(frozen=True)
class DebugGeometrySettingSnapshot:
    stable_id: str
    display_name: str
    category: str
    enabled: bool


@dataclass(frozen=True)
class ScenePropertiesSnapshot:
    fixed_update_frequency: float
    time_scale: float
    background_color: tuple[float, float, float, float]
    ambient_color: tuple[float, float, float]
    ambient_intensity: float
    skybox_type: str
    skybox_color: tuple[float, float, float]
    skybox_top_color: tuple[float, float, float]
    skybox_bottom_color: tuple[float, float, float]
    pipelines: tuple[ScenePipelineSnapshot, ...]
    debug_geometry: tuple[DebugGeometrySettingSnapshot, ...]


class ScenePropertiesController:
    def __init__(
        self,
        scene,
        *,
        push_undo_command: Callable[[object, bool], None] | None = None,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        self._scene = scene
        self._push_undo_command = push_undo_command
        self._on_changed = on_changed

    def set_scene(self, scene) -> ScenePropertiesSnapshot | None:
        self._scene = scene
        return None if scene is None else self.load()

    def load(self) -> ScenePropertiesSnapshot:
        state = _render_state(self._scene)
        mount = scene_render_mount(self._scene)
        handles = tuple(mount.pipeline_templates)
        pipelines = tuple(
            ScenePipelineSnapshot(
                name=handle.name if handle.is_valid else "(missing pipeline)",
                uuid=handle.uuid if handle.is_valid else "",
                valid=bool(handle.is_valid),
            )
            for handle in handles
        )
        debug_geometry = tuple(
            DebugGeometrySettingSnapshot(
                stable_id=str(item["stable_id"]),
                display_name=str(item["display_name"]),
                category=str(item["category"]),
                enabled=bool(mount.debug_geometry_enabled(str(item["stable_id"]))),
            )
            for item in debug_geometry_types()
        )
        return ScenePropertiesSnapshot(
            fixed_update_frequency=1.0 / float(self._scene.fixed_timestep),
            time_scale=float(self._scene.time_scale),
            background_color=_color(state.background_srgb_color, alpha=True),
            ambient_color=_color(state.ambient_srgb_color, alpha=False),
            ambient_intensity=float(state.ambient_intensity),
            skybox_type=str(state.skybox_type),
            skybox_color=_color(state.skybox_srgb_color, alpha=False),
            skybox_top_color=_color(state.skybox_top_srgb_color, alpha=False),
            skybox_bottom_color=_color(state.skybox_bottom_srgb_color, alpha=False),
            pipelines=pipelines,
            debug_geometry=debug_geometry,
        )

    def set_debug_geometry_enabled(
        self,
        stable_id: str,
        enabled: bool,
    ) -> ScenePropertiesSnapshot:
        scene_render_mount(self._scene).set_debug_geometry_enabled(
            str(stable_id), bool(enabled)
        )
        return self._published()

    def set_fixed_update_frequency(self, value: float) -> ScenePropertiesSnapshot:
        frequency = float(value)
        if not math.isfinite(frequency) or frequency <= 0.0:
            raise ValueError("fixed update frequency must be finite and positive")
        old_timestep = float(self._scene.fixed_timestep)
        new_timestep = 1.0 / frequency
        command = ScenePropertyEditCommand(
            self._scene,
            "fixed_timestep",
            old_timestep,
            new_timestep,
            "Edit fixed update frequency",
        )

        def apply_direct() -> None:
            self._scene.fixed_timestep = new_timestep

        self._apply_command(command, apply_direct, True)
        return self._published()

    def set_time_scale(self, value: float) -> ScenePropertiesSnapshot:
        scale = float(value)
        if not math.isfinite(scale) or scale < 0.0:
            raise ValueError("time scale must be finite and non-negative")
        old_scale = float(self._scene.time_scale)
        command = ScenePropertyEditCommand(
            self._scene,
            "time_scale",
            old_scale,
            scale,
            "Edit simulation time scale",
        )

        def apply_direct() -> None:
            self._scene.time_scale = scale

        self._apply_command(command, apply_direct, True)
        return self._published()

    def set_background_color(self, value) -> ScenePropertiesSnapshot:
        state = _render_state(self._scene)
        color = _srgb_color(value, alpha=True)
        return self._edit("background_color", state.background_srgb_color, color, merge=False)

    def set_ambient_color(self, value) -> ScenePropertiesSnapshot:
        state = _render_state(self._scene)
        return self._edit(
            "ambient_color", state.ambient_srgb_color, _srgb_color(value, alpha=False), merge=False
        )

    def set_ambient_intensity(self, value: float) -> ScenePropertiesSnapshot:
        intensity = float(value)
        if not 0.0 <= intensity <= 10.0:
            raise ValueError("ambient intensity must be in range 0..10")
        state = _render_state(self._scene)
        return self._edit("ambient_intensity", state.ambient_intensity, intensity, merge=True)

    def set_skybox_type(self, value: str) -> ScenePropertiesSnapshot:
        skybox_type = str(value)
        if skybox_type not in SKYBOX_TYPES:
            raise ValueError(f"unsupported skybox type: {skybox_type}")
        state = _render_state(self._scene)
        if skybox_type != state.skybox_type:
            command = SkyboxTypeEditCommand(self._scene, state.skybox_type, skybox_type)
            def apply_direct() -> None:
                state.skybox_type = skybox_type

            self._apply_command(command, apply_direct, False)
        return self._published()

    def set_skybox_color(self, value) -> ScenePropertiesSnapshot:
        state = _render_state(self._scene)
        return self._edit(
            "skybox_color", state.skybox_srgb_color, _srgb_color(value, alpha=False), merge=False
        )

    def set_skybox_top_color(self, value) -> ScenePropertiesSnapshot:
        state = _render_state(self._scene)
        return self._edit(
            "skybox_top_color", state.skybox_top_srgb_color, _srgb_color(value, alpha=False), merge=False
        )

    def set_skybox_bottom_color(self, value) -> ScenePropertiesSnapshot:
        state = _render_state(self._scene)
        return self._edit(
            "skybox_bottom_color", state.skybox_bottom_srgb_color, _srgb_color(value, alpha=False), merge=False
        )

    def remove_pipeline(self, index: int) -> ScenePropertiesSnapshot:
        mount = scene_render_mount(self._scene)
        handles = tuple(mount.pipeline_templates)
        if not 0 <= index < len(handles):
            raise IndexError("scene pipeline index is out of range")
        mount.remove_pipeline_template(handles[index])
        return self._published()

    def _edit(self, name: str, old_value, new_value, *, merge: bool) -> ScenePropertiesSnapshot:
        command = ScenePropertyEditCommand(self._scene, name, old_value, new_value)
        state = _render_state(self._scene)

        def apply_direct() -> None:
            if name == "background_color":
                state.background_srgb_color = new_value
            elif name == "ambient_color":
                state.ambient_srgb_color = new_value
            elif name == "ambient_intensity":
                state.ambient_intensity = new_value
            elif name == "skybox_color":
                state.skybox_srgb_color = new_value
            elif name == "skybox_top_color":
                state.skybox_top_srgb_color = new_value
            elif name == "skybox_bottom_color":
                state.skybox_bottom_srgb_color = new_value
            else:
                raise RuntimeError(f"unsupported direct scene property: {name}")

        self._apply_command(command, apply_direct, merge)
        return self._published()

    def _apply_command(self, command, apply_direct: Callable[[], None], merge: bool) -> None:
        if self._push_undo_command is None:
            apply_direct()
        else:
            self._push_undo_command(command, merge)

    def _published(self) -> ScenePropertiesSnapshot:
        if self._on_changed is not None:
            self._on_changed()
        return self.load()


__all__ = [
    "SHADOW_METHODS",
    "SKYBOX_TYPES",
    "SceneNamesController",
    "SceneNamesSnapshot",
    "ScenePipelineSnapshot",
    "DebugGeometrySettingSnapshot",
    "ScenePropertiesController",
    "ScenePropertiesSnapshot",
    "ShadowSettingsController",
    "ShadowSettingsSnapshot",
]
