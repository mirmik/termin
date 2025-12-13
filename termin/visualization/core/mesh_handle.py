"""
MeshHandle и MeshKeeper — система управления ссылками на меши.

MeshHandle — легковесная ссылка на меш для MeshRenderer.
MeshKeeper — владелец меша по имени, управляет жизненным циклом.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from termin.visualization.core.mesh import MeshDrawable


class MeshKeeper:
    """
    Владелец меша по имени.

    Создаётся ResourceManager'ом при первом обращении к имени.
    Хранит меш, знает источник (файл), контролирует конфликты.
    """

    def __init__(self, name: str):
        self.name = name
        self._mesh: MeshDrawable | None = None
        self._source_path: str | None = None

    @property
    def mesh(self) -> MeshDrawable | None:
        """Текущий меш или None если не загружен."""
        return self._mesh

    @property
    def source_path(self) -> str | None:
        """Путь к файлу-источнику меша."""
        return self._source_path

    @property
    def has_mesh(self) -> bool:
        """Есть ли меш."""
        return self._mesh is not None

    def set_mesh(self, mesh: MeshDrawable, source_path: str | None = None) -> None:
        """
        Установить меш.

        Args:
            mesh: Меш
            source_path: Путь к файлу-источнику (для контроля конфликтов)
        """
        # Удаляем старый меш из GPU если был
        if self._mesh is not None:
            self._mesh.delete()

        self._mesh = mesh
        if source_path is not None:
            self._source_path = source_path

    def update_mesh(self, mesh: MeshDrawable) -> None:
        """
        Обновить меш (hot-reload).

        Заменяет меш, удаляя старый из GPU.
        """
        if self._mesh is not None:
            self._mesh.delete()
        self._mesh = mesh

    def clear(self) -> None:
        """Удалить меш из keeper'а."""
        if self._mesh is not None:
            self._mesh.delete()
        self._mesh = None
        self._source_path = None


class MeshHandle:
    """
    Умная ссылка на меш.

    Два режима работы:
    1. Direct — хранит прямую ссылку на MeshDrawable (создан из кода)
    2. Named — хранит ссылку на MeshKeeper (по имени из ResourceManager)

    MeshRenderer хранит MeshHandle, а не MeshDrawable напрямую.
    """

    def __init__(self):
        self._direct_mesh: MeshDrawable | None = None
        self._keeper: MeshKeeper | None = None
        self._name: str | None = None

    @classmethod
    def from_mesh(cls, mesh: MeshDrawable) -> "MeshHandle":
        """Создать handle с прямой ссылкой на меш."""
        handle = cls()
        handle._direct_mesh = mesh
        return handle

    @classmethod
    def from_name(cls, name: str) -> "MeshHandle":
        """Создать handle по имени меша."""
        from termin.visualization.core.resources import ResourceManager

        handle = cls()
        handle._name = name
        handle._keeper = ResourceManager.instance().get_or_create_mesh_keeper(name)
        return handle

    @property
    def is_direct(self) -> bool:
        """True если это прямая ссылка на меш."""
        return self._direct_mesh is not None

    @property
    def is_named(self) -> bool:
        """True если это ссылка по имени."""
        return self._keeper is not None

    @property
    def name(self) -> str | None:
        """Имя меша (для named) или None (для direct)."""
        if self._direct_mesh is not None:
            return self._direct_mesh.name
        return self._name

    def get(self) -> MeshDrawable | None:
        """
        Получить меш.

        Returns:
            MeshDrawable или None если меш недоступен
        """
        # Direct mode
        if self._direct_mesh is not None:
            return self._direct_mesh

        # Named mode
        if self._keeper is not None and self._keeper.has_mesh:
            return self._keeper.mesh

        return None

    def get_or_none(self) -> MeshDrawable | None:
        """Получить меш или None если недоступен."""
        return self.get()

    def serialize(self) -> dict:
        """Сериализация для сохранения сцены."""
        if self._direct_mesh is not None:
            # Direct mesh — сериализуем сам меш
            return {
                "type": "direct",
                "mesh": self._direct_mesh.serialize(),
            }
        elif self._name is not None:
            # Named — сохраняем только имя
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

        # Fallback — пустой handle
        return cls()
