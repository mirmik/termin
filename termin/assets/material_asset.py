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

from termin.assets.data_asset import DataAsset
from termin._native import log

if TYPE_CHECKING:
    from termin._native.render import TcMaterial


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
                pass

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
            uuid=uuid,
        )


# --- File I/O functions ---

def _build_render_state(shader_phase, phase_mark: str | None = None):
    """Build tc_render_state from shader phase flags."""
    from termin._native.render import TcRenderState

    # Start with default based on phase mark
    mark = phase_mark or shader_phase.phase_mark
    if mark == "transparent":
        state = TcRenderState.transparent()
    elif mark == "wireframe":
        state = TcRenderState.wireframe()
    else:
        state = TcRenderState.opaque()

    # Check for per-mark settings first
    if phase_mark and hasattr(shader_phase, 'mark_settings'):
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

    # Apply defaults from shader phase properties
    for prop in shader_phase.uniforms:
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
        elif prop_type in ("Vec4", "Color") and isinstance(default, (list, tuple)) and len(default) >= 4:
            phase.set_uniform_vec4(name, Vec4(default[0], default[1], default[2], default[3]))

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
    from termin.assets.texture_handle import get_white_texture_handle, get_normal_texture_handle

    for prop in shader_phase.uniforms:
        if prop.property_type != "Texture":
            continue

        name = prop.name
        default = prop.default

        # Get default texture based on property default value
        if isinstance(default, str) and default == "normal":
            tex_handle = get_normal_texture_handle()
        else:
            tex_handle = get_white_texture_handle()

        tc_tex = tex_handle.get()
        if tc_tex is not None:
            phase.set_texture(name, tc_tex)


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
    from termin._native.render import TcMaterial, TcRenderState
    from termin.assets.resources import ResourceManager
    from termin.geombase import Vec3, Vec4

    data = json.loads(content)

    shader_name = data.get("shader", "DefaultShader")
    file_uuid = data.get("uuid")
    phase_marks = data.get("phase_marks", [])  # Per-phase mark overrides

    rm = ResourceManager.instance()
    program = rm.get_shader(shader_name)

    if program is None:
        log.error(f"[MaterialAsset] Shader '{shader_name}' not found, creating empty material")
        mat = TcMaterial.create(name or "unknown", file_uuid or "")
        mat.shader_name = shader_name
        if source_path:
            mat.source_path = source_path
        return mat, file_uuid

    # Convert uniforms
    uniforms_data = data.get("uniforms", {})
    uniforms: Dict[str, Any] = {}
    for uname, value in uniforms_data.items():
        if isinstance(value, list):
            if len(value) == 3:
                uniforms[uname] = Vec3(value[0], value[1], value[2])
            elif len(value) == 4:
                uniforms[uname] = Vec4(value[0], value[1], value[2], value[3])
            else:
                uniforms[uname] = [float(v) for v in value]
        else:
            uniforms[uname] = value

    # Load textures by name from ResourceManager
    textures_data = data.get("textures", {})
    textures = {}
    for uniform_name, tex_name in textures_data.items():
        tex_handle = rm.get_texture_handle(tex_name)
        if tex_handle is not None:
            textures[uniform_name] = tex_handle

    # Create TcMaterial
    mat = TcMaterial.create(name or "material", file_uuid or "")
    mat.shader_name = shader_name
    if source_path:
        mat.source_path = source_path

    # Create phases from shader
    for i, shader_phase in enumerate(program.phases):
        # Get shader sources
        vertex_source = ""
        fragment_source = ""
        geometry_source = ""

        if "vertex" in shader_phase.stages:
            vertex_source = shader_phase.stages["vertex"].source
        if "fragment" in shader_phase.stages:
            fragment_source = shader_phase.stages["fragment"].source
        if "geometry" in shader_phase.stages:
            geometry_source = shader_phase.stages["geometry"].source

        if not vertex_source or not fragment_source:
            log.warning(f"[MaterialAsset] Phase {i} missing vertex or fragment shader")
            continue

        # Determine phase mark (apply override if specified)
        phase_mark = shader_phase.phase_mark
        if i < len(phase_marks) and phase_marks[i]:
            phase_mark = phase_marks[i]

        # Build render state
        state = _build_render_state(shader_phase, phase_mark)

        # Add phase
        phase = mat.add_phase_from_sources(
            vertex_source=vertex_source,
            fragment_source=fragment_source,
            geometry_source=geometry_source,
            shader_name=shader_name,
            phase_mark=phase_mark,
            priority=shader_phase.priority,
            state=state,
        )

        if phase is None:
            log.error(f"[MaterialAsset] Failed to add phase {i}")
            continue

        # Apply shader features (e.g., lighting_ubo)
        shader = phase.shader
        for feature in program.features:
            if feature == "lighting_ubo":
                shader.set_feature(1)  # TC_SHADER_FEATURE_LIGHTING_UBO = 1
                log.info(f"[MaterialAsset] Applied lighting_ubo feature to shader '{shader_name}'")

        # Set available marks
        if shader_phase.available_marks:
            phase.set_available_marks(shader_phase.available_marks)

        # Apply uniform defaults
        _apply_uniform_defaults(phase, shader_phase, uniforms)

        # Set default textures from shader properties
        _apply_texture_defaults(phase, shader_phase, rm)

        # Apply textures from .material file (override defaults)
        for tex_name, tex_handle in textures.items():
            # TextureHandle.get() returns TcTexture
            tc_tex = tex_handle.get() if tex_handle else None
            if tc_tex is not None:
                phase.set_texture(tex_name, tc_tex)

    return mat, file_uuid


def _load_material_file(path: str) -> tuple["TcMaterial", str | None]:
    """
    Load material from .material file.

    Args:
        path: Path to .material file

    Returns:
        Tuple of (TcMaterial, uuid or None)
    """
    from termin._native.render import TcMaterial
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
    from termin._native.render import TcMaterial

    result: Dict[str, Any] = {
        "uuid": uuid,
        "shader": material.shader_name if hasattr(material, 'shader_name') else "",
    }

    # For TcMaterial, save phase marks if available
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

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
