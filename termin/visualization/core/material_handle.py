"""
MaterialHandle — умная ссылка на материал.

Два режима:
1. Direct — хранит Material напрямую
2. Asset — хранит MaterialAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.core.material import Material
    from termin.visualization.core.material_asset import MaterialAsset


class MaterialHandle(ResourceHandle["Material", "MaterialAsset"]):
    """
    Умная ссылка на материал.

    Использование:
        handle = MaterialHandle.from_direct(material)  # raw Material
        handle = MaterialHandle.from_asset(asset)      # MaterialAsset
        handle = MaterialHandle.from_name("Metal")     # lookup в ResourceManager
    """

    @classmethod
    def from_direct(cls, material: "Material") -> "MaterialHandle":
        """Создать handle с raw Material."""
        handle = cls()
        handle._init_direct(material)
        return handle

    # Alias for backward compatibility
    from_material = from_direct

    @classmethod
    def from_asset(cls, asset: "MaterialAsset") -> "MaterialHandle":
        """Создать handle с MaterialAsset."""
        handle = cls()
        handle._init_asset(asset)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "MaterialHandle":
        """Создать handle по имени (lookup в ResourceManager)."""
        from termin.visualization.core.resources import ResourceManager

        asset = ResourceManager.instance().get_material_asset(name)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    # --- Resource extraction ---

    def _get_resource_from_asset(self, asset: "MaterialAsset") -> "Material | None":
        """Извлечь Material из MaterialAsset."""
        return asset.material

    # --- Convenience accessors ---

    @property
    def material(self) -> "Material | None":
        """Получить Material."""
        return self.get()

    @property
    def asset(self) -> "MaterialAsset | None":
        """Получить MaterialAsset."""
        return self.get_asset()

    def get_material(self) -> "Material":
        """
        Получить Material.

        Returns:
            Material или ErrorMaterial если материал недоступен
        """
        mat = self.get()
        if mat is not None:
            return mat

        from termin.visualization.core.material import get_error_material
        return get_error_material()

    def get_material_or_none(self) -> "Material | None":
        """Получить Material или None если недоступен."""
        return self.get()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw Material."""
        if self._direct is not None and self._direct.source_path:
            return {
                "type": "path",
                "path": str(self._direct.source_path),
            }
        # No source_path - can't serialize raw material without file
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "MaterialHandle":
        """Десериализация."""
        from termin.visualization.core.material_asset import MaterialAsset

        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "path":
            path = data.get("path")
            if path:
                asset = MaterialAsset.from_file(path)
                return cls.from_asset(asset)

        return cls()
