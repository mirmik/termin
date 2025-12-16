"""
MaterialHandle — умная ссылка на MaterialAsset.

Указывает на MaterialAsset напрямую или по имени через ResourceManager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.core.material import Material
    from termin.visualization.core.material_asset import MaterialAsset


def _get_material_asset(name: str) -> "MaterialAsset | None":
    """Lookup MaterialAsset by name in ResourceManager."""
    from termin.visualization.core.resources import ResourceManager

    return ResourceManager.instance().get_material_asset(name)


class MaterialHandle(ResourceHandle["MaterialAsset"]):
    """
    Умная ссылка на MaterialAsset.

    Использование:
        handle = MaterialHandle.from_asset(asset)     # прямая ссылка на asset
        handle = MaterialHandle.from_material(mat)   # прямая ссылка (создаёт asset)
        handle = MaterialHandle.from_name("Metal")   # по имени (hot-reload)
    """

    _resource_getter = staticmethod(_get_material_asset)

    @classmethod
    def from_asset(cls, asset: "MaterialAsset") -> "MaterialHandle":
        """Создать handle с прямой ссылкой на MaterialAsset."""
        handle = cls()
        handle._init_direct(asset)
        return handle

    @classmethod
    def from_material(cls, material: "Material") -> "MaterialHandle":
        """
        Создать handle из Material (обратная совместимость).

        Создаёт MaterialAsset из Material.
        """
        from termin.visualization.core.material_asset import MaterialAsset

        asset = MaterialAsset.from_material(material)
        return cls.from_asset(asset)

    @classmethod
    def from_name(cls, name: str) -> "MaterialHandle":
        """Создать handle по имени материала."""
        handle = cls()
        handle._init_named(name)
        return handle

    # --- Convenience accessors ---

    def get_asset(self) -> "MaterialAsset | None":
        """Получить MaterialAsset."""
        return self.get()

    @property
    def asset(self) -> "MaterialAsset | None":
        """Алиас для get()."""
        return self.get()

    def get_material(self) -> "Material":
        """
        Получить Material.

        Returns:
            Material или ErrorMaterial если материал недоступен
        """
        asset = self.get()
        if asset is not None and asset.material is not None:
            return asset.material

        from termin.visualization.core.material import get_error_material

        return get_error_material()

    def get_material_or_none(self) -> "Material | None":
        """Получить Material или None если недоступен."""
        asset = self.get()
        if asset is not None:
            return asset.material
        return None

    # --- Serialization ---

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            if self._direct.source_path:
                return {
                    "type": "path",
                    "path": str(self._direct.source_path),
                }
            # No source_path - save by name (material must exist in ResourceManager)
            return {
                "type": "named",
                "name": self._direct.name,
            }
        elif self._name is not None:
            return {
                "type": "named",
                "name": self._name,
            }
        else:
            return {"type": "none"}

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
