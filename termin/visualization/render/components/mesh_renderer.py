from __future__ import annotations

from typing import List, Set, TYPE_CHECKING
from termin.mesh.mesh import Mesh3
from termin.editor.inspect_field import InspectField
from termin.visualization.core.entity import Component, RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.material_handle import MaterialHandle
from termin.visualization.core.mesh_handle import MeshHandle
from termin.visualization.render.drawable import GeometryDrawCall

if TYPE_CHECKING:
    pass


class MeshRenderer(Component):
    """
    Renderer component that draws a mesh.

    Атрибуты:
        mesh: Геометрия для отрисовки (через MeshHandle).
        material: Материал для рендеринга.
        cast_shadow: Отбрасывает ли объект тень (добавляет "shadow" в phase_marks).
        override_material: Если True, используется локальная копия материала
                          с переопределёнными параметрами.

    Фильтрация по фазам:
        phase_marks = фазы из материала + {"shadow"} если cast_shadow.
        get_phases(phase_mark) возвращает MaterialPhase с совпадающим phase_mark.
    """

    inspect_fields = {
        "mesh": InspectField(
            label="Mesh",
            kind="mesh_handle",
            getter=lambda self: self._mesh_handle,
            setter=lambda self, value: self.set_mesh(value),
        ),
        "material": InspectField(
            label="Material",
            kind="material_handle",
            getter=lambda self: self._material_handle,
            setter=lambda self, value: self._set_material_handle(value),
        ),
        "override_material": InspectField(
            path="override_material",
            label="Override Material",
            kind="bool",
            setter=lambda obj, value: obj.set_override_material(value),
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
        mesh: MeshHandle | Mesh3 | None = None,
        material: Material | None = None,
        cast_shadow: bool = True,
        override_material: bool = False,
    ):
        super().__init__(enabled=True)

        if self._DEBUG_INIT:
            print(f"[MeshRenderer.__init__] mesh={mesh}, material={material}")

        self._mesh_handle: MeshHandle = MeshHandle()
        if mesh is not None:
            if isinstance(mesh, Mesh3):
                self._mesh_handle = MeshHandle.from_mesh3(mesh)
            elif isinstance(mesh, MeshHandle):
                self._mesh_handle = mesh

        self.cast_shadow = cast_shadow
        self._override_material: bool = override_material
        self._overridden_material: Material | None = None

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

        mat = self.material
        if mat:
            for phase in mat.phases:
                marks.add(phase.phase_mark)

        if self.cast_shadow:
            marks.add("shadow")

        return marks

    @property
    def override_material(self) -> bool:
        """Возвращает флаг переопределения материала."""
        return self._override_material

    @override_material.setter
    def override_material(self, value: bool) -> None:
        """Устанавливает флаг переопределения материала."""
        self.set_override_material(value)

    def set_override_material(self, value: bool) -> None:
        """
        Устанавливает флаг переопределения материала.

        При активации создаёт локальную копию материала для переопределения.
        При деактивации удаляет локальную копию.
        """
        if value == self._override_material:
            return

        self._override_material = value

        if value:
            # Создаём локальную копию материала
            base_mat = self._material_handle.get_material_or_none()
            if base_mat is not None:
                name = f"{base_mat.name}_override" if base_mat.name else "override"
                self._overridden_material = base_mat.copy(name=name)
            else:
                self._overridden_material = None
        else:
            # Удаляем локальную копию
            self._overridden_material = None

    @property
    def base_material(self) -> Material | None:
        """Возвращает базовый материал (из ассетов)."""
        return self._material_handle.get_material_or_none()

    @base_material.setter
    def base_material(self, value: Material | None) -> None:
        """Устанавливает базовый материал."""
        self.set_base_material(value)

    def set_base_material(self, material: Material | None) -> None:
        """
        Устанавливает базовый материал.

        Если override_material активен, пересоздаёт локальную копию.
        """
        if material is None:
            self._material_handle = MaterialHandle()
        else:
            self._material_handle = MaterialHandle.from_material(material)

        # Если override активен, пересоздаём локальную копию
        if self._override_material:
            base_mat = self._material_handle.get_material_or_none()
            if base_mat is not None:
                name = f"{base_mat.name}_override" if base_mat.name else "override"
                self._overridden_material = base_mat.copy(name=name)
            else:
                self._overridden_material = None

    @property
    def material(self) -> Material | None:
        """
        Возвращает текущий материал для рендеринга.

        Если override_material активен, возвращает локальную копию.
        Иначе возвращает базовый материал из ассетов.
        """
        if self._override_material and self._overridden_material is not None:
            return self._overridden_material
        return self._material_handle.get_material_or_none()

    @material.setter
    def material(self, value: Material | None):
        """Устанавливает материал (для обратной совместимости)."""
        self.set_base_material(value)

    @property
    def overridden_material(self) -> Material | None:
        """
        Возвращает переопределённый материал (локальную копию).

        Возвращает None если override_material не активен.
        """
        if self._override_material:
            return self._overridden_material
        return None

    @property
    def mesh(self) -> MeshHandle:
        """Возвращает MeshHandle."""
        return self._mesh_handle

    @mesh.setter
    def mesh(self, value: MeshHandle | Mesh3 | None):
        """Устанавливает меш."""
        if value is None:
            self._mesh_handle = MeshHandle()
        elif isinstance(value, Mesh3):
            self._mesh_handle = MeshHandle.from_mesh3(value)
        elif isinstance(value, MeshHandle):
            self._mesh_handle = value

    def set_mesh(self, mesh: MeshHandle | Mesh3 | None):
        """Устанавливает меш напрямую."""
        self.mesh = mesh

    def set_mesh_by_name(self, name: str):
        """Устанавливает меш по имени из ResourceManager."""
        self._mesh_handle = MeshHandle.from_name(name)

    def update_mesh(self, mesh: MeshHandle | Mesh3 | None):
        """Устанавливает меш (legacy alias)."""
        self.mesh = mesh

    def set_material(self, material: Material | None):
        """Устанавливает материал напрямую (алиас для set_base_material)."""
        self.set_base_material(material)

    def _set_material_handle(self, handle: MaterialHandle | None):
        """
        Устанавливает материал через MaterialHandle.

        Используется виджетом HandleSelectorWidget.
        """
        if handle is None:
            self._material_handle = MaterialHandle()
        else:
            self._material_handle = handle

        # Если override активен, пересоздаём локальную копию
        if self._override_material:
            base_mat = self._material_handle.get_material_or_none()
            if base_mat is not None:
                name = f"{base_mat.name}_override" if base_mat.name else "override"
                self._overridden_material = base_mat.copy(name=name)
            else:
                self._overridden_material = None

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
        mesh_data = self._mesh_handle.mesh
        gpu = self._mesh_handle.gpu
        if mesh_data is None or gpu is None:
            return
        gpu.draw(context, mesh_data, self._mesh_handle.version)

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
        mat = self.material  # Использует overridden материал если активен
        if self._DEBUG_DRAWS:
            entity_name = self.entity.name if self.entity else "no_entity"
            print(f"[MeshRenderer.get_geometry_draws] entity={entity_name!r}, phase_mark={phase_mark!r}")
            print(f"  _override_material={self._override_material}")
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


