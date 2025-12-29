"""GPU mesh helper built on top of :mod:`termin.mesh` geometry."""

from __future__ import annotations

from typing import Dict, Optional

from termin.mesh.mesh import Mesh2, Mesh3
from termin.visualization.render.render_context import RenderContext
from termin.visualization.core.mesh_asset import MeshAsset
from termin.visualization.core.mesh_gpu import MeshGPU
from termin.visualization.core.mesh_handle import MeshHandle
from termin.visualization.platform.backends.base import MeshHandle as GPUMeshHandle


class MeshDrawable:
    """
    Рендер-ресурс для 3D-меша.

    Обёртка над MeshHandle (ссылка на MeshAsset) + MeshGPU (GPU handles).
    Сохраняет обратную совместимость с существующим API.
    """

    RESOURCE_KIND = "mesh"

    def __init__(
        self,
        mesh: Mesh3 | MeshAsset | None = None,
        *,
        source_id: Optional[str] = None,
        name: Optional[str] = None,
    ):
        """
        Создаёт MeshDrawable.

        Args:
            mesh: Mesh3 геометрия или MeshAsset
            source_id: Путь к файлу-источнику
            name: Имя ресурса
        """
        # Создаём MeshAsset из входных данных
        if mesh is None:
            asset = MeshAsset(mesh_data=None, name=name or "mesh", source_path=source_id)
        elif isinstance(mesh, MeshAsset):
            asset = mesh
        else:
            # Mesh3
            asset = MeshAsset(
                mesh_data=mesh,
                name=name or source_id or "mesh",
                source_path=source_id,
            )

        # Храним через MeshHandle для единообразия
        self._handle: MeshHandle = MeshHandle.from_asset(asset)
        self._gpu: MeshGPU = MeshGPU()

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
        asset = self._handle.get_asset()
        if asset is not None and asset.source_path is not None:
            return str(asset.source_path)
        return None

    @property
    def name(self) -> Optional[str]:
        """Имя ресурса."""
        asset = self._handle.get_asset()
        return asset.name if asset else None

    @name.setter
    def name(self, value: Optional[str]) -> None:
        """Устанавливает имя."""
        asset = self._handle.get_asset()
        if asset is not None and value is not None:
            asset.name = value

    def set_source_id(self, source_id: str):
        asset = self._handle.get_asset()
        if asset is not None:
            asset.source_path = source_id
            if asset.name == "mesh":
                asset.name = source_id

    # --------- доступ к данным ---------

    @property
    def asset(self) -> MeshAsset | None:
        """Получить MeshAsset."""
        return self._handle.get_asset()

    @property
    def mesh(self) -> Mesh3 | None:
        """Геометрия (Mesh3)."""
        return self._handle.get()

    @mesh.setter
    def mesh(self, value: Mesh3):
        """Устанавливает геометрию."""
        asset = self._handle.get_asset()
        if asset is not None:
            asset.mesh_data = value
            # version автоматически увеличится в asset.mesh_data setter

    # --------- GPU lifecycle ---------

    def upload(self, context: RenderContext):
        """Загрузить в GPU (если ещё не загружено)."""
        mesh = self._handle.get()
        if mesh is None:
            return
        # MeshGPU сам проверит версию и загрузит если нужно
        # Но upload() в старом API не рисует, поэтому просто пропускаем
        # Реальная загрузка произойдёт при draw()

    def draw(self, context: RenderContext):
        """Рисует меш."""
        mesh = self._handle.get()
        asset = self._handle.get_asset()
        if mesh is None:
            return
        version = asset.version if asset else 0
        self._gpu.draw(context, mesh.tc_mesh, version)

    def delete(self):
        """Удаляет GPU ресурсы."""
        self._gpu.delete()

    # --------- сериализация / десериализация ---------

    def serialize(self) -> dict:
        """
        Сериализует меш.

        Сохраняет только ссылку на файл (source_path).
        Inline сериализация удалена.
        """
        asset = self._handle.get_asset()
        if asset is None:
            return {"type": "none"}

        if asset.source_path is not None:
            # Use as_posix() for cross-platform consistency (always forward slashes)
            return {
                "type": "file",
                "source_id": asset.source_path.as_posix(),
            }

        # Без source_path сохраняем имя
        return {
            "type": "named",
            "name": asset.name,
        }

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "MeshDrawable | None":
        """
        Восстанавливает MeshDrawable из сериализованных данных.
        """
        mesh_type = data.get("type", "file")

        if mesh_type == "file":
            source_id = data.get("source_id") or data.get("mesh")
            if source_id and context is not None:
                mesh3 = context.load_mesh(source_id)
                if mesh3 is not None:
                    return cls(mesh3, source_id=source_id, name=source_id)
            return None

        if mesh_type == "named":
            name = data.get("name")
            if name:
                # Создаём пустой drawable, данные загрузятся через ResourceManager
                return cls(mesh=None, name=name)
            return None

        return None

    # --------- утилиты ---------

    @staticmethod
    def from_vertices_indices(vertices, indices) -> "MeshDrawable":
        """
        Быстрая обёртка поверх Mesh3 для случаев, когда
        геометрия создаётся на лету.
        """
        mesh = Mesh3(vertices=vertices, triangles=indices)
        return MeshDrawable(mesh)

    def interleaved_buffer(self):
        """Проброс к геометрии."""
        mesh = self._handle.get()
        if mesh is None:
            return None
        return mesh.interleaved_buffer()

    def get_vertex_layout(self):
        """Проброс к геометрии."""
        mesh = self._handle.get()
        if mesh is None:
            return None
        return mesh.get_vertex_layout()


class Mesh2Drawable:
    """
    Рендер-ресурс для 2D-меша (линии/треугольники в плоскости).
    Аналогично MeshDrawable, но поверх Mesh2.

    TODO: Переделать аналогично MeshDrawable когда понадобится.
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
        self._context_resources: Dict[int, GPUMeshHandle] = {}
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
        from termin.visualization.platform.backends import (
            get_context_make_current,
            get_current_context_key,
        )

        original_ctx = get_current_context_key()

        for ctx_key, handle in self._context_resources.items():
            make_current = get_context_make_current(ctx_key)
            if make_current is not None:
                make_current()
            handle.delete()
        self._context_resources.clear()

        if original_ctx is not None:
            restore = get_context_make_current(original_ctx)
            if restore is not None:
                restore()

    def serialize(self) -> dict:
        if self._source_id is not None:
            return {"mesh": self._source_id}
        raise ValueError(
            "Mesh2Drawable.serialize: не задан source_id."
        )

    @classmethod
    def deserialize(cls, data: dict, context) -> "Mesh2Drawable":
        mesh_id = data["mesh"]
        mesh = context.load_mesh(mesh_id)
        return cls(mesh, source_id=mesh_id, name=mesh_id)

    @staticmethod
    def from_vertices_indices(vertices, indices) -> "Mesh2Drawable":
        mesh = Mesh2(vertices=vertices, indices=indices)
        return Mesh2Drawable(mesh)

    def interleaved_buffer(self):
        return self._mesh.interleaved_buffer()

    def get_vertex_layout(self):
        return self._mesh.get_vertex_layout()
