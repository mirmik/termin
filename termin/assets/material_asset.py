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
    from termin.visualization.core.material import Material


class MaterialAsset(DataAsset["Material"]):
    """
    Asset for material configuration.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores Material (shader reference, uniforms, textures).
    """

    _uses_binary = False  # JSON text format

    def __init__(
        self,
        material: "Material | None" = None,
        name: str = "material",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=material, name=name, source_path=source_path, uuid=uuid)

    # --- Convenience property ---

    @property
    def material(self) -> "Material | None":
        """Material configuration (lazy-loaded)."""
        return self.data

    @material.setter
    def material(self, value: "Material | None") -> None:
        """Set material and bump version."""
        self.data = value

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "Material | None":
        """Parse JSON content into Material."""
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

        Preserves identity of this asset but updates material content.
        """
        if other._data is not None:
            if self._data is not None:
                self._data.update_from(other._data)
            else:
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
        material: "Material",
        name: str | None = None,
        source_path: str | Path | None = None,
        uuid: str | None = None,
    ) -> "MaterialAsset":
        """Create MaterialAsset from existing Material."""
        return cls(
            material=material,
            name=name or material.name or "material",
            source_path=source_path or material.source_path,
            uuid=uuid,
        )


# --- File I/O functions ---

def _parse_material_content(
    content: str,
    name: str | None = None,
    source_path: str | None = None,
) -> tuple["Material", str | None]:
    """
    Parse material from JSON content string.

    Args:
        content: JSON content of .material file
        name: Material name (defaults to "material")
        source_path: Source path for the material

    Returns:
        Tuple of (Material, uuid or None)
    """
    from termin.visualization.core.material import Material
    from termin.assets.resources import ResourceManager

    data = json.loads(content)

    shader_name = data.get("shader", "DefaultShader")
    file_uuid = data.get("uuid")
    phase_marks = data.get("phase_marks", [])  # Per-phase mark overrides

    rm = ResourceManager.instance()
    program = rm.get_shader(shader_name)

    if program is None:
        raise ValueError(f"Shader '{shader_name}' not found in ResourceManager")

    # Convert uniforms
    from termin.geombase import Vec3, Vec4

    uniforms_data = data.get("uniforms", {})
    uniforms: Dict[str, Any] = {}
    for uname, value in uniforms_data.items():
        if isinstance(value, list):
            # Convert lists to Vec3/Vec4
            if len(value) == 3:
                uniforms[uname] = Vec3(value[0], value[1], value[2])
            elif len(value) == 4:
                uniforms[uname] = Vec4(value[0], value[1], value[2], value[3])
            else:
                # Keep as list for other sizes (vec2, etc.)
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

    # Create material
    mat = Material.from_parsed(
        program,
        uniforms=uniforms,
        textures=textures if textures else None,
        name=name or "material",
        source_path=source_path,
    )
    mat.shader_name = shader_name

    # Apply per-phase mark overrides (use set_phase_mark to also apply render state)
    for i, mark in enumerate(phase_marks):
        if i < len(mat.phases) and mark:
            mat.phases[i].set_phase_mark(mark)

    return mat, file_uuid


def _load_material_file(path: str) -> tuple["Material", str | None]:
    """
    Load material from .material file.

    Args:
        path: Path to .material file

    Returns:
        Tuple of (Material, uuid or None)
    """
    path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return _parse_material_content(content, name=path.stem, source_path=str(path))


def _save_material_file(material: "Material", path: str | Path, uuid: str) -> None:
    """
    Save material to .material file.

    Args:
        material: Material to save
        path: Path to save to
        uuid: UUID to include in file
    """
    from termin.assets.resources import ResourceManager

    def serialize_value(val: Any) -> Any:
        from termin.geombase import Vec3, Vec4
        if isinstance(val, Vec3):
            return [val.x, val.y, val.z]
        elif isinstance(val, Vec4):
            return [val.x, val.y, val.z, val.w]
        elif isinstance(val, (list, tuple)):
            return [float(v) for v in val]
        return val

    rm = ResourceManager.instance()

    # Collect uniforms from all phases
    uniforms: Dict[str, Any] = {}
    textures: Dict[str, str] = {}

    for phase in material.phases:
        for name, value in phase.uniforms.items():
            if name not in uniforms:
                uniforms[name] = serialize_value(value)
        for name, tex in phase.textures.items():
            if name not in textures:
                tex_name = rm.find_texture_name(tex)
                # Don't save white texture - it's the default
                if tex_name and tex_name != "__white_1x1__":
                    textures[name] = tex_name

    result: Dict[str, Any] = {
        "uuid": uuid,
        "shader": material.shader_name,
    }

    # Save per-phase marks (only if different from default)
    phase_marks = []
    has_overrides = False
    for phase in material.phases:
        default_mark = phase.available_marks[0] if phase.available_marks else ""
        if phase.phase_mark != default_mark:
            phase_marks.append(phase.phase_mark)
            has_overrides = True
        else:
            phase_marks.append("")
    if has_overrides:
        result["phase_marks"] = phase_marks

    if uniforms:
        result["uniforms"] = uniforms
    if textures:
        result["textures"] = textures

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
