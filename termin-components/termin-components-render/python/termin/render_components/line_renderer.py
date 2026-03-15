"""
LineRenderer - canonical render components path.
"""

from __future__ import annotations

import uuid
from typing import Iterable, List, Optional, Set, TYPE_CHECKING

import numpy as np

from termin.mesh import TcMesh
from tgfx import TcVertexLayout, TcAttribType, TcDrawMode
from termin.visualization.core.python_component import PythonComponent
from termin.visualization.render.render_context import RenderContext
from termin._native.render import TcMaterial, TcRenderState
from termin.visualization.render.drawable import GeometryDrawCall
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin._native.render import TcMaterialPhase


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
    """Build a triangle ribbon for a polyline."""
    if len(points) < 2:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.int32)

    if up_hint is None:
        up_hint = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    pts = np.array(points, dtype=np.float32)
    n_points = len(pts)
    n_segments = n_points - 1
    directions = np.zeros((n_points, 3), dtype=np.float32)

    for i in range(n_segments):
        seg_dir = pts[i + 1] - pts[i]
        seg_len = np.linalg.norm(seg_dir)
        if seg_len > 1e-8:
            seg_dir /= seg_len
        directions[i] += seg_dir
        directions[i + 1] += seg_dir

    for i in range(n_points):
        d_len = np.linalg.norm(directions[i])
        if d_len > 1e-8:
            directions[i] /= d_len

    half_width = width * 0.5
    vertices = []

    for i in range(n_points):
        p = pts[i]
        d = directions[i]
        perp = np.cross(d, up_hint)
        perp_len = np.linalg.norm(perp)

        if perp_len < 1e-8:
            alt_up = np.array([1.0, 0.0, 0.0], dtype=np.float32)
            perp = np.cross(d, alt_up)
            perp_len = np.linalg.norm(perp)
            if perp_len < 1e-8:
                alt_up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                perp = np.cross(d, alt_up)
                perp_len = np.linalg.norm(perp)

        if perp_len > 1e-8:
            perp /= perp_len

        vertices.append(p - perp * half_width)
        vertices.append(p + perp * half_width)

    vertices = np.array(vertices, dtype=np.float32)
    triangles = []
    for i in range(n_segments):
        bl = i * 2
        br = i * 2 + 1
        tl = (i + 1) * 2
        tr = (i + 1) * 2 + 1
        triangles.append([bl, tl, br])
        triangles.append([br, tl, tr])

    triangles = np.array(triangles, dtype=np.int32) if triangles else np.zeros((0, 3), dtype=np.int32)
    return vertices, triangles


