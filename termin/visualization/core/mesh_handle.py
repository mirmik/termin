"""
MeshKeeper и MeshHandle — управление ссылками на меши.

Наследуются от ResourceKeeper/ResourceHandle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle, ResourceKeeper

if TYPE_CHECKING:
    from termin.visualization.core.mesh import MeshDrawable


class MeshKeeper(ResourceKeeper["MeshDrawable"]):
    """
    Владелец меша по имени.

    Меш требует GPU cleanup через delete().
    """

    @property
    def mesh(self) -> "MeshDrawable | None":
        """Алиас для resource."""
        return self._resource

    @property
    def has_mesh(self) -> bool:
        """Алиас для has_resource."""
        return self.has_resource

    def set_mesh(self, mesh: "MeshDrawable", source_path: str | None = None) -> None:
        """Алиас для set_resource."""
        self.set_resource(mesh, source_path)

    def update_mesh(self, mesh: "MeshDrawable") -> None:
        """Алиас для update_resource."""
        self.update_resource(mesh)


class MeshHandle(ResourceHandle["MeshDrawable"]):
    """
    Умная ссылка на меш.

    Использование:
        handle = MeshHandle.from_mesh(drawable)  # прямая ссылка
        handle = MeshHandle.from_name("cube")    # по имени (hot-reload)
    """

    @classmethod
    def from_mesh(cls, mesh: "MeshDrawable") -> "MeshHandle":
        """Создать handle с прямой ссылкой на меш."""
        handle = cls()
        handle._init_direct(mesh)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "MeshHandle":
        """Создать handle по имени меша."""
        from termin.visualization.core.resources import ResourceManager

        handle = cls()
        keeper = ResourceManager.instance().get_or_create_mesh_keeper(name)
        handle._init_named(name, keeper)
        return handle

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            return {
                "type": "direct",
                "mesh": self._direct.serialize(),
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
        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "direct":
            from termin.visualization.core.mesh import MeshDrawable

            mesh_data = data.get("mesh")
            if mesh_data:
                mesh = MeshDrawable.deserialize(mesh_data, context)
                if mesh is not None:
                    return cls.from_mesh(mesh)

        return cls()
