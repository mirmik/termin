"""Toolkit-neutral material inspector state and mutation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable


_logger = logging.getLogger(__name__)

MaterialChangedHandler = Callable[[], None]
RenderTargetTextureResolver = Callable[[str, str], Any | None]


@dataclass(frozen=True)
class MaterialTextureValue:
    tag: str
    name: str
    default_kind: str = "white"


@dataclass(frozen=True)
class MaterialPropertySnapshot:
    name: str
    label: str
    kind: str
    value: Any
    minimum: float | None = None
    maximum: float | None = None
    texture: MaterialTextureValue | None = None


@dataclass(frozen=True)
class MaterialInspectorSnapshot:
    has_material: bool
    name: str = ""
    uuid: str = ""
    shader_name: str = ""
    shader_choices: tuple[str, ...] = ()
    phase_count: int = 0
    properties: tuple[MaterialPropertySnapshot, ...] = ()
    message: str = "Material not found."


def material_vector(value: Any, size: int, *, color: bool = False) -> tuple[float, ...]:
    """Normalize shader vector values without depending on a widget toolkit."""
    if value is None:
        values = []
    else:
        try:
            values = [float(component) for component in value][:size]
        except (TypeError, ValueError) as error:
            _logger.error("Material vector value is not iterable: %r: %s", value, error)
            raise ValueError("material vector value is not iterable") from error
    fill = 1.0 if color and size == 4 and len(values) == 3 else 0.0
    values.extend(fill for _ in range(size - len(values)))
    if color:
        values = [max(0.0, min(1.0, component)) for component in values]
    return tuple(values)


class MaterialInspectorController:
    """Own material discovery, edits, persistence and immutable UI snapshots."""

    def __init__(
        self,
        resource_manager,
        *,
        changed: MaterialChangedHandler | None = None,
        render_target_texture: RenderTargetTextureResolver | None = None,
    ) -> None:
        self._resource_manager = resource_manager
        self._changed = changed
        self._render_target_texture = render_target_texture
        self._material = None
        self._snapshot = MaterialInspectorSnapshot(False)

    @property
    def material(self):
        return self._material

    @property
    def snapshot(self) -> MaterialInspectorSnapshot:
        return self._snapshot

    def set_changed_handler(self, handler: MaterialChangedHandler | None) -> None:
        self._changed = handler

    def set_render_target_texture_resolver(self, resolver: RenderTargetTextureResolver | None) -> None:
        self._render_target_texture = resolver

    def set_target(self, material) -> MaterialInspectorSnapshot:
        self._material = material
        return self.refresh()

    def refresh(self) -> MaterialInspectorSnapshot:
        material = self._material
        if material is None:
            self._snapshot = MaterialInspectorSnapshot(False)
            return self._snapshot

        shader_choices = tuple(self._resource_manager.list_shader_names())
        program = self._resource_manager.get_shader(material.shader_name)
        properties: tuple[MaterialPropertySnapshot, ...] = ()
        message = ""
        if program is None or not program.phases:
            message = "Shader metadata unavailable."
        else:
            properties = tuple(self._property_snapshot(prop) for prop in program.material_properties)
        self._snapshot = MaterialInspectorSnapshot(
            True,
            name=str(material.name or ""),
            uuid=str(material.uuid or ""),
            shader_name=str(material.shader_name or ""),
            shader_choices=shader_choices,
            phase_count=len(material.phases or ()),
            properties=properties,
            message=message,
        )
        return self._snapshot

    def set_name(self, name: str) -> MaterialInspectorSnapshot:
        material = self._require_material()
        normalized = name.strip()
        if not normalized:
            _logger.error("Cannot assign an empty material name")
            raise ValueError("material name cannot be empty")
        if material.name != normalized:
            material.name = normalized
            self._commit_change()
        return self.refresh()

    def set_shader(self, shader_name: str) -> MaterialInspectorSnapshot:
        material = self._require_material()
        if not shader_name or shader_name == material.shader_name:
            return self.refresh()
        program = self._resource_manager.get_shader(shader_name)
        if program is None:
            _logger.error("Cannot apply unknown material shader '%s'", shader_name)
            raise ValueError(f"unknown material shader '{shader_name}'")
        from termin.default_assets.render.shader_asset import update_material_shader

        shader_asset = self._resource_manager.get_shader_asset(shader_name)
        shader_uuid = "" if shader_asset is None else shader_asset.uuid
        update_material_shader(material, program, shader_name, shader_uuid)
        self._commit_change()
        return self.refresh()

    def set_property(self, name: str, value: Any) -> MaterialInspectorSnapshot:
        prop = self._property(name)
        kind = prop.property_type
        if kind == "Bool":
            converted = bool(value)
        elif kind == "Int":
            converted = int(value)
        elif kind == "Float":
            converted = float(value)
        elif kind == "Vec2":
            converted = list(material_vector(value, 2))
        elif kind in ("Vec3", "Color", "Vec4"):
            from termin.geombase import Vec3, Vec4

            size = 3 if kind == "Vec3" else 4
            components = material_vector(value, size, color=kind == "Color")
            converted = Vec3(*components) if size == 3 else Vec4(*components)
        else:
            _logger.error("Material property '%s' has unsupported scalar kind '%s'", name, kind)
            raise ValueError(f"unsupported material property kind '{kind}'")
        material = self._require_material()
        for phase in material.phases:
            phase.set_param(name, converted)
        self._commit_change()
        return self.refresh()

    def set_texture(
        self,
        name: str,
        tag: str,
        texture_name: str = "",
        *,
        default_kind: str = "white",
    ) -> MaterialInspectorSnapshot:
        material = self._require_material()
        texture = self._resolve_texture(tag, texture_name, default_kind)
        if texture is None or not texture.is_valid:
            _logger.error(
                "Cannot resolve valid material texture '%s' (%s:%s)",
                name,
                tag,
                texture_name,
            )
            raise ValueError(f"invalid texture for material property '{name}'")
        applied = material.set_texture(name, texture)
        if applied <= 0:
            _logger.error("Material texture property '%s' was not applied to any phase", name)
            raise ValueError(f"texture property '{name}' was not applied")
        self._commit_change()
        return self.refresh()

    def _property_snapshot(self, prop) -> MaterialPropertySnapshot:
        material = self._require_material()
        name = str(prop.name)
        kind = str(prop.property_type)
        label = str(prop.label or name)
        if kind in ("Texture", "Texture2D"):
            default_kind = prop.default if prop.default in ("white", "normal") else "white"
            texture = self._texture_value(name, default_kind)
            return MaterialPropertySnapshot(name, label, kind, None, texture=texture)
        value = material.uniforms.get(name, prop.default)
        if kind in ("Vec2", "Vec3", "Vec4", "Color"):
            size = {"Vec2": 2, "Vec3": 3, "Vec4": 4, "Color": 4}[kind]
            value = material_vector(value, size, color=kind == "Color")
        return MaterialPropertySnapshot(
            name,
            label,
            kind,
            value,
            minimum=None if prop.range_min is None else float(prop.range_min),
            maximum=None if prop.range_max is None else float(prop.range_max),
        )

    def _texture_value(self, name: str, default_kind: str) -> MaterialTextureValue:
        material = self._require_material()
        texture = material.textures.get(name)
        if texture is None or not texture.is_valid:
            return MaterialTextureValue("default", "", default_kind)
        asset_name = self._resource_manager.find_texture_name(texture)
        if asset_name and asset_name != "__white_1x1__":
            return MaterialTextureValue("file", asset_name, default_kind)
        from termin.default_assets.render.material_asset import _classify_render_target_texture

        reference = _classify_render_target_texture(texture)
        if reference is not None:
            return MaterialTextureValue(f"rt_{reference['channel']}", reference["target"], default_kind)
        return MaterialTextureValue("default", "", default_kind)

    def _resolve_texture(self, tag: str, name: str, default_kind: str):
        if tag == "default" or not name:
            from termin.render.texture_handle import (
                get_normal_texture_handle,
                get_white_texture_handle,
            )

            return get_normal_texture_handle() if default_kind == "normal" else get_white_texture_handle()
        if tag == "file":
            return self._resource_manager.get_texture_handle(name)
        if tag in ("rt_color", "rt_depth") and self._render_target_texture is not None:
            return self._render_target_texture(name, "depth" if tag == "rt_depth" else "color")
        _logger.error("Unknown or unavailable material texture source '%s'", tag)
        raise ValueError(f"unknown material texture source '{tag}'")

    def _property(self, name: str):
        material = self._require_material()
        program = self._resource_manager.get_shader(material.shader_name)
        if program is not None:
            for prop in program.material_properties:
                if prop.name == name:
                    return prop
        _logger.error("Cannot edit unknown material property '%s'", name)
        raise KeyError(name)

    def _require_material(self):
        if self._material is None:
            _logger.error("Material inspector has no target")
            raise RuntimeError("material inspector has no target")
        return self._material

    def _commit_change(self) -> None:
        self._save_material_asset()
        if self._changed is not None:
            self._changed()

    def _save_material_asset(self) -> None:
        material = self._require_material()
        material_name = self._resource_manager.find_material_name(material)
        if material_name is None:
            _logger.warning(
                "Material changes are runtime-only: material '%s' has no registered asset",
                material.name,
            )
            return
        asset = self._resource_manager.get_material_asset(material_name)
        if asset is None:
            _logger.warning(
                "Material changes are runtime-only: registered material '%s' has no asset",
                material_name,
            )
            return
        if not asset.save_to_file():
            _logger.error("Failed to save material asset '%s'", material_name)
            raise RuntimeError(f"failed to save material asset '{material_name}'")


__all__ = [
    "MaterialInspectorController",
    "MaterialInspectorSnapshot",
    "MaterialPropertySnapshot",
    "MaterialTextureValue",
    "material_vector",
]