class LineRenderer(PythonComponent):
    """Drawable polyline renderer."""

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
    }

    def __init__(
        self,
        points: Iterable[tuple[float, float, float]] | None = None,
        width: float = 0.1,
        raw_lines: bool = False,
        material: TcMaterial | None = None,
    ):
        super().__init__(enabled=True)
        self._points: List[tuple[float, float, float]] = list(points) if points else []
        self._width: float = width
        self._raw_lines: bool = raw_lines
        self._material: TcMaterial | None = material
        self._mesh: TcMesh | None = None
        self._dirty = True
        self._ribbon_material: TcMaterial | None = None
        self._ribbon_material_source_uuid: str = ""

    @property
    def phase_marks(self) -> Set[str]:
        marks: Set[str] = set()
        mat = self._get_effective_material()
        if mat is None:
            return marks
        for i in range(mat.phase_count):
            phase = mat.get_phase(i)
            if phase is not None:
                marks.add(phase.phase_mark)
        return marks

    @property
    def points(self) -> List[tuple[float, float, float]]:
        return self._points

    @points.setter
    def points(self, value: Iterable[tuple[float, float, float]]):
        new_points = list(value)
        if new_points != self._points:
            self._points = new_points
            self._dirty = True

    @property
    def width(self) -> float:
        return self._width

    @width.setter
    def width(self, value: float):
        self._width = value

    @property
    def raw_lines(self) -> bool:
        return self._raw_lines

    @raw_lines.setter
    def raw_lines(self, value: bool):
        if self._raw_lines != value:
            self._raw_lines = value
            self._ribbon_material = None

    @property
    def material(self) -> TcMaterial | None:
        return self._material

    @material.setter
    def material(self, value: TcMaterial | None):
        self._material = value
        self._ribbon_material = None

    def set_points(self, points: Iterable[tuple[float, float, float]]):
        self.points = points

    def set_width(self, value: float):
        self.width = value

    def set_raw_lines(self, value: bool):
        self.raw_lines = value

    def set_material(self, value: TcMaterial | None):
        self.material = value

    def set_material_by_name(self, name: str):
        from termin.assets.resources import ResourceManager
        rm = ResourceManager.instance()
        asset = rm.get_material_asset(name)
        if asset is not None:
            self._material = asset.material
        else:
            self._material = None
        self._ribbon_material = None

    def _rebuild_geometry(self):
        self._mesh = None
        n_points = len(self._points)
        if n_points < 2:
            self._dirty = False
            return

        layout = TcVertexLayout()
        layout.add("position", 3, TcAttribType.FLOAT32, 0)
        vertices = np.array(self._points, dtype=np.float32).flatten()

        n_segments = n_points - 1
        indices = np.zeros(n_segments * 2, dtype=np.uint32)
        for i in range(n_segments):
            indices[i * 2] = i
            indices[i * 2 + 1] = i + 1

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
        if self._dirty:
            self._rebuild_geometry()

    def _get_mesh(self) -> TcMesh | None:
        self._ensure_geometry()
        return self._mesh

    _default_material: Optional[TcMaterial] = None

    def _get_base_material(self) -> TcMaterial:
        mat = self._material
        if mat is None:
            if LineRenderer._default_material is None:
                default_mat = TcMaterial.create(name="DefaultLineMaterial", uuid_hint="")
                default_mat.shader_name = "DefaultLineShader"
                state = TcRenderState.opaque()
                state.cull = 0
                phase = default_mat.add_phase_from_sources(
                    vertex_source=_DEFAULT_LINE_VERT,
                    fragment_source=_DEFAULT_LINE_FRAG,
                    geometry_source="",
                    shader_name="DefaultLineShader",
                    phase_mark="opaque",
                    priority=0,
                    state=state,
                )
                if phase is not None:
                    phase.set_color(1.0, 1.0, 1.0, 1.0)
                LineRenderer._default_material = default_mat
            mat = LineRenderer._default_material
        return mat

    def _get_effective_material(self) -> TcMaterial:
        base_mat = self._get_base_material()
        if self._raw_lines:
            return base_mat

        source_uuid = base_mat.uuid
        if self._ribbon_material is None or self._ribbon_material_source_uuid != source_uuid:
            from termin.visualization.render.shader_line_ribbon import get_line_ribbon_material
            self._ribbon_material = get_line_ribbon_material(base_mat)
            self._ribbon_material_source_uuid = source_uuid

        return self._ribbon_material

    def draw_geometry(self, context: RenderContext, geometry_id: int = 0) -> None:
        mesh = self._get_mesh()
        if mesh is None or not mesh.is_valid:
            return

        if not self._raw_lines and context.current_shader is not None:
            context.current_shader.set_uniform_float("u_line_width", self._width)

        mesh.draw_gpu()

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        mat = self._get_effective_material()
        phases: List["TcMaterialPhase"] = []
        for i in range(mat.phase_count):
            phase = mat.get_phase(i)
            if phase is None:
                continue
            if phase_mark is None or phase.phase_mark == phase_mark:
                phases.append(phase)

        phases.sort(key=lambda p: p.priority)
        return [GeometryDrawCall(phase=p) for p in phases]


__all__ = ["LineRenderer", "_build_line_ribbon"]
