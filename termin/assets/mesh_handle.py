"""
MeshHandle — умная ссылка на меш.

Два режима:
1. Direct — хранит Mesh3 напрямую
2. Asset — хранит MeshAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.mesh.mesh import Mesh3
    from termin.visualization.core.mesh_asset import MeshAsset
    from termin.visualization.core.mesh_gpu import MeshGPU


class MeshHandle(ResourceHandle["Mesh3", "MeshAsset"]):
    """
    Умная ссылка на меш.

    Использование:
        handle = MeshHandle.from_direct(mesh)     # raw Mesh3
        handle = MeshHandle.from_asset(asset)     # MeshAsset
        handle = MeshHandle.from_name("cube")     # lookup в ResourceManager
    """

    @classmethod
    def from_direct(cls, mesh: "Mesh3") -> "MeshHandle":
        """Создать handle с raw Mesh3 (без asset, без GPU)."""
        handle = cls()
        handle._init_direct(mesh)
        return handle

    @classmethod
    def from_mesh3(cls, mesh: "Mesh3", name: str = "mesh", source_path: str | None = None) -> "MeshHandle":
        """Создать handle с MeshAsset из Mesh3."""
        from termin.visualization.core.mesh_asset import MeshAsset
        asset = MeshAsset(mesh_data=mesh, name=name, source_path=source_path)
        return cls.from_asset(asset)

    # Alias for backward compatibility
    from_mesh = from_mesh3

    @classmethod
    def from_vertices_indices(cls, vertices, indices, name: str = "mesh") -> "MeshHandle":
        """Создать handle из вершин и индексов."""
        from termin.mesh.mesh import Mesh3
        mesh = Mesh3(vertices=vertices, triangles=indices)
        return cls.from_mesh3(mesh, name=name)

    @classmethod
    def from_asset(cls, asset: "MeshAsset") -> "MeshHandle":
        """Создать handle с MeshAsset."""
        handle = cls()
        handle._init_asset(asset)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "MeshHandle":
        """Создать handle по имени (lookup в ResourceManager)."""
        from termin.assets.resources import ResourceManager

        asset = ResourceManager.instance().get_mesh_asset(name)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    # --- Resource extraction ---

    def _get_resource_from_asset(self, asset: "MeshAsset") -> "Mesh3 | None":
        """Извлечь Mesh3 из MeshAsset (lazy loading внутри asset.data)."""
        return asset.data

    # --- Convenience accessors ---

    @property
    def mesh(self) -> "Mesh3 | None":
        """Получить Mesh3."""
        return self.get()

    @property
    def gpu(self) -> "MeshGPU | None":
        """Получить MeshGPU для рендеринга."""
        if self._asset is not None:
            return self._asset.gpu
        return None

    @property
    def version(self) -> int:
        """Версия данных для отслеживания изменений."""
        if self._asset is not None:
            return self._asset.version
        return 0

    def get_mesh(self) -> "Mesh3 | None":
        """Получить Mesh3."""
        return self.get()

    def get_mesh_or_none(self) -> "Mesh3 | None":
        """Алиас для get_mesh()."""
        return self.get()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw Mesh3 — не поддерживается."""
        # Mesh3 слишком большой для inline сериализации
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "MeshHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "path":
            path = data.get("path")
            if path:
                from termin.visualization.core.mesh_asset import MeshAsset
                asset = MeshAsset(mesh_data=None, source_path=path)
                return cls.from_asset(asset)

        return cls()
