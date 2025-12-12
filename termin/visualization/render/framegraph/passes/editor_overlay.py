"""
EditorOverlayPass — рендерит только редакторские сущности (editor_only=True).

Это позволяет отделить гизмо и прочие редакторские элементы от основной
сцены, чтобы они не рендерились на игровых камерах.

Использование:
- Добавьте EditorOverlayPass после ColorPass в редакторском пайплайне
- Сущности с editor_only=True будут рендериться только в этом пассе
- Игровые пайплайны не должны включать этот пасс
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.components import MeshRenderer
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.core.material import MaterialPhase
    from termin.visualization.core.entity import Entity


@dataclass
class EditorDrawCall:
    """
    Описание одного draw call для редакторской сущности.
    """
    entity: "Entity"
    mesh_renderer: MeshRenderer
    phase: "MaterialPhase"
    priority: int


class EditorOverlayPass(RenderFramePass):
    """
    Проход для рендеринга редакторских сущностей.

    Рисует только сущности с editor_only=True.
    Это позволяет отделить гизмо, редакторские маркеры и т.д.
    от основной сцены.

    Атрибуты:
        input_res: Имя входного ресурса (обычно "color" от ColorPass).
        output_res: Имя выходного ресурса (обычно "color").
        phase_mark: Метка фазы для фильтрации ("opaque", "transparent" и т.д.).
    """

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "phase_mark": InspectField(path="phase_mark", label="Phase Mark", kind="string"),
    }

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "EditorOverlay",
        phase_mark: str | None = None,
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
        )
        self.input_res = input_res
        self.output_res = output_res
        self.phase_mark = phase_mark

    def _serialize_params(self) -> dict:
        """Сериализует параметры EditorOverlayPass."""
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
            "phase_mark": self.phase_mark,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "EditorOverlayPass":
        """Создаёт EditorOverlayPass из сериализованных данных."""
        return cls(
            input_res=data.get("input_res", "color"),
            output_res=data.get("output_res", "color"),
            pass_name=data.get("pass_name", "EditorOverlay"),
            phase_mark=data.get("phase_mark"),
        )

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """EditorOverlayPass читает input_res и пишет output_res inplace."""
        return [(self.input_res, self.output_res)]

    def _collect_editor_draw_calls(self, scene, phase_mark: str | None) -> List[EditorDrawCall]:
        """
        Собирает draw calls только для editor_only сущностей.
        """
        draw_calls: List[EditorDrawCall] = []

        for entity in scene.entities:
            if not (entity.active and entity.visible):
                continue

            # Рендерим ТОЛЬКО editor_only сущности
            if not entity.editor_only:
                continue

            mr = entity.get_component(MeshRenderer)
            if mr is None or not mr.enabled:
                continue

            phases = mr.get_phases_for_mark(phase_mark)
            for phase in phases:
                draw_calls.append(EditorDrawCall(
                    entity=entity,
                    mesh_renderer=mr,
                    phase=phase,
                    priority=phase.priority,
                ))

        draw_calls.sort(key=lambda dc: dc.priority)
        return draw_calls

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle | None"],
        writes_fbos: dict[str, "FramebufferHandle | None"],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        """
        Выполняет проход рендеринга редакторских сущностей.
        """
        from termin.visualization.render.lighting.upload import upload_lights_to_shader, upload_ambient_to_shader
        from termin.visualization.render.renderpass import RenderState
        from termin.visualization.core.entity import RenderContext

        if lights is not None:
            scene.lights = lights

        px, py, pw, ph = rect
        key = context_key

        fb = writes_fbos.get(self.output_res)
        if fb is None:
            return

        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)

        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()

        render_context = RenderContext(
            view=view,
            projection=projection,
            camera=camera,
            scene=scene,
            context_key=key,
            graphics=graphics,
            phase=self.phase_mark if self.phase_mark else "main",
        )

        if self.phase_mark is not None:
            draw_calls = self._collect_editor_draw_calls(scene, self.phase_mark)

            for dc in draw_calls:
                model = dc.entity.model_matrix()

                graphics.apply_render_state(dc.phase.render_state)
                dc.phase.apply(model, view, projection, graphics, context_key=key)

                shader = dc.phase.shader_programm
                upload_lights_to_shader(shader, scene.lights)
                upload_ambient_to_shader(shader, scene.ambient_color, scene.ambient_intensity)

                if dc.mesh_renderer.mesh is not None:
                    dc.mesh_renderer.mesh.draw(render_context)

            graphics.apply_render_state(RenderState())

        else:
            # Legacy режим
            for entity in scene.entities:
                if not entity.editor_only:
                    continue

                entity.draw(render_context)
