"""
LineRenderer — компонент для рендеринга линий.

Реализует Drawable протокол для интеграции с ColorPass и другими пассами.

Два режима работы:
- raw_lines=False (по умолчанию): использует geometry shader для генерации
  ленты на GPU, width работает с любым материалом
- raw_lines=True: использует GL_LINES напрямую, width игнорируется,
  пользователь может использовать свой geometry shader для толщины
"""

from __future__ import annotations

import uuid
from typing import Iterable, List, Optional, Set, TYPE_CHECKING

import numpy as np

from termin.mesh import TcMesh
from termin.mesh._mesh_native import TcVertexLayout, TcAttribType, TcDrawMode
from termin.visualization.core.python_component import PythonComponent
from termin.visualization.render.render_context import RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.material_handle import MaterialHandle
from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.renderpass import RenderState
from termin.visualization.render.drawable import GeometryDrawCall
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin._native.render import MeshGPU


# Дефолтный шейдер для линий
_DEFAULT_LINE_VERT = """
#version 330 core

layout(location = 0) in vec3 a_position;

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
    Строит ленту из треугольников для линии (CPU).

    Для каждого сегмента создаёт quad (2 треугольника).
    Ширина откладывается перпендикулярно направлению линии.

    Параметры:
        points: Список точек линии [(x, y, z), ...]
        width: Толщина линии в мировых координатах
        up_hint: Подсказка для направления "вверх" (по умолчанию Y)

    Возвращает:
        (vertices, triangles) — массивы для меша
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


class LineRenderer(PythonComponent):
    """
    Компонент для рендеринга линий.

    Реализует Drawable протокол для интеграции с ColorPass.

    Атрибуты:
        points: Список точек линии [(x, y, z), ...].
        width: Толщина линии (в мировых координатах).
        raw_lines: Если True, использует GL_LINES без geometry shader.
        material: Материал для рендеринга (если None — создаётся дефолтный).

    Фильтрация по фазам:
        phase_marks = фазы из материала.
        get_phases(phase_mark) возвращает MaterialPhase с совпадающим phase_mark.
    """

    is_drawable = True

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
            path="_material_handle",
            label="Material",
            kind="material_handle",
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

        # TcMesh (always GL_LINES)
        self._mesh: TcMesh | None = None
        self._mesh_gpu: Optional["MeshGPU"] = None

        # Флаг необходимости перестроения меша
        self._dirty = True

        # Cached line ribbon material
        self._ribbon_material: Material | None = None
        self._ribbon_material_source_id: int = 0

    @property
    def phase_marks(self) -> Set[str]:
        """
        Возвращает множество phase_marks для этого renderer'а.
        Собирается из phase_mark каждой фазы материала.
        """
        marks: Set[str] = set()
        mat = self._get_effective_material()
        if mat is None:
            return marks
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
        new_points = list(value)
        if new_points != self._points:
            self._points = new_points
            self._dirty = True

    @property
    def width(self) -> float:
        """Толщина линии в мировых координатах."""
        return self._width

    @width.setter
    def width(self, value: float):
        self._width = value
        # width не требует пересборки меша - передаётся как uniform

    @property
    def raw_lines(self) -> bool:
        """Режим GL_LINES без geometry shader."""
        return self._raw_lines

    @raw_lines.setter
    def raw_lines(self, value: bool):
        if self._raw_lines != value:
            self._raw_lines = value
            self._ribbon_material = None  # Invalidate cached ribbon material

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
        self._ribbon_material = None  # Invalidate cached ribbon material

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
        self._ribbon_material = None

    # --- Geometry building ---

    def _rebuild_geometry(self):
        """Перестраивает меш из точек."""
        self._mesh = None
        self._mesh_gpu = None

        n_points = len(self._points)
        if n_points < 2:
            self._dirty = False
            return

        # Layout: position only (vec3)
        layout = TcVertexLayout()
        layout.add("position", 3, TcAttribType.FLOAT32, 0)

        # Vertices: just positions
        vertices = np.array(self._points, dtype=np.float32).flatten()

        # Indices: pairs for each line segment
        n_segments = n_points - 1
        indices = np.zeros(n_segments * 2, dtype=np.uint32)
        for i in range(n_segments):
            indices[i * 2] = i
            indices[i * 2 + 1] = i + 1

        # Generate unique uuid for mesh registry lookup
        mesh_uuid = str(uuid.uuid4())
        self._mesh = TcMesh.from_interleaved(
            vertices=vertices,
            vertex_count=n_points,
            indices=indices,
            layout=layout,
            name="line_renderer",
            uuid=mesh_uuid,
            draw_mode=TcDrawMode.LINES,
        )
        self._dirty = False

    def _ensure_geometry(self):
        """Ленивое построение геометрии."""
        if self._dirty:
            self._rebuild_geometry()

    def _get_mesh(self) -> TcMesh | None:
        """Возвращает TcMesh."""
        self._ensure_geometry()
        return self._mesh

    # Class-level cache for default line material
    _default_material: Optional[Material] = None

    def _get_base_material(self) -> Material:
        """Возвращает базовый материал (без ribbon трансформации)."""
        mat = self._material_handle.get_material_or_none()
        if mat is None:
            if LineRenderer._default_material is None:
                shader = ShaderProgram(
                    vertex_source=_DEFAULT_LINE_VERT,
                    fragment_source=_DEFAULT_LINE_FRAG,
                )
                render_state = RenderState(cull=False)
                LineRenderer._default_material = Material(
                    shader=shader,
                    color=(1.0, 1.0, 1.0, 1.0),
                    phase_mark="opaque",
                    render_state=render_state,
                )
            mat = LineRenderer._default_material
        return mat

    def _get_effective_material(self) -> Material:
        """Возвращает материал с учётом режима (ribbon или raw)."""
        base_mat = self._get_base_material()

        if self._raw_lines:
            # Raw mode - use material as-is
            return base_mat

        # Ribbon mode - apply line ribbon transformation
        source_id = id(base_mat)
        if self._ribbon_material is None or self._ribbon_material_source_id != source_id:
            from termin.visualization.render.shader_line_ribbon import get_line_ribbon_material
            self._ribbon_material = get_line_ribbon_material(base_mat)
            self._ribbon_material_source_id = source_id

        return self._ribbon_material

    # --- Drawable protocol ---

    def draw_geometry(self, context: RenderContext, geometry_id: int = 0) -> None:
        """
        Рисует геометрию линий (шейдер уже привязан пассом).

        Параметры:
            context: Контекст рендеринга.
            geometry_id: Идентификатор геометрии (игнорируется — одна геометрия).
        """
        mesh = self._get_mesh()
        if mesh is None or not mesh.is_valid:
            return

        # Set line width uniform for geometry shader
        if not self._raw_lines and context.current_shader is not None:
            context.current_shader.set_uniform_float("u_line_width", self._width)

        if self._mesh_gpu is None:
            from termin._native.render import MeshGPU
            self._mesh_gpu = MeshGPU()
        self._mesh_gpu.draw(context, mesh.mesh, mesh.version)

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """
        Возвращает GeometryDrawCalls для указанной метки фазы.

        Параметры:
            phase_mark: Фильтр по метке ("opaque", "transparent", "editor", etc.)
                        Если None, возвращает все фазы.

        Возвращает:
            Список GeometryDrawCall с совпадающим phase_mark, отсортированный по priority.
        """
        mat = self._get_effective_material()

        if phase_mark is None:
            phases = list(mat.phases)
        else:
            phases = [p for p in mat.phases if p.phase_mark == phase_mark]

        # Disable backface culling for lines
        for phase in phases:
            phase.render_state.cull = False

        phases.sort(key=lambda p: p.priority)
        return [GeometryDrawCall(phase=p) for p in phases]
