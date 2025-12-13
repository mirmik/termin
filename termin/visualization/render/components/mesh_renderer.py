from __future__ import annotations

from typing import List, Set, TYPE_CHECKING
from termin.mesh.mesh import Mesh3
from termin.editor.inspect_field import InspectField
from termin.visualization.core.entity import Component, RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.material_handle import MaterialHandle
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.core.mesh_handle import MeshHandle
from termin.visualization.core.resources import ResourceManager

if TYPE_CHECKING:
    from termin.visualization.core.material import MaterialPhase


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
            setter=lambda obj, value: obj.set_mesh_by_name(value.name) if value else obj.set_mesh(None),
        ),
        "material": InspectField(
            path="material",
            label="Material",
            kind="material",
            setter=lambda obj, value: obj.set_material_by_name(value.name) if value else obj.set_material(None),
        ),
        "cast_shadow": InspectField(
            path="cast_shadow",
            label="Cast Shadow",
            kind="bool",
        ),
    }

    def __init__(
        self,
        mesh: MeshDrawable | None = None,
        material: Material | None = None,
        cast_shadow: bool = True,
    ):
        super().__init__(enabled=True)

        self._mesh_handle: MeshHandle = MeshHandle()
        if mesh is not None:
            if isinstance(mesh, Mesh3):
                mesh = MeshDrawable(mesh)
            self._mesh_handle = MeshHandle.from_mesh(mesh)

        self.cast_shadow = cast_shadow

        self._material_handle: MaterialHandle = MaterialHandle()
        if material is not None:
            self._material_handle = MaterialHandle.from_material(material)

    @property
    def phase_marks(self) -> Set[str]:
        """
        Возвращает множество phase_marks для этого renderer'а.

        Собирается из:
        - phase_mark каждой фазы материала
        - "shadow" если cast_shadow=True
        """
        marks: Set[str] = set()

        mat = self._material_handle.get_or_none()
        if mat:
            for phase in mat.phases:
                marks.add(phase.phase_mark)

        if self.cast_shadow:
            marks.add("shadow")

        return marks

    @property
    def material(self) -> Material | None:
        """Возвращает текущий материал."""
        return self._material_handle.get_or_none()

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
        return self._mesh_handle.get_or_none()

    @mesh.setter
    def mesh(self, value: MeshDrawable | None):
        """Устанавливает меш."""
        if value is None:
            self._mesh_handle = MeshHandle()
        else:
            self._mesh_handle = MeshHandle.from_mesh(value)

    def set_mesh(self, mesh: MeshDrawable | None):
        """Устанавливает меш напрямую."""
        self.mesh = mesh

    def set_mesh_by_name(self, name: str):
        """
        Устанавливает меш по имени из ResourceManager.
        Меш будет автоматически обновляться при hot-reload.
        """
        self._mesh_handle = MeshHandle.from_name(name)

    def update_mesh(self, mesh: MeshDrawable | None):
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

    def draw_geometry(self, context: RenderContext) -> None:
        """Рисует геометрию (шейдер уже привязан пассом)."""
        if self.mesh is None:
            return
        self.mesh.draw(context)

    def get_phases(self, phase_mark: str | None = None) -> List["MaterialPhase"]:
        """
        Возвращает MaterialPhases для указанной метки фазы.

        Параметры:
            phase_mark: Фильтр по метке ("opaque", "transparent", "editor", etc.)
                        Если None, возвращает все фазы.

        Возвращает:
            Список MaterialPhase с совпадающим phase_mark, отсортированный по priority.
        """
        mat = self._material_handle.get_or_none()
        if mat is None:
            return []

        if phase_mark is None:
            result = list(mat.phases)
        else:
            result = [p for p in mat.phases if p.phase_mark == phase_mark]

        result.sort(key=lambda p: p.priority)
        return result

    # --- сериализация ---

    def serialize_data(self) -> dict:
        """Сериализует MeshRenderer."""
        rm = ResourceManager.instance()

        data = {
            "enabled": self.enabled,
            "cast_shadow": self.cast_shadow,
        }

        if self.mesh is not None:
            mesh_name = rm.find_mesh_name(self.mesh)
            if mesh_name:
                data["mesh"] = mesh_name
            elif self.mesh.name:
                data["mesh"] = self.mesh.name

        mat = self._material_handle.get_or_none()
        if mat is not None:
            mat_name = rm.find_material_name(mat)
            if mat_name:
                data["material"] = mat_name
            elif mat.name:
                data["material"] = mat.name

        return data

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "MeshRenderer":
        """Восстанавливает MeshRenderer из сериализованных данных."""
        rm = ResourceManager.instance()

        mesh = None
        mesh_name = data.get("mesh")
        if mesh_name:
            mesh = rm.get_mesh(mesh_name)

        material = None
        mat_name = data.get("material")
        if mat_name:
            material = rm.get_material(mat_name)

        renderer = cls(
            mesh=mesh,
            material=material,
            cast_shadow=data.get("cast_shadow", True),
        )
        renderer.enabled = data.get("enabled", True)

        # Bind by name for hot-reload support
        if mesh_name:
            renderer.set_mesh_by_name(mesh_name)
        if mat_name:
            renderer.set_material_by_name(mat_name)

        return renderer
