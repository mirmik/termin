"""MaterialAsset - Asset for material configuration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

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
            from termin.visualization.core.material import Material

            self._material = Material.load_from_material_file(str(self._source_path))
            self._loaded = True
            return True
        except Exception:
            return False

    def unload(self) -> None:
        """Unload material to free memory."""
        self._material = None
        self._loaded = False

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

    # --- Serialization ---

    def serialize(self) -> dict:
        """Serialize material asset reference."""
        return {
            "uuid": self.uuid,
            "name": self._name,
            "source_path": str(self._source_path) if self._source_path else None,
        }

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "MaterialAsset":
        """Deserialize material asset (lazy - doesn't load material)."""
        return cls(
            material=None,
            name=data.get("name", "material"),
            source_path=data.get("source_path"),
            uuid=data.get("uuid"),
        )

    # --- Factory methods ---

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "MaterialAsset":
        """Create MaterialAsset from .material file."""
        from termin.visualization.core.material import Material

        material = Material.load_from_material_file(str(path))
        return cls(
            material=material,
            name=name or Path(path).stem,
            source_path=path,
        )

    @classmethod
    def from_material(
        cls,
        material: "Material",
        name: str | None = None,
        source_path: str | Path | None = None,
    ) -> "MaterialAsset":
        """Create MaterialAsset from existing Material."""
        return cls(
            material=material,
            name=name or material.name or "material",
            source_path=source_path or material.source_path,
        )
