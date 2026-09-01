"""MaterialAsset - Asset for material configuration.

NOTE: This class has some deviations from the standard DataAsset pattern:

1. from_file() reads content immediately instead of lazy loading.
   Standard pattern defers reading until .data is accessed.

2. UUID is stored inside the .material JSON file, not in a separate .meta file.
   This requires manual UUID extraction in _parse_content().

3. _on_loaded() auto-saves the file if UUID was missing.
   This ensures all materials get persistent UUIDs.

These deviations exist because materials are self-contained JSON documents
that embed their own metadata. Since materials are typically small files
(a few KB), eager loading does not significantly impact engine performance.

See also: PrefabAsset (same pattern).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from termin_assets import DataAsset
from termin.base import log

if TYPE_CHECKING:
    from termin.materials import TcMaterial


class MaterialAsset(DataAsset["TcMaterial"]):
    """
    Asset for material configuration.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores TcMaterial (shader reference, uniforms, textures).
    """

    _uses_binary = False  # JSON text format

    def __init__(
        self,
        material: "TcMaterial | None" = None,
        name: str = "material",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=material, name=name, source_path=source_path, uuid=uuid)

    # --- Convenience property ---

    @property
    def material(self) -> "TcMaterial | None":
        """Material configuration (lazy-loaded)."""
        return self.data

    @material.setter
    def material(self, value: "TcMaterial | None") -> None:
        """Set material and bump version."""
        self.data = value

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "TcMaterial | None":
        """Parse JSON content into TcMaterial."""
        material, file_uuid = _parse_material_content(
            content,
            name=self._name,
            source_path=str(self._source_path) if self._source_path else None,
        )

        # Adopt UUID from file if present
        if file_uuid:
            self._uuid = file_uuid
            self._runtime_id = hash(self._uuid) & 0xFFFFFFFFFFFFFFFF
            # Mark that UUID was in the file, so we don't re-save
            self._has_uuid_in_spec = True

        return material

    def _on_loaded(self) -> None:
        """After loading, save file if it didn't have UUID."""
        # Check if file has UUID by re-reading (not ideal but simple)
        if self._source_path is not None:
            try:
                with open(self._source_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "uuid" not in data:
                    self.save_to_file()
            except Exception:
                log.warning(f"[MaterialAsset] Failed to re-read material file for UUID check: {self._source_path}")

    # --- Saving (materials save to their own file, not spec) ---

    def save_spec_file(self) -> bool:
        """Materials don't use spec files - save to the material file instead."""
        return self.save_to_file()

    def save_to_file(self, path: str | Path | None = None) -> bool:
        """
        Save material to .material file.

        Args:
            path: Path to save. If None, uses source_path.

        Returns:
            True if saved successfully.
        """
        if self._data is None:
            return False

        save_path = Path(path) if path else self._source_path
        if save_path is None:
            return False

        try:
            _save_material_file(self._data, save_path, uuid=self.uuid)
            self._source_path = Path(save_path)
            self.mark_just_saved()
            return True
        except Exception:
            log.error(f"[MaterialAsset] Failed to save material to file: {save_path}", exc_info=True)
            return False

    def update_from(self, other: "MaterialAsset") -> None:
        """
        Update material data from another asset (hot-reload).

        For TcMaterial, we replace entirely (hot-reload will recreate phases).
        """
        if other._data is not None:
            self._data = other._data
            self._loaded = True
            self._bump_version()

    # --- Factory methods ---

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "MaterialAsset":
        """Create MaterialAsset from .material file."""
        path = Path(path)
        material, file_uuid = _load_material_file(str(path))
        return cls(
            material=material,
            name=name or path.stem,
            source_path=path,
            uuid=file_uuid,
        )

    @classmethod
    def from_material(
        cls,
        material: "TcMaterial",
        name: str | None = None,
        source_path: str | Path | None = None,
        uuid: str | None = None,
    ) -> "MaterialAsset":
        """Create MaterialAsset from existing TcMaterial."""
        return cls(
            material=material,
            name=name or material.name or "material",
            source_path=source_path or material.source_path,
            # TcMaterial is itself UUID-addressed by the native registry.  The
            # asset and its runtime handle must never acquire separate IDs.
            uuid=uuid or material.uuid,
        )


# --- File I/O functions ---

def _build_render_state(shader_phase, phase_mark: str | None = None):
    """Build tc_render_state from shader phase flags."""
    from termin.materials import TcRenderState

    # Start with default based on phase mark
    mark = phase_mark or shader_phase.phase_mark
    if mark == "transparent":
        state = TcRenderState.transparent()
    elif mark == "wireframe":
        state = TcRenderState.wireframe()
    else:
        state = TcRenderState.opaque()

    # Check for per-mark settings first
    if phase_mark:
        mark_settings = shader_phase.mark_settings.get(phase_mark)
        if mark_settings:
            if mark_settings.gl_depth_mask is not None:
                state.depth_write = 1 if mark_settings.gl_depth_mask else 0
            if mark_settings.gl_depth_test is not None:
                state.depth_test = 1 if mark_settings.gl_depth_test else 0
            if mark_settings.gl_blend is not None:
                state.blend = 1 if mark_settings.gl_blend else 0
            if mark_settings.gl_cull is not None:
                state.cull = 1 if mark_settings.gl_cull else 0
            return state

    # Apply phase-level overrides
    if shader_phase.gl_depth_mask is not None:
        state.depth_write = 1 if shader_phase.gl_depth_mask else 0
    if shader_phase.gl_depth_test is not None:
        state.depth_test = 1 if shader_phase.gl_depth_test else 0
    if shader_phase.gl_blend is not None:
        state.blend = 1 if shader_phase.gl_blend else 0
    if shader_phase.gl_cull is not None:
        state.cull = 1 if shader_phase.gl_cull else 0

    return state


def _apply_uniform_defaults(phase, shader_phase, uniforms: dict):
    """Apply uniform defaults from shader phase and extra uniforms."""
    from termin.geombase import Vec3, Vec4

    shader_uniforms = list(shader_phase.uniforms) + list(shader_phase.material_uniforms)

    # Apply defaults from shader phase properties and non-inspector uniforms
    for prop in shader_uniforms:
        name = prop.name
        default = prop.default  # Note: binding exposes as 'default', not 'default_value'

        if default is None:
            continue

        prop_type = prop.property_type
        if prop_type == "Float":
            phase.set_uniform_float(name, float(default))
        elif prop_type == "Int":
            phase.set_uniform_int(name, int(default))
        elif prop_type == "Bool":
            phase.set_uniform_int(name, 1 if default else 0)
        elif prop_type == "Vec3" and isinstance(default, (list, tuple)) and len(default) >= 3:
            phase.set_uniform_vec3(name, Vec3(default[0], default[1], default[2]))
        elif prop_type == "Vec4" and isinstance(default, (list, tuple)) and len(default) == 4:
            phase.set_uniform_vec4(name, Vec4(default[0], default[1], default[2], default[3]))
        elif prop_type in ("SrgbColor", "LinearColor") and isinstance(default, (list, tuple)) and len(default) == 4:
            from termin.geombase import LinearColor, SrgbColor
            color_type = SrgbColor if prop_type == "SrgbColor" else LinearColor
            setter = phase.set_uniform_srgb_color if prop_type == "SrgbColor" else phase.set_uniform_linear_color
            setter(name, color_type(*default[:4]))

    # Apply extra uniforms (from .material file)
    for name, value in uniforms.items():
        if isinstance(value, Vec3):
            phase.set_uniform_vec3(name, value)
        elif isinstance(value, Vec4):
            phase.set_uniform_vec4(name, value)
        elif isinstance(value, float):
            phase.set_uniform_float(name, value)
        elif isinstance(value, bool):
            phase.set_uniform_int(name, 1 if value else 0)
        elif isinstance(value, int):
            phase.set_uniform_int(name, value)


def _apply_texture_defaults(phase, shader_phase, rm):
    """Apply default textures from shader phase properties."""
    from termin.render.texture_handle import get_white_texture_handle, get_normal_texture_handle

    shader_uniforms = list(shader_phase.uniforms) + list(shader_phase.material_uniforms)
    for prop in shader_uniforms:
        if prop.property_type != "Texture":
            continue

        name = prop.name
        default = prop.default

        # Get default texture based on property default value
        if isinstance(default, str) and default == "normal":
            texture = get_normal_texture_handle()
        else:
            texture = get_white_texture_handle()

        if texture is not None and texture.is_valid:
            phase.set_texture(name, texture)
        else:
            log.warn(f"[MaterialAsset] Failed to get default texture for '{name}'")


def _apply_canonical_property_defaults(phase, properties: list[dict], uniforms: dict) -> None:
    """Populate material values from the canonical program schema."""
    from termin.geombase import Mat44, Mat44f, Vec2, Vec3, Vec4

    def apply_value(name: str, prop_type: str, value) -> None:
        if prop_type == "Float":
            phase.set_uniform_float(name, float(value))
        elif prop_type in ("Int", "Bool"):
            phase.set_uniform_int(name, int(value))
        elif prop_type == "Vec2":
            vector = value if isinstance(value, Vec2) else Vec2(*value[:2])
            phase.set_uniform_vec2(name, vector)
        elif prop_type == "Vec3":
            vector = value if isinstance(value, Vec3) else Vec3(*value[:3])
            phase.set_uniform_vec3(name, vector)
        elif prop_type == "Vec4":
            vector = value if isinstance(value, Vec4) else Vec4(*value[:4])
            phase.set_uniform_vec4(name, vector)
        elif prop_type in ("SrgbColor", "LinearColor"):
            from termin.geombase import LinearColor, SrgbColor
            color_type = SrgbColor if prop_type == "SrgbColor" else LinearColor
            setter = phase.set_uniform_srgb_color if prop_type == "SrgbColor" else phase.set_uniform_linear_color
            if isinstance(value, color_type):
                color = value
            else:
                if not isinstance(value, (list, tuple)) or len(value) != 4:
                    raise ValueError(f"Material uniform '{name}' ({prop_type}) requires exactly 4 components")
                color = color_type(*value)
            setter(name, color)
        elif prop_type == "Mat4":
            if isinstance(value, (Mat44, Mat44f)):
                matrix = value
            else:
                if len(value) != 16:
                    log.error(
                        f"[MaterialAsset] Mat4 property '{name}' requires 16 default components; "
                        f"got {len(value)}"
                    )
                    raise ValueError(f"Mat4 property '{name}' requires 16 components")
                matrix = Mat44f.zero()
                for column in range(4):
                    for row in range(4):
                        matrix[column, row] = float(value[column * 4 + row])
            phase.set_param(name, matrix)

    property_types = {prop["name"]: prop["property_type"] for prop in properties}
    for prop in properties:
        default = prop.get("default")
        if default is None:
            continue
        apply_value(prop["name"], prop["property_type"], default)

    for name, value in uniforms.items():
        prop_type = property_types.get(name)
        if prop_type is not None:
            apply_value(name, prop_type, value)
        elif isinstance(value, Vec2):
            phase.set_uniform_vec2(name, value)
        elif isinstance(value, Vec3):
            phase.set_uniform_vec3(name, value)
        elif isinstance(value, Vec4):
            phase.set_uniform_vec4(name, value)
        elif isinstance(value, (Mat44, Mat44f)):
            phase.set_param(name, value)
        elif isinstance(value, float):
            phase.set_uniform_float(name, value)
        elif isinstance(value, bool):
            phase.set_uniform_int(name, 1 if value else 0)
        elif isinstance(value, int):
            phase.set_uniform_int(name, value)


def _canonical_texture_properties(properties: list[dict]) -> dict[str, dict]:
    return {
        str(prop["name"]): prop
        for prop in properties
        if prop["property_type"] in ("Texture", "Texture2D")
    }


def _validate_canonical_texture_defaults(properties: list[dict]) -> None:
    for prop in _canonical_texture_properties(properties).values():
        expected_encoding = prop.get("expected_encoding")
        if expected_encoding not in (None, "srgb", "linear"):
            raise ValueError(
                f"Texture property '{prop['name']}' has invalid expected encoding "
                f"'{expected_encoding}'"
            )
        default = prop.get("default")
        if default not in (None, "white", "normal"):
            raise ValueError(
                f"Texture property '{prop['name']}' has unsupported default '{default}'"
            )
        if default == "normal" and expected_encoding == "srgb":
            raise ValueError(
                f"Texture property '{prop['name']}' cannot use normal default with "
                f"{expected_encoding} encoding"
            )


def _declare_canonical_texture_slots(phase, properties: list[dict]) -> None:
    _validate_canonical_texture_defaults(properties)
    for prop in _canonical_texture_properties(properties).values():
        expected_encoding = prop.get("expected_encoding")
        phase.declare_texture(prop["name"], expected_encoding)


def _apply_canonical_texture_defaults(phase, properties: list[dict]) -> None:
    from termin.render.texture_handle import get_normal_texture_handle, get_white_texture_handle

    _declare_canonical_texture_slots(phase, properties)
    for prop in _canonical_texture_properties(properties).values():
        texture = (
            get_normal_texture_handle()
            if prop.get("default") == "normal"
            else get_white_texture_handle(prop.get("expected_encoding") or "linear")
        )
        if texture is not None and texture.is_valid:
            if not phase.set_texture(prop["name"], texture):
                raise ValueError(
                    f"failed to apply default texture for '{prop['name']}'"
                )
        else:
            log.error(
                f"[MaterialAsset] Failed to get default texture for '{prop['name']}'"
            )
            raise RuntimeError(
                f"failed to get default texture for '{prop['name']}'"
            )


def _canonical_render_state(state_data: dict):
    from termin.materials import TcRenderState

    state = TcRenderState()
    state.polygon_mode = state_data["polygon_mode"]
    state.cull = int(state_data["cull"])
    state.depth_test = int(state_data["depth_test"])
    state.depth_write = int(state_data["depth_write"])
    state.blend = int(state_data["blend"])
    state.blend_src = state_data["blend_src"]
    state.blend_dst = state_data["blend_dst"]
    state.depth_func = state_data["depth_func"]
    return state


def _parse_material_content(
    content: str,
    name: str | None = None,
    source_path: str | None = None,
) -> tuple["TcMaterial", str | None]:
    """
    Parse material from JSON content string.

    Args:
        content: JSON content of .material file
        name: Material name (defaults to "material")
        source_path: Source path for the material

    Returns:
        Tuple of (TcMaterial, uuid or None)
    """
    from termin.default_assets.render.texture_asset import TextureAsset
    from termin_assets import get_resource_manager
    from termin.geombase import LinearColor, SrgbColor, Vec3, Vec4
    from termin.materials import TcMaterial

    data = json.loads(content)

    shader_uuid = data.get("shader_uuid")
    shader_name = data.get("shader", "BlinnPhong")
    file_uuid = data.get("uuid")
    phase_marks = data.get("phase_marks", [])  # Per-phase mark overrides

    rm = get_resource_manager()
    if rm is None:
        log.error("[MaterialAsset] Resource manager is not configured; creating empty material")
        mat = TcMaterial.create(name or "unknown", file_uuid or "")
        mat.shader_name = shader_name
        if source_path:
            mat.source_path = source_path
        return mat, file_uuid

    # Try to load shader by UUID first, fallback to name
    program = None
    if shader_uuid:
        program = rm.get_shader_by_uuid(shader_uuid)
    if program is None:
        program = rm.get_shader(shader_name)

    if program is None:
        log.error(f"[MaterialAsset] Shader not found (uuid={shader_uuid}, name={shader_name}), creating empty material")
        mat = TcMaterial.create(name or "unknown", file_uuid or "")
        mat.shader_name = shader_name
        if source_path:
            mat.source_path = source_path
        return mat, file_uuid

    # Convert uniforms according to the shader schema. A four-component JSON
    # array is ambiguous on its own: retain the declared color semantic rather
    # than eagerly turning every such value into Vec4.
    property_types = {prop["name"]: prop["property_type"] for prop in program.properties}
    uniforms_data = data.get("uniforms", {})
    uniforms: Dict[str, Any] = {}
    for uname, value in uniforms_data.items():
        if isinstance(value, list):
            property_type = property_types.get(uname)
            if property_type in ("SrgbColor", "LinearColor"):
                if len(value) != 4 or not all(
                    isinstance(component, (int, float)) and not isinstance(component, bool) for component in value
                ):
                    log.error(
                        f"[MaterialAsset] Uniform '{uname}' ({property_type}) requires exactly four numeric components"
                    )
                    raise ValueError(f"uniform '{uname}' ({property_type}) requires exactly four numeric components")
                color_type = SrgbColor if property_type == "SrgbColor" else LinearColor
                uniforms[uname] = color_type(*value)
            elif property_type == "Vec4" and len(value) == 4:
                uniforms[uname] = Vec4(*value)
            elif len(value) == 3:
                uniforms[uname] = Vec3(value[0], value[1], value[2])
            elif len(value) == 4:
                uniforms[uname] = Vec4(value[0], value[1], value[2], value[3])
            else:
                uniforms[uname] = [float(v) for v in value]
        else:
            uniforms[uname] = value

    # Load textures by asset UUID
    textures_data = data.get("textures", {})
    textures = {}
    for uniform_name, tex_asset_uuid in textures_data.items():
        asset = rm.get_asset_by_uuid(tex_asset_uuid)
        if isinstance(asset, TextureAsset):
            if asset.texture_data is None and not asset.ensure_loaded():
                log.warning(f"[MaterialAsset] Texture asset failed to load by UUID: {tex_asset_uuid}")
                continue
            if asset.texture_data is None:
                log.warning(f"[MaterialAsset] Texture asset loaded without data: {tex_asset_uuid}")
                continue
            textures[uniform_name] = asset.texture_data
        else:
            log.warning(f"[MaterialAsset] Texture asset not found by UUID: {tex_asset_uuid}")

    # Symbolic non-asset texture references are retained by the material and
    # resolved against the current render context at draw time. In particular,
    # loading a material must not capture a render target from whichever scene
    # happened to be alive first.
    texture_refs = data.get("texture_refs", {})
    normalized_texture_refs = {}
    for uniform_name, ref in texture_refs.items():
        normalized_texture_refs[uniform_name] = _validate_texture_ref(ref)

    # Create TcMaterial
    mat = TcMaterial.create(name or "material", file_uuid or "")
    mat.shader_name = shader_name
    mat.set_shader_program_dependency(program.uuid, program.version)
    if source_path:
        mat.source_path = source_path

    canonical_phases = program.phases
    available_marks = [item["phase_mark"] for item in canonical_phases]
    for i, shader_phase in enumerate(canonical_phases):
        # Determine phase mark (apply override if specified)
        phase_mark = shader_phase["phase_mark"]
        if i < len(phase_marks) and phase_marks[i]:
            phase_mark = phase_marks[i]

        shader = shader_phase["shader"]
        if not shader.is_valid:
            log.error(f"[MaterialAsset] Stale shader phase: {shader_phase['phase_mark']}")
            continue

        phase = mat.add_phase(shader, phase_mark, shader_phase["priority"])

        if phase is None:
            log.error(f"[MaterialAsset] Failed to add phase {i}")
            continue
        phase.state = _canonical_render_state(shader_phase["state"])

        # Set available marks
        phase.set_available_marks(available_marks)

        # Apply uniform defaults
        _apply_canonical_property_defaults(phase, program.properties, uniforms)

        # Set default textures from shader properties
        _apply_canonical_texture_defaults(phase, program.properties)

        # Apply textures from .material file (override defaults)
        for tex_name, tc_tex in textures.items():
            if tc_tex is not None and tc_tex.is_valid:
                if not phase.set_texture(tex_name, tc_tex):
                    raise ValueError(
                        f"failed to bind texture '{tex_name}' in material "
                        f"'{name or 'material'}'"
                    )

    for uniform_name, ref in normalized_texture_refs.items():
        mat.set_texture_source(
            uniform_name,
            ref["kind"],
            ref["target"],
            ref["channel"],
        )

    return mat, file_uuid


def _load_material_file(path: str) -> tuple["TcMaterial", str | None]:
    """
    Load material from .material file.

    Args:
        path: Path to .material file

    Returns:
        Tuple of (TcMaterial, uuid or None)
    """
    path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return _parse_material_content(content, name=path.stem, source_path=str(path))


def _save_material_file(material, path: str | Path, uuid: str) -> None:
    """
    Save material to .material file.

    Args:
        material: TcMaterial to save
        path: Path to save to
        uuid: UUID to include in file
    """
    from termin.materials import TcMaterial
    from termin.geombase import Vec3, Vec4
    from termin.geombase import LinearColor, SrgbColor
    from termin_assets import get_resource_manager

    shader_name = material.shader_name
    rm = get_resource_manager()

    # Get shader UUID from ResourceManager
    shader_uuid = material.shader_program_uuid
    if shader_name and not shader_uuid:
        if rm is None:
            log.warning(f"[MaterialAsset] Resource manager is not configured; saving '{shader_name}' without shader UUID")
        else:
            shader_asset = rm.get_shader_asset(shader_name)
            if shader_asset is not None:
                shader_uuid = shader_asset.uuid

    result: Dict[str, Any] = {
        "uuid": uuid,
        "shader": shader_name,
    }
    if shader_uuid:
        result["shader_uuid"] = shader_uuid

    # For TcMaterial, save phase marks, uniforms, and textures
    if isinstance(material, TcMaterial):
        phase_marks = []
        has_overrides = False
        for i in range(material.phase_count):
            phase = material.get_phase(i)
            if phase:
                available = phase.get_available_marks()
                default_mark = available[0] if available else ""
                if phase.phase_mark != default_mark:
                    phase_marks.append(phase.phase_mark)
                    has_overrides = True
                else:
                    phase_marks.append("")
        if has_overrides:
            result["phase_marks"] = phase_marks

        # Save material-level uniforms aggregated across phases.
        uniforms_data: Dict[str, Any] = {}
        for name, value in material.uniforms.items():
            if isinstance(value, (SrgbColor, LinearColor)):
                uniforms_data[name] = [value.r, value.g, value.b, value.a]
            elif isinstance(value, Vec3):
                uniforms_data[name] = [value.x, value.y, value.z]
            elif isinstance(value, Vec4):
                components = [value.x, value.y, value.z, value.w]
                uniforms_data[name] = components
            elif isinstance(value, (int, float, bool)):
                uniforms_data[name] = value
            elif isinstance(value, tuple):
                uniforms_data[name] = list(value)
        if uniforms_data:
            result["uniforms"] = uniforms_data

        # Save material-level textures. Two destinations:
        #   - `textures`: uniform → asset UUID (regular TextureAsset).
        #   - `texture_refs`: uniform → {kind, target, channel} for non-asset
        #     symbolic render-target color/depth sources.
        textures_data: Dict[str, str] = {}
        texture_refs_data: Dict[str, Dict[str, str]] = {}
        symbolic_sources = dict(material.texture_sources)
        for name, ref in symbolic_sources.items():
            texture_refs_data[name] = {
                "kind": str(ref["kind"]),
                "target": str(ref["target"]),
                "channel": str(ref["channel"]),
            }
        for name, tex in material.textures.items():
            if name in symbolic_sources:
                continue
            if tex is None or not tex.is_valid:
                continue
            tex_name = tex.name
            # Skip default placeholder textures (by name)
            if tex_name in (
                "__white_1x1__",
                "__white_srgb_1x1__",
                "__normal_1x1__",
            ):
                continue
            # Texture handles and assets share one canonical UUID. Resolve by
            # that identity directly: asset names are display metadata and may
            # legitimately be duplicated within a project.
            asset = rm.get_texture_asset_by_uuid(str(tex.uuid or ""))
            if asset is not None:
                textures_data[name] = asset.uuid
                continue
            # Fallback: maybe it's an RT-owned texture. Walk live RTs
            # and match on tc_texture uuid.
            ref = _classify_render_target_texture(tex)
            if ref is not None:
                texture_refs_data[name] = ref
            else:
                log.warning(
                    f"[MaterialAsset] Texture '{name}' was not saved: "
                    f"no TextureAsset or render-target match for tc_uuid={tex.uuid} tc_name='{tex.name}'"
                )
        if textures_data:
            result["textures"] = textures_data
        if texture_refs_data:
            result["texture_refs"] = texture_refs_data

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)


