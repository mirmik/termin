"""
LineRenderer — компонент для рендеринга линий.

Реализует Drawable протокол для интеграции с ColorPass и другими пассами.

Два режима работы:
- raw_lines=False (по умолчанию): генерирует ленту из треугольников на CPU,
  width гарантированно работает с любым шейдером
- raw_lines=True: использует GL_LINES, width игнорируется,
  пользователь может использовать geometry shader для толщины
"""

from __future__ import annotations

from typing import Iterable, List, Set, TYPE_CHECKING

import numpy as np

from termin.mesh.mesh import Mesh2, Mesh3
from termin.visualization.core.entity import Component, RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import Mesh2Drawable, MeshDrawable
from termin.visualization.core.material_handle import MaterialHandle
from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.renderpass import RenderPass, RenderState
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.material import MaterialPhase


# Стандартные phase marks для линий (без теней)
DEFAULT_LINE_PHASE_MARKS: Set[str] = {"opaque"}


# Дефолтный шейдер для линий
_DEFAULT_LINE_VERT = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_uv;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

_DEFAULT_LINE_FRAG = """
#version 330 core

uniform vec4 u_color;

out vec4 FragColor;

void main() {
    FragColor = u_color;
}
"""


def _build_line_ribbon(
    points: List[tuple[float, float, float]],
    width: float,
    up_hint: np.ndarray = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Строит ленту из треугольников для линии.

    Для каждого сегмента создаёт quad (2 треугольника).
    Ширина откладывается перпендикулярно направлению линии.

    Параметры:
        points: Список точек линии [(x, y, z), ...]
        width: Толщина линии в мировых координатах
        up_hint: Подсказка для направления "вверх" (по умолчанию Y)

    Возвращает:
        (vertices, triangles) — массивы для Mesh3
    """
    if len(points) < 2:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.int32)

    if up_hint is None:
        up_hint = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    pts = np.array(points, dtype=np.float32)
    n_points = len(pts)
    n_segments = n_points - 1

    # Для каждой точки вычисляем направление и перпендикуляр
    # На стыках усредняем направления соседних сегментов
    directions = np.zeros((n_points, 3), dtype=np.float32)

    for i in range(n_segments):
        seg_dir = pts[i + 1] - pts[i]
        seg_len = np.linalg.norm(seg_dir)
        if seg_len > 1e-8:
            seg_dir /= seg_len
        directions[i] += seg_dir
        directions[i + 1] += seg_dir

    # Нормализуем направления
    for i in range(n_points):
        d_len = np.linalg.norm(directions[i])
        if d_len > 1e-8:
            directions[i] /= d_len

    # Вычисляем перпендикуляры
    half_width = width * 0.5
    vertices = []

    for i in range(n_points):
        p = pts[i]
        d = directions[i]

        # Перпендикуляр = cross(direction, up_hint)
        perp = np.cross(d, up_hint)
        perp_len = np.linalg.norm(perp)

        if perp_len < 1e-8:
            # Линия параллельна up_hint, используем другую ось
            alt_up = np.array([1.0, 0.0, 0.0], dtype=np.float32)
            perp = np.cross(d, alt_up)
            perp_len = np.linalg.norm(perp)
            if perp_len < 1e-8:
                alt_up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                perp = np.cross(d, alt_up)
                perp_len = np.linalg.norm(perp)

        if perp_len > 1e-8:
            perp /= perp_len

        # Две вершины: слева и справа от центра
        v_left = p - perp * half_width
        v_right = p + perp * half_width
        vertices.append(v_left)
        vertices.append(v_right)

    vertices = np.array(vertices, dtype=np.float32)

    # Строим треугольники
    # Для каждого сегмента: 2 треугольника из 4 вершин
    triangles = []
    for i in range(n_segments):
        # Индексы вершин для сегмента i
        bl = i * 2      # bottom-left
        br = i * 2 + 1  # bottom-right
        tl = (i + 1) * 2      # top-left
        tr = (i + 1) * 2 + 1  # top-right

        # Два треугольника
        triangles.append([bl, tl, br])
        triangles.append([br, tl, tr])

    triangles = np.array(triangles, dtype=np.int32) if triangles else np.zeros((0, 3), dtype=np.int32)

    return vertices, triangles


class LineRenderer(Component):
    """
    Компонент для рендеринга линий.

    Реализует Drawable протокол для интеграции с ColorPass.

    Атрибуты:
        points: Список точек линии [(x, y, z), ...].
        width: Толщина линии (в мировых координатах).
        raw_lines: Если True, использует GL_LINES без генерации квадов.
        material: Материал для рендеринга.
        phase_marks: Множество фаз, в которых участвует renderer.
    """

    inspect_fields = {
        "points": InspectField(
            path="points",
            label="Points",
            kind="vec3_list",
            setter=lambda obj, value: obj.set_points(value),
        ),
        "width": InspectField(
            path="width",
            label="Width",
            kind="float",
            min=0.001,
            max=10.0,
            step=0.01,
            setter=lambda obj, value: obj.set_width(value),
        ),
        "raw_lines": InspectField(
            path="raw_lines",
            label="Raw Lines (GL_LINES)",
            kind="bool",
            setter=lambda obj, value: obj.set_raw_lines(value),
        ),
        "material": InspectField(
            path="material",
            label="Material",
            kind="material",
            setter=lambda obj, value: obj.set_material(value),
        ),
    }

    def __init__(
        self,
        points: Iterable[tuple[float, float, float]] | None = None,
        width: float = 0.1,
        raw_lines: bool = False,
        material: Material | None = None,
        phase_marks: Set[str] | None = None,
    ):
        super().__init__(enabled=True)

        self._points: List[tuple[float, float, float]] = list(points) if points else []
        self._width: float = width
        self._raw_lines: bool = raw_lines
        self.phase_marks: Set[str] = phase_marks if phase_marks is not None else set(DEFAULT_LINE_PHASE_MARKS)

        # Материал
        self._material_handle: MaterialHandle = MaterialHandle()
        if material is not None:
            self._material_handle = MaterialHandle.from_material(material)

        # Drawables для двух режимов
        self._ribbon_drawable: MeshDrawable | None = None  # для quad режима
        self._lines_drawable: Mesh2Drawable | None = None   # для raw_lines режима

        # Флаг необходимости перестроения
        self._dirty = True

    # --- Properties ---

    @property
    def points(self) -> List[tuple[float, float, float]]:
        """Список точек линии."""
        return self._points

    @points.setter
    def points(self, value: Iterable[tuple[float, float, float]]):
        self._points = list(value)
        self._dirty = True

    @property
    def width(self) -> float:
        """Толщина линии."""
        return self._width

    @width.setter
    def width(self, value: float):
        self._width = value
        self._dirty = True

    @property
    def raw_lines(self) -> bool:
        """Режим GL_LINES."""
        return self._raw_lines

    @raw_lines.setter
    def raw_lines(self, value: bool):
        self._raw_lines = value
        self._dirty = True

    @property
    def material(self) -> Material | None:
        """Текущий материал."""
        return self._material_handle.get()

    @material.setter
    def material(self, value: Material | None):
        if value is None:
            self._material_handle = MaterialHandle()
        else:
            self._material_handle = MaterialHandle.from_material(value)

    # --- Setters for inspector ---

    def set_points(self, points: Iterable[tuple[float, float, float]]):
        """Устанавливает точки линии."""
        self.points = points

    def set_width(self, value: float):
        """Устанавливает толщину линии."""
        self.width = value

    def set_raw_lines(self, value: bool):
        """Устанавливает режим GL_LINES."""
        self.raw_lines = value

    def set_material(self, value: Material | None):
        """Устанавливает материал."""
        self.material = value

    def set_material_by_name(self, name: str):
        """Устанавливает материал по имени из ResourceManager."""
        self._material_handle = MaterialHandle.from_name(name)

    # --- Geometry building ---

    def _rebuild_geometry(self):
        """Перестраивает геометрию в зависимости от режима."""
        self._ribbon_drawable = None
        self._lines_drawable = None

        if len(self._points) < 2:
            self._dirty = False
            return

        if self._raw_lines:
            # GL_LINES режим
            edges = [[i, i + 1] for i in range(len(self._points) - 1)]
            mesh2 = Mesh2.from_lists(self._points, edges)
            self._lines_drawable = Mesh2Drawable(mesh2)
        else:
            # Ribbon режим (квады)
            vertices, triangles = _build_line_ribbon(self._points, self._width)
            if len(triangles) > 0:
                mesh3 = Mesh3(vertices=vertices, triangles=triangles)
                self._ribbon_drawable = MeshDrawable(mesh3)

        self._dirty = False

    def _ensure_geometry(self):
        """Ленивое построение геометрии."""
        if self._dirty:
            self._rebuild_geometry()

    def _get_drawable(self):
        """Возвращает текущий drawable."""
        self._ensure_geometry()
        if self._raw_lines:
            return self._lines_drawable
        return self._ribbon_drawable

    def _ensure_material(self) -> Material:
        """Ленивая инициализация материала."""
        mat = self._material_handle.get_or_none()
        if mat is None:
            # Создаём дефолтный материал для линий
            from termin.visualization.core.material import Material
            from termin.visualization.render.shader import ShaderProgram
            from termin.visualization.render.renderpass import RenderState

            # Простой шейдер для линий
            shader = ShaderProgram(
                vertex_source=_DEFAULT_LINE_VERT,
                fragment_source=_DEFAULT_LINE_FRAG,
            )

            # RenderState с отключённым culling для двустороннего рендеринга
            render_state = RenderState(cull=False)

            # Создаём материал с phase_mark="opaque"
            mat = Material(
                shader=shader,
                color=(1.0, 1.0, 1.0, 1.0),
                phase_mark="opaque",
                render_state=render_state,
            )

            self._material_handle = MaterialHandle.from_material(mat)
        return mat

    # --- Drawable protocol ---

    def draw_geometry(self, context: RenderContext) -> None:
        """
        Рисует геометрию линий (шейдер уже привязан пассом).

        Параметры:
            context: Контекст рендеринга.
        """
        drawable = self._get_drawable()
        if drawable is None:
            return
        drawable.draw(context)

    def get_phases(self, phase_mark: str | None = None) -> List["MaterialPhase"]:
        """
        Возвращает MaterialPhases для указанной метки фазы.

        LineRenderer игнорирует phase_mark материала и всегда возвращает
        все фазы, если запрошенная метка есть в phase_marks компонента.
        Это позволяет использовать любой материал с LineRenderer.

        Также устанавливает cull=False для двустороннего рендеринга ленты.

        Параметры:
            phase_mark: Метка фазы ("opaque", etc.)
                        Если None, возвращает все фазы.

        Возвращает:
            Список MaterialPhase.
        """
        material = self._ensure_material()

        # Проверяем, что запрошенная фаза есть в наших phase_marks
        if phase_mark is not None and phase_mark not in self.phase_marks:
            print(f"[LineRenderer.get_phases] phase_mark={phase_mark} not in {self.phase_marks}, returning []")
            return []

        # Возвращаем все фазы материала (игнорируем phase_mark материала)
        phases = list(material.phases)

        # Для ribbon режима отключаем culling
        if not self._raw_lines:
            for phase in phases:
                print(f"[LineRenderer.get_phases] Setting cull=False for phase {phase.phase_mark}, was {phase.render_state.cull}")
                phase.render_state.cull = False

        print(f"[LineRenderer.get_phases] Returning {len(phases)} phases")
        return phases

    # --- Legacy draw ---

    def required_shaders(self):
        """Возвращает шейдеры, требуемые для рендеринга."""
        mat = self._material_handle.get()
        if mat is not None and mat.shader is not None:
            yield mat.shader

    def draw(self, context: RenderContext):
        """
        Legacy метод отрисовки.
        """
        if self.entity is None:
            return

        drawable = self._get_drawable()
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
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()

        data = {
            "enabled": self.enabled,
            "points": [list(p) for p in self._points],
            "width": self._width,
            "raw_lines": self._raw_lines,
        }

        # Материал (только если явно задан, не дефолтный)
        mat = self._material_handle.get()
        if mat is not None:
            mat_name = rm.find_material_name(mat)
            if mat_name and mat_name != "__ErrorMaterial__":
                data["material"] = mat_name
            elif mat.name and mat.name != "__ErrorMaterial__":
                data["material"] = mat.name

        return data

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "LineRenderer":
        """Восстанавливает LineRenderer из сериализованных данных."""
        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()

        points = [tuple(p) for p in data.get("points", [])]
        width = data.get("width", 0.1)
        raw_lines = data.get("raw_lines", False)

        renderer = cls(points=points, width=width, raw_lines=raw_lines)
        renderer.enabled = data.get("enabled", True)

        # Материал
        mat_name = data.get("material")
        if mat_name:
            renderer.set_material_by_name(mat_name)

        return renderer
