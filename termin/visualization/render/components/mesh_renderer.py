from __future__ import annotations

from typing import List, Set, TYPE_CHECKING
from termin.mesh.mesh import Mesh3
from termin.editor.inspect_field import InspectField
from termin.visualization.core.entity import Component, RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.material_handle import MaterialHandle
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.core.resources import ResourceManager
from termin.visualization.render.drawable import GeometryDrawCall

if TYPE_CHECKING:
    pass


class MeshRenderer(Component):
    """
    Renderer component that draws MeshDrawable.

    Атрибуты:
        mesh: Геометрия для отрисовки.
        material: Материал для рендеринга.
        cast_shadow: Отбрасывает ли объект тень (добавляет "shadow" в phase_marks).

    Фильтрация по фазам:
        phase_marks = фазы из материала + {"shadow"} если cast_shadow.
        get_phases(phase_mark) возвращает MaterialPhase с совпадающим phase_mark.
    """

    inspect_fields = {
        "mesh": InspectField(
            path="mesh",
            label="Mesh",
            kind="mesh",
            setter=lambda obj, value: obj.set_mesh(value),
        ),
        "material": InspectField(
            path="material",
            label="Material",
            kind="material",
            setter=lambda obj, value: obj.set_material(value),
        ),
        "cast_shadow": InspectField(
            path="cast_shadow",
            label="Cast Shadow",
            kind="bool",
        ),
    }

    _DEBUG_INIT = False

    def __init__(
        self,
        mesh: MeshDrawable | Mesh3 | None = None,
        material: Material | None = None,
        cast_shadow: bool = True,
    ):
        super().__init__(enabled=True)

        if self._DEBUG_INIT:
            print(f"[MeshRenderer.__init__] mesh={mesh}, material={material}")

        self._mesh: MeshDrawable | None = None
        if mesh is not None:
            if isinstance(mesh, Mesh3):
                self._mesh = MeshDrawable(mesh)
            else:
                self._mesh = mesh

        self.cast_shadow = cast_shadow

        self._material_handle: MaterialHandle = MaterialHandle()
        if material is not None:
            self._material_handle = MaterialHandle.from_material(material)
            if self._DEBUG_INIT:
                print(f"  Created MaterialHandle from material: _direct={self._material_handle._direct}")

    @property
    def phase_marks(self) -> Set[str]:
        """
        Возвращает множество phase_marks для этого renderer'а.

        Собирается из:
        - phase_mark каждой фазы материала
        - "shadow" если cast_shadow=True
        """
        marks: Set[str] = set()

        mat = self._material_handle.get_material_or_none()
        if mat:
            for phase in mat.phases:
                marks.add(phase.phase_mark)

        if self.cast_shadow:
            marks.add("shadow")

        return marks

    @property
    def material(self) -> Material | None:
        """Возвращает текущий материал."""
        return self._material_handle.get_material_or_none()

    @material.setter
    def material(self, value: Material | None):
        """Устанавливает материал."""
        if value is None:
            self._material_handle = MaterialHandle()
        else:
            self._material_handle = MaterialHandle.from_material(value)

    @property
    def mesh(self) -> MeshDrawable | None:
        """Возвращает текущий меш."""
        return self._mesh

    @mesh.setter
    def mesh(self, value: MeshDrawable | Mesh3 | None):
        """Устанавливает меш."""
        if value is None:
            self._mesh = None
        elif isinstance(value, Mesh3):
            self._mesh = MeshDrawable(value)
        else:
            self._mesh = value

    def set_mesh(self, mesh: MeshDrawable | Mesh3 | None):
        """Устанавливает меш напрямую."""
        self.mesh = mesh

    def set_mesh_by_name(self, name: str):
        """
        Устанавливает меш по имени из ResourceManager.
        Меш загружается из ResourceManager и оборачивается в MeshDrawable.
        """
        rm = ResourceManager.instance()
        asset = rm.get_mesh_asset(name)
        if asset is not None:
            self._mesh = MeshDrawable(asset)
        else:
            self._mesh = None

    def update_mesh(self, mesh: MeshDrawable | Mesh3 | None):
        """Устанавливает меш (legacy alias)."""
        self.mesh = mesh

    def set_material(self, material: Material | None):
        """Устанавливает материал напрямую."""
        self.material = material

    def set_material_by_name(self, name: str):
        """
        Устанавливает материал по имени из ResourceManager.
        Материал будет автоматически обновляться при hot-reload.
        """
        self._material_handle = MaterialHandle.from_name(name)

    # --- рендеринг ---

    def draw_geometry(self, context: RenderContext, geometry_id: str = "") -> None:
        """Рисует геометрию (шейдер уже привязан пассом)."""
        # geometry_id игнорируется — у MeshRenderer одна геометрия
        if self.mesh is None:
            return
        self.mesh.draw(context)

    _DEBUG_DRAWS = False  # DEBUG: отладка get_geometry_draws

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """
        Возвращает GeometryDrawCalls для указанной метки фазы.

        Параметры:
            phase_mark: Фильтр по метке ("opaque", "transparent", "editor", etc.)
                        Если None, возвращает все фазы.

        Возвращает:
            Список GeometryDrawCall с совпадающим phase_mark, отсортированный по priority.
        """
        mat = self._material_handle.get_material_or_none()
        if self._DEBUG_DRAWS:
            entity_name = self.entity.name if self.entity else "no_entity"
            print(f"[MeshRenderer.get_geometry_draws] entity={entity_name!r}, phase_mark={phase_mark!r}")
            print(f"  _material_handle._direct={self._material_handle._direct}")
            print(f"  _material_handle._asset={self._material_handle._asset}")
            print(f"  mat={mat}")
            if mat:
                print(f"  mat.phases={[(p.phase_mark, type(p.shader_programm).__name__) for p in mat.phases]}")
        if mat is None:
            return []

        if phase_mark is None:
            phases = list(mat.phases)
        else:
            phases = [p for p in mat.phases if p.phase_mark == phase_mark]

        phases.sort(key=lambda p: p.priority)
        return [GeometryDrawCall(phase=p) for p in phases]

    # --- сериализация ---

    def serialize_data(self) -> dict:
        """Сериализует MeshRenderer."""
        rm = ResourceManager.instance()

        data = {
            "enabled": self.enabled,
            "cast_shadow": self.cast_shadow,
        }

        if self.mesh is not None:
            # Try to save UUID, fallback to name
            mesh_uuid = rm.find_mesh_uuid(self.mesh)
            if mesh_uuid:
                data["mesh"] = {"uuid": mesh_uuid}
            else:
                mesh_name = rm.find_mesh_name(self.mesh)
                if mesh_name:
                    data["mesh"] = mesh_name
                elif self.mesh.name:
                    data["mesh"] = self.mesh.name

        mat = self._material_handle.get_material_or_none()
        if mat is not None:
            # Try to save UUID, fallback to name
            mat_uuid = rm.find_material_uuid(mat)
            if mat_uuid:
                data["material"] = {"uuid": mat_uuid}
            else:
                mat_name = rm.find_material_name(mat)
                if mat_name:
                    data["material"] = mat_name
                elif mat.name:
                    data["material"] = mat.name

        return data