# --- Render-target texture references --------------------------------------
#
# Materials can sample render-target color/depth as textures. RT-owned
# tc_textures don't have a TextureAsset behind them, so they're persisted
# in a separate `texture_refs` section keyed by render-target name.

def _iter_render_targets():
    """Yield (handle, name) for every alive render target in the pool."""
    try:
        # Native module — `termin.render_framework.__init__` does not
        # re-export render_target_pool_list in the app package layout.
        from termin.render_framework._render_framework_native import (
            render_target_pool_list,
        )
    except ImportError:
        log.debug("[MaterialAsset] render_target_pool_list not available, skipping RT texture resolution")
        return
    for h in render_target_pool_list():
        if not h.alive:
            continue
        yield h, h.name


def _classify_render_target_texture(tc_tex) -> Dict[str, str] | None:
    """If `tc_tex` is the color or depth channel of a live render target,
    return a serializable ref dict. Otherwise None.
    """
    if tc_tex is None or not tc_tex.is_valid:
        return None
    target_uuid = tc_tex.uuid
    for h, name in _iter_render_targets():
        if not name:
            continue
        color_tex = h.color_texture
        if color_tex is not None and color_tex.is_valid \
                and color_tex.uuid == target_uuid:
            return {"kind": "render_target", "target": name, "channel": "color"}
        depth_tex = h.depth_texture
        if depth_tex is not None and depth_tex.is_valid \
                and depth_tex.uuid == target_uuid:
            return {"kind": "render_target", "target": name, "channel": "depth"}
    return None


def _validate_texture_ref(ref: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(ref, dict):
        raise ValueError("material texture_ref must be an object")
    kind = ref.get("kind")
    target = ref.get("target")
    channel = ref.get("channel", "color")
    if kind != "render_target":
        raise ValueError(f"unsupported material texture_ref kind '{kind}'")
    if not isinstance(target, str) or not target:
        raise ValueError("render_target texture_ref requires a non-empty target")
    if channel not in ("color", "depth"):
        raise ValueError(
            f"render_target texture_ref '{target}' has unsupported channel '{channel}'"
        )
    return {"kind": kind, "target": target, "channel": channel}
