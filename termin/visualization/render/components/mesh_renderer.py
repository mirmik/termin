from __future__ import annotations

from typing import List, Set, TYPE_CHECKING
from termin.mesh.mesh import Mesh3
from termin.editor.inspect_field import InspectField
from termin.visualization.core.entity import Component, RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.material_handle import MaterialHandle
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.core.resources import ResourceManager
from termin.visualization.render.lighting.upload import upload_lights_to_shader, upload_ambient_to_shader
from termin.visualization.render.lighting.shadow_upload import upload_shadow_maps_to_shader
from termin.visualization.render.renderpass import RenderState

if TYPE_CHECKING:
    from termin.visualization.core.material import MaterialPhase


# Стандартные phase marks для обычных объектов
DEFAULT_PHASE_MARKS: Set[str] = {"opaque", "shadow"}


class MeshRenderer(Component):
    """
    Renderer component that draws MeshDrawable.

    Implements the Drawable protocol for use with ColorPass, ShadowPass, IdPass.

    Атрибуты:
        mesh: Геометрия для отрисовки.
        material: Материал для рендеринга (через MaterialHandle).
        phase_marks: Множество фаз, в которых участвует этот renderer.
                     По умолчанию {"opaque", "shadow"}.
                     Для редакторских объектов: {"editor"}.
                     "shadow" означает, что объект отбрасывает тень.
    """

    inspect_fields = {
        "mesh": InspectField(
            path="mesh",
            label="Mesh",
            kind="mesh",
            setter=lambda obj, value: obj.update_mesh(value),
        ),
        "material": InspectField(
            path="material",
            label="Material",
            kind="material",
            setter=lambda obj, value: obj.set_material_by_name(value.name) if value else obj.set_material(None),
        ),
    }

    def __init__(
        self,
        mesh: MeshDrawable | None = None,
        material: Material | None = None,
        phase_marks: Set[str] | None = None,
    ):
        super().__init__(enabled=True)

        if isinstance(mesh, Mesh3):
            mesh = MeshDrawable(mesh)

        self.mesh = mesh
        self.phase_marks: Set[str] = phase_marks if phase_marks is not None else set(DEFAULT_PHASE_MARKS)

        # Материал через handle для hot-reload
        self._material_handle: MaterialHandle = MaterialHandle()
        if material is not None:
            self._material_handle = MaterialHandle.from_material(material)

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

    def update_mesh(self, mesh: MeshDrawable | None):
        """Устанавливает меш."""
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

    def _ensure_material(self) -> Material:
        """Ленивая инициализация материала."""
        mat = self._material_handle.get_or_none()
        if mat is None:
            mat = Material()
            self._material_handle = MaterialHandle.from_material(mat)
        return mat

    def draw_geometry(self, context: RenderContext) -> None:
        """
        Рисует только геометрию (шейдер уже привязан пассом).

        Это метод из Drawable протокола.

        Параметры:
            context: Контекст рендеринга.
        """
        if self.mesh is None:
            return
        self.mesh.draw(context)

    def get_phases(self, phase_mark: str | None = None) -> List["MaterialPhase"]:
        """
        Возвращает MaterialPhases для указанной метки фазы.

        Это метод из Drawable протокола. Используется ColorPass.

        Логика:
        - Если phase_mark задан и НЕ входит в self.phase_marks, возвращает []
        - Если phase_mark входит в self.phase_marks, возвращает все фазы материала
          (игнорирует phase_mark материала — это позволяет использовать любой
          материал с любым renderer'ом)

        Параметры:
            phase_mark: Метка фазы ("opaque", "editor", etc.)
                        Если None, возвращает все фазы.

        Возвращает:
            Список MaterialPhase отсортированный по priority.
        """
        # Проверяем, что запрошенная фаза есть в наших phase_marks
        if phase_mark is not None and phase_mark not in self.phase_marks:
            return []

        mat = self._ensure_material()

        # Возвращаем все фазы материала (игнорируем phase_mark материала)
        result = list(mat.phases)
        result.sort(key=lambda p: p.priority)
        return result

    # --- сериализация ---

    def serialize_data(self) -> dict:
        """Сериализует MeshRenderer."""
        rm = ResourceManager.instance()

        data = {
            "enabled": self.enabled,
        }

        # Mesh
        if self.mesh is not None:
            mesh_name = rm.find_mesh_name(self.mesh)
            if mesh_name:
                data["mesh"] = mesh_name
            elif self.mesh.name:
                data["mesh"] = self.mesh.name

        # Material
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

        # Mesh
        mesh = None
        mesh_name = data.get("mesh")
        if mesh_name:
            mesh = rm.get_mesh(mesh_name)

        # Material
        material = None
        mat_name = data.get("material")
        if mat_name:
            material = rm.get_material(mat_name)

        # Legacy: поддержка старого формата с passes
        if material is None and "passes" in data:
            passes_data = data.get("passes", [])
            if passes_data:
                mat_name = passes_data[0].get("material")
                if mat_name:
                    material = rm.get_material(mat_name)

        renderer = cls(mesh=mesh, material=material)
        renderer.enabled = data.get("enabled", True)

        # Устанавливаем материал по имени для hot-reload
        if mat_name:
            renderer.set_material_by_name(mat_name)

        return renderer
