from __future__ import annotations

from typing import Iterable, List, Optional, TYPE_CHECKING
from termin.mesh.mesh import Mesh3
from termin.editor.inspect_field import InspectField
from termin.visualization.core.entity import Component, RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.core.resources import ResourceManager
from termin.visualization.render.lighting.upload import upload_lights_to_shader, upload_ambient_to_shader
from termin.visualization.render.lighting.shadow_upload import upload_shadow_maps_to_shader
from termin.visualization.render.renderpass import RenderState, RenderPass

if TYPE_CHECKING:
    from termin.visualization.core.material import MaterialPhase

class MeshRenderer(Component):
    """Renderer component that draws MeshDrawable with one or multiple passes."""

    inspect_fields = {
        # mesh-инспект мы уже добавляли раньше
        "mesh": InspectField(
            path="mesh",
            label="Mesh",
            kind="mesh",
            # можно прямое присваивание, можно отдельный метод
            setter=lambda obj, value: obj.update_mesh(value),
        ),
        "material": InspectField(
            path="material",
            label="Material",
            kind="material",
            setter=lambda obj, value: obj.update_material(value),
        ),
    }

    def __init__(
        self,
        mesh: MeshDrawable | None = None,
        material: Material | None = None,
        passes: list[RenderPass] | None = None,
    ):
        super().__init__(enabled=True)

        if isinstance(mesh, Mesh3):
            mesh = MeshDrawable(mesh)

        if material is None and passes is None:
            material = Material()

        self.mesh = mesh
        self._material: Material | None = None
        self.passes: list[RenderPass] = []

        if passes is not None:
            # нормализация списка переданных проходов
            for p in passes:
                if isinstance(p, RenderPass):
                    self.passes.append(p)
                elif isinstance(p, Material):
                    self.passes.append(RenderPass(material=p, state=RenderState()))
                else:
                    raise TypeError("passes must contain Material or RenderPass")
        elif material is not None:
            # если материал задан в конструкторе — как раньше: один проход
            self.passes.append(RenderPass(material=material, state=RenderState()))

    @property
    def material(self) -> Material | None:
        """Возвращает материал первого прохода (для обратной совместимости)."""
        if self.passes:
            return self.passes[0].material
        return self._material

    @material.setter
    def material(self, value: Material | None):
        """Устанавливает материал первого прохода."""
        self._material = value
        if self.passes:
            self.passes[0].material = value

    def update_mesh(self, mesh: MeshDrawable | None):
        self.mesh = mesh

    def update_material(self, material: Material | None):
        """
        Вызывается инспектором при смене материала.
        Гарантирует наличие хотя бы одного RenderPass при установке материала.
        """
        if material is not None and not self.passes:
            # Новый компонент, до этого не было проходов — создаём дефолтный
            self.passes.append(RenderPass(material=material, state=RenderState()))
        else:
            # setter обновит первый pass
            self.material = material

    # --- рендеринг ---

    def required_shaders(self):
        for p in self.passes:
            yield p.material.shader

    def draw(self, context: RenderContext):
        if self.entity is None:
            return

        if self.mesh is None:
            return

        model = self.entity.model_matrix()
        view = context.view
        proj = context.projection
        gfx = context.graphics
        key = context.context_key

        for p in self.passes:
            gfx.apply_render_state(p.state)

            mat = p.material
            mat.apply(model, view, proj, graphics=gfx, context_key=key)

            shader = mat.shader

            upload_lights_to_shader(shader, context.scene.lights)
            upload_ambient_to_shader(
                shader,
                context.scene.ambient_color,
                context.scene.ambient_intensity,
            )

            # Загружаем shadow map uniform'ы (если есть shadow_data в контексте)
            if context.shadow_data is not None:
                upload_shadow_maps_to_shader(shader, context.shadow_data)

            self.mesh.draw(context)

        gfx.apply_render_state(RenderState())

    def get_phases_for_mark(self, phase_mark: str | None) -> List["MaterialPhase"]:
        """
        Возвращает все фазы материалов с указанной меткой, отсортированные по priority.

        Собирает фазы из всех RenderPass в self.passes. Для каждого pass.material
        получает фазы с помощью material.get_phases_for_mark().

        Параметры:
            phase_mark: Метка фазы ("opaque", "transparent", "shadow" и т.д.).
                        Если None, возвращает все фазы из всех материалов.

        Возвращает:
            Список MaterialPhase отсортированный по priority (меньше = раньше).
        """
        result: List["MaterialPhase"] = []

        for render_pass in self.passes:
            mat = render_pass.material
            if mat is None:
                continue

            if phase_mark is None:
                # Возвращаем все фазы
                result.extend(mat.phases)
            else:
                # Фильтруем по phase_mark
                result.extend(mat.get_phases_for_mark(phase_mark))

        # Сортируем по priority
        result.sort(key=lambda p: p.priority)
        return result

    # --- сериализация ---

    def serialize_data(self) -> dict:
        """
        Сериализует MeshRenderer, используя ссылки на ресурсы по имени.

        Mesh и материалы сохраняются как имена в ResourceManager.
        """
        rm = ResourceManager.instance()

        data = {
            "enabled": self.enabled,
        }

        # Mesh - сохраняем имя из ResourceManager
        if self.mesh is not None:
            mesh_name = rm.find_mesh_name(self.mesh)
            if mesh_name:
                data["mesh"] = mesh_name
            else:
                # Меш не зарегистрирован - используем name если есть
                data["mesh"] = self.mesh.name

        # Passes/Materials - сохраняем имена материалов
        passes_data = []
        for render_pass in self.passes:
            pass_data = {}
            if render_pass.material is not None:
                mat_name = rm.find_material_name(render_pass.material)
                if mat_name:
                    pass_data["material"] = mat_name
                elif render_pass.material.name:
                    pass_data["material"] = render_pass.material.name
            passes_data.append(pass_data)
        data["passes"] = passes_data

        return data

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "MeshRenderer":
        """
        Восстанавливает MeshRenderer из сериализованных данных.

        Параметры:
            data: Сериализованные данные (секция 'data' из Component.serialize)
            context: Опциональный контекст (не используется, ресурсы берутся из ResourceManager)

        Возвращает:
            MeshRenderer с восстановленными ссылками на ресурсы
        """
        rm = ResourceManager.instance()

        # Получаем mesh
        mesh = None
        mesh_name = data.get("mesh")
        if mesh_name:
            mesh = rm.get_mesh(mesh_name)

        # Получаем passes/materials
        passes = []
        for pass_data in data.get("passes", []):
            mat_name = pass_data.get("material")
            material = None
            if mat_name:
                material = rm.get_material(mat_name)
            if material is not None:
                passes.append(RenderPass(material=material, state=RenderState()))

        # Создаём MeshRenderer
        if passes:
            renderer = cls(mesh=mesh, passes=passes)
        elif mesh is not None:
            renderer = cls(mesh=mesh)
        else:
            renderer = cls()

        renderer.enabled = data.get("enabled", True)
        return renderer
