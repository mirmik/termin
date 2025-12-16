"""MaterialAsset - Asset for material configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

import numpy as np

from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    from termin.visualization.core.material import Material


class MaterialAsset(Asset):
    """
    Asset for material configuration.

    Stores Material (shader reference, uniforms, textures).
    MaterialAsset handles resource management (UUID, version, loading).
    Material is used in render logic.
    """

    def __init__(
        self,
        material: "Material | None" = None,
        name: str = "material",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize MaterialAsset.

        Args:
            material: Material instance (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to .material file for loading/reloading
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._material: "Material | None" = material
        self._loaded = material is not None

    @property
    def material(self) -> "Material | None":
        """Material configuration."""
        return self._material

    @material.setter
    def material(self, value: "Material | None") -> None:
        """Set material and bump version."""
        self._material = value
        self._loaded = value is not None
        self._bump_version()

    def load(self) -> bool:
        """
        Load material from source_path.

        Returns:
            True if loaded successfully.
        """
        if self._source_path is None:
            return False

        try:
            with open(self._source_path, "r", encoding="utf-8") as f:
                content = f.read()
            return self.load_from_content(content)
        except Exception:
            return False

    def load_from_content(self, content: str | None) -> bool:
        """
        Load material from JSON content string.

        Args:
            content: JSON content of .material file

        Returns:
            True if loaded successfully.
        """
        if content is None:
            return False

        try:
            material, file_uuid = parse_material_content(
                content,
                name=self._name,
                source_path=str(self._source_path) if self._source_path else None,
            )
            self._material = material

            if file_uuid:
                # File has UUID - adopt it (may differ from ours if file was edited)
                self._uuid = file_uuid
            else:
                # Old file without UUID - save immediately to persist our UUID
                self.save_to_file()

            self._loaded = True
            return True
        except Exception as e:
            print(f"[MaterialAsset] Failed to parse content: {e}")
            return False

    def unload(self) -> None:
        """Unload material to free memory."""
        self._material = None
        self._loaded = False

    def save_to_file(self, path: str | Path | None = None) -> bool:
        """
        Save material to .material file.

        Args:
            path: Path to save. If None, uses source_path.

        Returns:
            True if saved successfully.
        """
        if self._material is None:
            return False

        save_path = Path(path) if path else self._source_path
        if save_path is None:
            return False

        try:
            save_material_file(self._material, save_path, uuid=self.uuid)
            self._source_path = Path(save_path)
            self.mark_just_saved()
            return True
        except Exception:
            return False

    def update_from(self, other: "MaterialAsset") -> None:
        """
        Update material data from another asset (hot-reload).

        Preserves identity of this asset but updates material content.
        """
        if other._material is not None:
            if self._material is not None:
                self._material.update_from(other._material)
            else:
                self._material = other._material
            self._loaded = True
            self._bump_version()

    # --- Factory methods ---

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "MaterialAsset":
        """Create MaterialAsset from .material file."""
        path = Path(path)
        material, file_uuid = load_material_file(str(path))
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

def parse_material_content(
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
    from termin.visualization.core.resources import ResourceManager

    data = json.loads(content)

    shader_name = data.get("shader", "DefaultShader")
    file_uuid = data.get("uuid")

    rm = ResourceManager.instance()
    program = rm.get_shader(shader_name)

    if program is None:
        raise ValueError(f"Shader '{shader_name}' not found in ResourceManager")

    # Convert uniforms
    uniforms_data = data.get("uniforms", {})
    uniforms: Dict[str, Any] = {}
    for uname, value in uniforms_data.items():
        if isinstance(value, list):
            uniforms[uname] = np.array(value, dtype=np.float32)
        else:
            uniforms[uname] = value

    # Load textures by name from ResourceManager
    textures_data = data.get("textures", {})
    textures = {}
    for uniform_name, tex_name in textures_data.items():
        tex = rm.get_texture(tex_name)
        if tex is not None:
            textures[uniform_name] = tex

    # Create material
    mat = Material.from_parsed(
        program,
        uniforms=uniforms,
        textures=textures if textures else None,
        name=name or "material",
        source_path=source_path,
    )
    mat.shader_name = shader_name

    return mat, file_uuid


def load_material_file(path: str) -> tuple["Material", str | None]:
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

    return parse_material_content(content, name=path.stem, source_path=str(path))


def save_material_file(material: "Material", path: str | Path, uuid: str) -> None:
    """
    Save material to .material file.

    Args:
        material: Material to save
        path: Path to save to
        uuid: UUID to include in file
    """
    from termin.visualization.core.resources import ResourceManager

    def serialize_value(val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
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
    if uniforms:
        result["uniforms"] = uniforms
    if textures:
        result["textures"] = textures

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
