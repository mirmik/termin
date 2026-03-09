"""GPU mesh helper built on top of :mod:`termin.mesh` geometry."""

from __future__ import annotations

from typing import Dict, Optional

from termin.mesh.mesh import Mesh2, Mesh3
from termin.mesh import TcMesh
from termin.visualization.render.render_context import RenderContext
from termin.visualization.core.mesh_asset import MeshAsset
from tgfx import GPUMeshHandle  # GPU backend mesh handle


class MeshDrawable:
    """DEAD CODE. Use TcMesh + MeshRenderer directly.

    Kept for import compatibility. Do not use in new code.
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

        self._asset: MeshAsset = asset

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
        if self._asset.source_path is not None:
            return str(self._asset.source_path)
        return None

    @property
    def name(self) -> Optional[str]:
        """Имя ресурса."""
        return self._asset.name

    @name.setter
    def name(self, value: Optional[str]) -> None:
        """Устанавливает имя."""
        if value is not None:
            self._asset.name = value

    def set_source_id(self, source_id: str):
        self._asset.source_path = source_id
        if self._asset.name == "mesh":
            self._asset.name = source_id

    # --------- доступ к данным ---------

    @property
    def asset(self) -> MeshAsset:
        """Получить MeshAsset."""
        return self._asset

    @property
    def mesh(self) -> TcMesh | None:
        """Геометрия (TcMesh)."""
        return self._asset.mesh_data

    @mesh.setter
    def mesh(self, value: Mesh3):
        """Устанавливает геометрию."""
        # Create TcMesh from Mesh3 with asset's UUID
        tc_mesh = TcMesh.from_mesh3(value, self._asset.name, self._asset._uuid)
        self._asset.mesh_data = tc_mesh

    # --------- GPU lifecycle ---------

    def upload(self, context: RenderContext):
        """Загрузить в GPU (если ещё не загружено)."""
        tc_mesh = self._asset.mesh_data
        if tc_mesh is None or not tc_mesh.is_valid:
            return
        tc_mesh.upload_gpu()

    def draw(self, context: RenderContext):
        """Рисует меш."""
        tc_mesh = self._asset.mesh_data
        if tc_mesh is None or not tc_mesh.is_valid:
            from tcbase import log
            log.warn(f"MeshDrawable.draw: invalid mesh (asset={self._asset})")
            return
        tc_mesh.draw_gpu()

    def delete(self):
        """Удаляет GPU ресурсы (no-op, handled by tc_mesh)."""
        pass

    # --------- сериализация / десериализация ---------

    def serialize(self) -> dict:
        """
        Сериализует меш.

        Сохраняет только ссылку на файл (source_path).
        Inline сериализация удалена.
        """
        if self._asset.source_path is not None:
            # Use as_posix() for cross-platform consistency (always forward slashes)
            return {
                "type": "file",
                "source_id": self._asset.source_path.as_posix(),
            }

        # Без source_path сохраняем имя
        return {
            "type": "named",
            "name": self._asset.name,
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
        tc_mesh = self._asset.mesh_data
        if tc_mesh is None or not tc_mesh.is_valid:
            return None
        return tc_mesh.interleaved_buffer()

    def get_vertex_layout(self):
        """Проброс к геометрии."""
        tc_mesh = self._asset.mesh_data
        if tc_mesh is None or not tc_mesh.is_valid:
            return None
        return tc_mesh.get_vertex_layout()


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
        self._handle: GPUMeshHandle | None = None
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
        if self._handle is not None:
            return
        self._handle = context.graphics.create_mesh(self._mesh)

    def draw(self, context: RenderContext):
        if self._handle is None:
            self.upload(context)
        self._handle.draw()

    def delete(self):
        if self._handle is not None:
            self._handle.delete()
            self._handle = None

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
