"""GPU mesh helper built on top of :mod:`termin.mesh` geometry."""

from __future__ import annotations

from typing import Dict, Optional

from termin.mesh.mesh import Mesh2, Mesh3
from .entity import RenderContext
from .backends.base import MeshHandle


class MeshDrawable:
    """
    Рендер-ресурс для 3D-меша.

    Держит ссылку на CPU-геометрию (Mesh3), умеет грузить её в GPU через
    graphics backend, хранит GPU-хендлы per-context, а также метаданные
    ресурса: имя и source_id (путь / идентификатор в системе ресурсов).
    """

    RESOURCE_KIND = "mesh"

    def __init__(
        self,
        mesh: Mesh3,
        *,
        source_id: Optional[str] = None,
        name: Optional[str] = None,
    ):
        self._mesh: Mesh3 = mesh

        # если нормали ещё не посчитаны — посчитаем здесь, а не в Mesh3
        if self._mesh.vertex_normals is None:
            self._mesh.compute_vertex_normals()

        # GPU-хендлы на разных контекстах
        self._context_resources: Dict[int, MeshHandle] = {}

        # ресурсные метаданные (чтоб Mesh3 о них не знал)
        self._source_id: Optional[str] = source_id
        # name по умолчанию можно взять из source_id, если имя не задано явно
        self.name: Optional[str] = name or source_id

    # --------- интерфейс ресурса ---------

    @property
    def resource_kind(self) -> str:
        return self.RESOURCE_KIND

    @property
    def resource_id(self) -> Optional[str]:
        """
        То, что кладём в сериализацию и по чему грузим обратно.
        Обычно это путь к файлу или GUID.
        """
        return self._source_id

    def set_source_id(self, source_id: str):
        self._source_id = source_id
        # если имени ещё не было — логично синхронизировать
        if self.name is None:
            self.name = source_id

    # --------- доступ к геометрии ---------

    @property
    def mesh(self) -> Mesh3:
        return self._mesh

    @mesh.setter
    def mesh(self, value: Mesh3):
        # при смене геометрии надо будет перевыгрузить в GPU
        self.delete()
        self._mesh = value
        if self._mesh.vertex_normals is None:
            self._mesh.compute_vertex_normals()

    # --------- GPU lifecycle ---------

    def upload(self, context: RenderContext):
        ctx = context.context_key
        if ctx in self._context_resources:
            return
        # backend знает, как из Mesh3 сделать GPU-буферы
        handle = context.graphics.create_mesh(self._mesh)
        self._context_resources[ctx] = handle

    def draw(self, context: RenderContext):
        ctx = context.context_key
        if ctx not in self._context_resources:
            self.upload(context)
        handle = self._context_resources[ctx]
        handle.draw()

    def delete(self):
        for handle in self._context_resources.values():
            handle.delete()
        self._context_resources.clear()

    # --------- сериализация / десериализация ---------

    def serialize(self) -> dict:
        """
        Возвращает словарь с идентификатором ресурса.

        По-хорошему, source_id должен выставлять загрузчик ресурсов
        (например, путь к файлу или GUID). Mesh3 при этом ни о чём
        таком знать не обязан.
        """
        if self._source_id is not None:
            return {"mesh": self._source_id}

        # Для совместимости со старым кодом: если Mesh3 всё-таки
        # имеет поле source_path — используем его, но это считается
        # legacy и лучше постепенно от него избавляться.
        if hasattr(self._mesh, "source_path"):
            return {"mesh": getattr(self._mesh, "source_path")}

        raise ValueError(
            "MeshDrawable.serialize: не задан source_id и у mesh нет source_path. "
            "Нечего сохранять в качестве идентификатора ресурса."
        )

    @classmethod
    def deserialize(cls, data: dict, context) -> "MeshDrawable":
        """
        Восстановление drawable по идентификатору меша.

        Предполагается, что `context.load_mesh(mesh_id)` вернёт Mesh3.
        """
        mesh_id = data["mesh"]
        mesh = context.load_mesh(mesh_id)  # должен вернуть Mesh3
        return cls(mesh, source_id=mesh_id, name=mesh_id)

    # --------- утилиты для инспектора / дебага ---------

    @staticmethod
    def from_vertices_indices(vertices, indices) -> "MeshDrawable":
        """
        Быстрая обёртка поверх Mesh3 для случаев, когда
        геометрия создаётся на лету.
        """
        mesh = Mesh3(vertices=vertices, triangles=indices)
        return MeshDrawable(mesh)

    def interleaved_buffer(self):
        """
        Проброс к геометрии. Формат буфера и layout определяет Mesh3.
        Это всё ещё геометрическая часть, не завязанная на конкретный API.
        """
        return self._mesh.interleaved_buffer()

    def get_vertex_layout(self):
        return self._mesh.get_vertex_layout()


class Mesh2Drawable:
    """
    Рендер-ресурс для 2D-меша (линии/треугольники в плоскости).
    Аналогично MeshDrawable, но поверх Mesh2.
    """

    RESOURCE_KIND = "mesh2"

    def __init__(
        self,
        mesh: Mesh2,
        *,
        source_id: Optional[str] = None,
        name: Optional[str] = None,
    ):
        self._mesh: Mesh2 = mesh
        self._context_resources: Dict[int, MeshHandle] = {}
        self._source_id: Optional[str] = source_id
        self.name: Optional[str] = name or source_id

    @property
    def resource_kind(self) -> str:
        return self.RESOURCE_KIND

    @property
    def resource_id(self) -> Optional[str]:
        return self._source_id

    def set_source_id(self, source_id: str):
        self._source_id = source_id
        if self.name is None:
            self.name = source_id

    @property
    def mesh(self) -> Mesh2:
        return self._mesh

    @mesh.setter
    def mesh(self, value: Mesh2):
        self.delete()
        self._mesh = value

    def upload(self, context: RenderContext):
        ctx = context.context_key
        if ctx in self._context_resources:
            return
        handle = context.graphics.create_mesh(self._mesh)
        self._context_resources[ctx] = handle

    def draw(self, context: RenderContext):
        ctx = context.context_key
        if ctx not in self._context_resources:
            self.upload(context)
        handle = self._context_resources[ctx]
        handle.draw()

    def delete(self):
        for handle in self._context_resources.values():
            handle.delete()
        self._context_resources.clear()

    def serialize(self) -> dict:
        if self._source_id is not None:
            return {"mesh": self._source_id}
        if hasattr(self._mesh, "source_path"):
            return {"mesh": getattr(self._mesh, "source_path")}
        raise ValueError(
            "Mesh2Drawable.serialize: не задан source_id и нет mesh.source_path."
        )

    @classmethod
    def deserialize(cls, data: dict, context) -> "Mesh2Drawable":
        mesh_id = data["mesh"]
        mesh = context.load_mesh(mesh_id)  # должен вернуть Mesh2
        return cls(mesh, source_id=mesh_id, name=mesh_id)

    @staticmethod
    def from_vertices_indices(vertices, indices) -> "Mesh2Drawable":
        mesh = Mesh2(vertices=vertices, indices=indices)
        return Mesh2Drawable(mesh)

    def interleaved_buffer(self):
        return self._mesh.interleaved_buffer()

    def get_vertex_layout(self):
        return self._mesh.get_vertex_layout()
