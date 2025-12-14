"""GPU mesh helper built on top of :mod:`termin.mesh` geometry."""

from __future__ import annotations

from typing import Dict, Optional

from termin.mesh.mesh import Mesh2, Mesh3
from termin.visualization.core.entity import RenderContext
from termin.visualization.platform.backends.base import MeshHandle


class MeshDrawable:
    """
    Рендер-ресурс для 3D-меша.

    Держит ссылку на CPU-геометрию (Mesh3), умеет грузить её в GPU через
    graphics backend, хранит GPU-хендлы per-context, а также метаданные
    ресурса: имя и source_id (путь / идентификатор в системе ресурсов).
    """

    RESOURCE_KIND = "mesh"

    unical_id_counter = 0

    def unical_id() -> int:
        MeshDrawable.unical_id_counter += 1
        return MeshDrawable.unical_id_counter

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
        self.name: Optional[str] = name or source_id or f"mesh_{MeshDrawable.unical_id()}"

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
        handle = context.graphics.create_mesh(self._mesh)
        self._context_resources[ctx] = handle

    def draw(self, context: RenderContext):
        ctx = context.context_key
        if ctx not in self._context_resources:
            self.upload(context)
        handle = self._context_resources[ctx]
        handle.draw()

    def delete(self):
        from termin.visualization.platform.backends.opengl import (
            get_context_make_current,
            get_current_context_key,
        )

        # Запоминаем текущий контекст чтобы восстановить после удаления
        original_ctx = get_current_context_key()

        for ctx_key, handle in self._context_resources.items():
            # Делаем контекст текущим перед удалением VAO
            make_current = get_context_make_current(ctx_key)
            if make_current is not None:
                make_current()
            handle.delete()
        self._context_resources.clear()

        # Восстанавливаем исходный контекст
        if original_ctx is not None:
            restore = get_context_make_current(original_ctx)
            if restore is not None:
                restore()

    # --------- сериализация / десериализация ---------

    def serialize(self) -> dict:
        """
        Сериализует меш.

        Если source_id задан - сохраняет только ссылку на файл.
        Иначе сериализует геометрию inline.
        """
        if self._source_id is not None:
            return {
                "type": "file",
                "source_id": self._source_id,
            }

        # Inline сериализация геометрии
        return {
            "type": "inline",
            "vertices": list(self._mesh.vertices.flatten()) if self._mesh.vertices is not None else [],
            "triangles": list(self._mesh.triangles.flatten()) if self._mesh.triangles is not None else [],
            "normals": list(self._mesh.vertex_normals.flatten()) if self._mesh.vertex_normals is not None else None,
        }

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "MeshDrawable":
        """
        Восстанавливает MeshDrawable из сериализованных данных.
        """
        import numpy as np

        mesh_type = data.get("type", "file")

        if mesh_type == "file":
            source_id = data.get("source_id") or data.get("mesh")
            if context is not None:
                mesh = context.load_mesh(source_id)
                return cls(mesh, source_id=source_id, name=source_id)
            # Без контекста не можем загрузить файл
            return None

        # Inline
        vertices_flat = data.get("vertices", [])
        triangles_flat = data.get("triangles", [])
        normals_flat = data.get("normals")

        vertices = np.array(vertices_flat, dtype=np.float32).reshape(-1, 3)
        triangles = np.array(triangles_flat, dtype=np.int32).reshape(-1, 3)
        normals = None
        if normals_flat is not None:
            normals = np.array(normals_flat, dtype=np.float32).reshape(-1, 3)

        mesh = Mesh3(vertices=vertices, triangles=triangles)
        if normals is not None:
            mesh.vertex_normals = normals

        return cls(mesh, name=data.get("name"))

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
        from termin.visualization.platform.backends.opengl import (
            get_context_make_current,
            get_current_context_key,
        )

        # Запоминаем текущий контекст чтобы восстановить после удаления
        original_ctx = get_current_context_key()

        for ctx_key, handle in self._context_resources.items():
            # Делаем контекст текущим перед удалением VAO
            make_current = get_context_make_current(ctx_key)
            if make_current is not None:
                make_current()
            handle.delete()
        self._context_resources.clear()

        # Восстанавливаем исходный контекст
        if original_ctx is not None:
            restore = get_context_make_current(original_ctx)
            if restore is not None:
                restore()

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
