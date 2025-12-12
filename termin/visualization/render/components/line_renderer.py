"""
LineRenderer — компонент для рендеринга линий.

Реализует Drawable протокол для интеграции с ColorPass и другими пассами.
"""

from __future__ import annotations

from typing import Iterable, List, Set, TYPE_CHECKING

import numpy as np

from termin.mesh.mesh import Mesh2
from termin.visualization.core.entity import Component, RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import Mesh2Drawable
from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.renderpass import RenderPass, RenderState
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.material import MaterialPhase


# =============================
#   Vertex Shader
# =============================
_VERT_SHADER = """
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_pos_world;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_pos_world = world.xyz;

    gl_Position = u_projection * u_view * world;
}
"""


# =============================
#   Fragment Shader
# =============================
_FRAG_SHADER = """
#version 330 core

in vec3 v_pos_world;

uniform vec4 u_color;

out vec4 FragColor;

void main() {
    FragColor = u_color;
}
"""


# Стандартные phase marks для линий (без теней — линии обычно не отбрасывают тень)
DEFAULT_LINE_PHASE_MARKS: Set[str] = {"opaque"}


class LineRenderer(Component):
    """
    Компонент для рендеринга линий.

    Реализует Drawable протокол для интеграции с ColorPass.

    Атрибуты:
        points: Список точек линии [(x, y, z), ...].
        color: Цвет линии (r, g, b, a).
        width: Толщина линии (пока не используется).
        phase_marks: Множество фаз, в которых участвует renderer.
    """

    inspect_fields = {
        "points": InspectField(
            path="points",
            label="Points",
            kind="vec3_list",
            setter=lambda obj, value: obj.set_points(value),
        ),
        "color": InspectField(
            path="color",
            label="Color",
            kind="color",
            setter=lambda obj, value: obj.set_color(value),
        ),
        "width": InspectField(
            path="width",
            label="Width",
            kind="float",
            min=0.1,
            max=10.0,
            step=0.1,
        ),
    }

    def __init__(
        self,
        points: Iterable[tuple[float, float, float]] | None = None,
        color: tuple[float, float, float, float] | None = None,
        width: float = 1.0,
        material: Material | None = None,
        phase_marks: Set[str] | None = None,
    ):
        super().__init__(enabled=True)

        self._points: List[tuple[float, float, float]] = list(points) if points else []
        self._color: tuple[float, float, float, float] = color if color else (1.0, 1.0, 1.0, 1.0)
        self.width = width
        self.phase_marks: Set[str] = phase_marks if phase_marks is not None else set(DEFAULT_LINE_PHASE_MARKS)

        # Шейдер и материал — ленивая инициализация
        self._shader: ShaderProgram | None = None
        self._material: Material | None = material
        self._drawable: Mesh2Drawable | None = None
        self._mesh: Mesh2 | None = None

        # Флаг необходимости перестроения меша
        self._dirty = True

    @property
    def points(self) -> List[tuple[float, float, float]]:
        """Список точек линии."""
        return self._points

    @points.setter
    def points(self, value: Iterable[tuple[float, float, float]]):
        """Устанавливает точки и помечает меш как грязный."""
        self._points = list(value)
        self._dirty = True

    @property
    def color(self) -> tuple[float, float, float, float]:
        """Цвет линии."""
        return self._color

    @color.setter
    def color(self, value: tuple[float, float, float, float]):
        """Устанавливает цвет линии."""
        self._color = value
        if self._material is not None:
            self._material.color = np.array(value, dtype=np.float32)

    def set_color(self, value: tuple[float, float, float, float]):
        """Устанавливает цвет линии (для инспектора)."""
        self.color = value

    def set_points(self, points: Iterable[tuple[float, float, float]]):
        """Устанавливает точки линии."""
        self.points = points

    def _ensure_shader(self) -> ShaderProgram:
        """Ленивая инициализация шейдера."""
        if self._shader is None:
            self._shader = ShaderProgram(
                vertex_source=_VERT_SHADER,
                fragment_source=_FRAG_SHADER,
            )
        return self._shader

    def _ensure_material(self) -> Material:
        """Ленивая инициализация материала."""
        if self._material is None:
            shader = self._ensure_shader()
            self._material = Material(shader=shader, color=self._color)
        return self._material

    def _rebuild_mesh(self):
        """Перестраивает меш из текущих точек."""
        if len(self._points) < 2:
            self._mesh = None
            self._drawable = None
            return

        # Создаём линейные сегменты
        edges = [[i, i + 1] for i in range(len(self._points) - 1)]
        self._mesh = Mesh2.from_lists(self._points, edges)
        self._drawable = Mesh2Drawable(self._mesh)
        self._dirty = False

    def _ensure_drawable(self) -> Mesh2Drawable | None:
        """Ленивая инициализация/обновление drawable."""
        if self._dirty:
            self._rebuild_mesh()
        return self._drawable

    # --- Drawable protocol ---

    def draw_geometry(self, context: RenderContext) -> None:
        """
        Рисует геометрию линий (шейдер уже привязан пассом).

        Параметры:
            context: Контекст рендеринга.
        """
        drawable = self._ensure_drawable()
        if drawable is None:
            return
        drawable.draw(context)

    def get_phases(self, phase_mark: str | None = None) -> List["MaterialPhase"]:
        """
        Возвращает MaterialPhases для указанной метки фазы.

        Параметры:
            phase_mark: Метка фазы ("opaque", etc.)
                        Если None, возвращает все фазы.

        Возвращает:
            Список MaterialPhase.
        """
        material = self._ensure_material()
        if phase_mark is None:
            return list(material.phases)
        return material.get_phases_for_mark(phase_mark)

    # --- Legacy draw (для обратной совместимости) ---

    def required_shaders(self):
        """Возвращает шейдеры, требуемые для рендеринга."""
        yield self._ensure_shader()

    def draw(self, context: RenderContext):
        """
        Legacy метод отрисовки (для обратной совместимости).

        Использует собственный материал и вызывает отрисовку.
        """
        if self.entity is None:
            return

        drawable = self._ensure_drawable()
        if drawable is None:
            return

        model = self.entity.model_matrix()
        view = context.view
        proj = context.projection
        gfx = context.graphics
        key = context.context_key

        material = self._ensure_material()
        material.apply(model, view, proj, graphics=gfx, context_key=key)
        drawable.draw(context)

    # --- Сериализация ---

    def serialize_data(self) -> dict:
        """Сериализует LineRenderer."""
        return {
            "enabled": self.enabled,
            "points": self._points,
            "color": list(self._color),
            "width": self.width,
        }

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "LineRenderer":
        """Восстанавливает LineRenderer из сериализованных данных."""
        points = [tuple(p) for p in data.get("points", [])]
        color = tuple(data.get("color", [1.0, 1.0, 1.0, 1.0]))
        width = data.get("width", 1.0)

        renderer = cls(points=points, color=color, width=width)
        renderer.enabled = data.get("enabled", True)
        return renderer
