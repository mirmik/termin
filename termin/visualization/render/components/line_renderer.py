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
from termin.visualization.core.mesh import Mesh2Drawable
from termin.visualization.core.mesh_handle import MeshHandle
from termin.visualization.core.material_handle import MaterialHandle
from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.renderpass import RenderState
from termin.visualization.render.drawable import GeometryDrawCall
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    pass


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
        material: Материал для рендеринга (если None — создаётся дефолтный).

    Фильтрация по фазам:
        phase_marks = фазы из материала.
        get_phases(phase_mark) возвращает MaterialPhase с совпадающим phase_mark.
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
    ):
        super().__init__(enabled=True)

        self._points: List[tuple[float, float, float]] = list(points) if points else []
        self._width: float = width
        self._raw_lines: bool = raw_lines

        # Материал
        self._material_handle: MaterialHandle = MaterialHandle()
        if material is not None:
            self._material_handle = MaterialHandle.from_material(material)

        # Drawables для двух режимов
        self._ribbon_handle: MeshHandle | None = None  # для quad режима
        self._lines_drawable: Mesh2Drawable | None = None   # для raw_lines режима

        # Флаг необходимости перестроения
        self._dirty = True

    @property
    def phase_marks(self) -> Set[str]:
        """
        Возвращает множество phase_marks для этого renderer'а.
        Собирается из phase_mark каждой фазы материала.
        """
        marks: Set[str] = set()
        mat = self._get_material_or_default()
        for phase in mat.phases:
            marks.add(phase.phase_mark)
        return marks

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

        # Проверяем совместимость с текущим материалом
        mat = self._material_handle.get_material_or_none()
        if mat is not None:
            self._warn_if_incompatible(mat)

    @property
    def material(self) -> Material | None:
        """Текущий материал."""
        return self._material_handle.get_material_or_none()

    @material.setter
    def material(self, value: Material | None):
        if value is None:
            self._material_handle = MaterialHandle()
        else:
            self._material_handle = MaterialHandle.from_material(value)
            self._warn_if_incompatible(value)

    def _warn_if_incompatible(self, material: Material) -> None:
        """Проверяет совместимость материала с режимом отрисовки."""
        has_geometry_shader = any(
            phase.shader_programm.geometry_source is not None
            for phase in material.phases
        )

        if has_geometry_shader and not self._raw_lines:
            import warnings
            warnings.warn(
                f"LineRenderer: материал '{material.name}' содержит geometry shader, "
                f"но raw_lines=False. Geometry shader для линий ожидает GL_LINES на входе. "
                f"Установите raw_lines=True или используйте материал без geometry shader.",
                RuntimeWarning,
                stacklevel=4,
            )

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
                self._ribbon_handle = MeshHandle.from_mesh3(mesh3, name="line_ribbon")

        self._dirty = False

    def _ensure_geometry(self):
        """Ленивое построение геометрии."""
        if self._dirty:
            self._rebuild_geometry()

    def _get_lines_drawable(self) -> Mesh2Drawable | None:
        """Возвращает drawable для GL_LINES режима."""
        self._ensure_geometry()
        return self._lines_drawable

    def _get_ribbon_handle(self) -> MeshHandle | None:
        """Возвращает MeshHandle для ribbon режима."""
        self._ensure_geometry()
        return self._ribbon_handle

    def _get_material_or_default(self) -> Material:
        """Возвращает материал или создаёт дефолтный."""
        mat = self._material_handle.get_material_or_none()
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

    def draw_geometry(self, context: RenderContext, geometry_id: str = "") -> None:
        """
        Рисует геометрию линий (шейдер уже привязан пассом).

        Параметры:
            context: Контекст рендеринга.
            geometry_id: Идентификатор геометрии (игнорируется — одна геометрия).
        """
        if self._raw_lines:
            drawable = self._get_lines_drawable()
            if drawable is not None:
                drawable.draw(context)
        else:
            handle = self._get_ribbon_handle()
            if handle is not None:
                mesh_data = handle.mesh
                gpu = handle.gpu
                if mesh_data is not None and gpu is not None:
                    gpu.draw(context, mesh_data, handle.version)

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """
        Возвращает GeometryDrawCalls для указанной метки фазы.

        Параметры:
            phase_mark: Фильтр по метке ("opaque", "transparent", "editor", etc.)
                        Если None, возвращает все фазы.

        Возвращает:
            Список GeometryDrawCall с совпадающим phase_mark, отсортированный по priority.
        """
        mat = self._get_material_or_default()

        if phase_mark is None:
            phases = list(mat.phases)
        else:
            phases = [p for p in mat.phases if p.phase_mark == phase_mark]

        # Для ribbon режима отключаем culling
        if not self._raw_lines:
            for phase in phases:
                phase.render_state.cull = False

        phases.sort(key=lambda p: p.priority)
        return [GeometryDrawCall(phase=p) for p in phases]

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
        mat = self._material_handle.get_material_or_none()
        if mat is not None:
            # Try to save UUID, fallback to name
            mat_uuid = rm.find_material_uuid(mat)
            if mat_uuid:
                data["material"] = {"uuid": mat_uuid}
            else:
                mat_name = rm.find_material_name(mat)
                if mat_name and mat_name != "__ErrorMaterial__":
                    data["material"] = mat_name
                elif mat.name and mat.name != "__ErrorMaterial__":
                    data["material"] = mat.name

        return data

