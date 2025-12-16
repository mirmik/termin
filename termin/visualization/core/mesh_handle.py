"""
MeshHandle — умная ссылка на MeshAsset.

Указывает на MeshAsset напрямую или по имени через ResourceManager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.core.mesh import MeshDrawable
    from termin.visualization.core.mesh_asset import MeshAsset


def _get_mesh_asset(name: str) -> "MeshAsset | None":
    """Lookup MeshAsset by name in ResourceManager."""
    from termin.visualization.core.resources import ResourceManager

    return ResourceManager.instance().get_mesh_asset(name)


class MeshHandle(ResourceHandle["MeshAsset"]):
    """
    Умная ссылка на MeshAsset.

    Использование:
        handle = MeshHandle.from_asset(asset)    # прямая ссылка
        handle = MeshHandle.from_name("cube")    # по имени (hot-reload)
    """

    _resource_getter = staticmethod(_get_mesh_asset)

    @classmethod
    def from_asset(cls, asset: "MeshAsset") -> "MeshHandle":
        """Создать handle с прямой ссылкой на MeshAsset."""
        handle = cls()
        handle._init_direct(asset)
        return handle

    @classmethod
    def from_mesh(cls, drawable: "MeshDrawable") -> "MeshHandle":
        """
        Создать handle из MeshDrawable (обратная совместимость).

        Извлекает MeshAsset из MeshDrawable.
        """
        from termin.visualization.core.mesh import MeshDrawable

        if isinstance(drawable, MeshDrawable):
            asset = drawable.asset
            if asset is not None:
                return cls.from_asset(asset)
        return cls()

    @classmethod
    def from_name(cls, name: str) -> "MeshHandle":
        """Создать handle по имени меша."""
        handle = cls()
        handle._init_named(name)
        return handle

    # --- Convenience accessors ---

    def get_asset(self) -> "MeshAsset | None":
        """Получить MeshAsset."""
        return self.get()

    @property
    def asset(self) -> "MeshAsset | None":
        """Алиас для get()."""
        return self.get()

    # --- Serialization ---

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            return {
                "type": "direct",
                "asset": self._direct.serialize(),
            }
        elif self._name is not None:
            return {
                "type": "named",
                "name": self._name,
            }
        else:
            return {"type": "none"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "MeshHandle":
        """Десериализация."""
        from termin.visualization.core.mesh_asset import MeshAsset

        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "direct":
            asset_data = data.get("asset") or data.get("mesh")
            if asset_data:
                asset = MeshAsset.deserialize(asset_data, context)
                if asset is not None:
                    return cls.from_asset(asset)

        return cls()
