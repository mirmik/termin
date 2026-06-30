import numpy as np

from termin_voxel_components import voxelizer_debug_draw
from termin_voxel_components.voxelizer_debug_draw import VoxelizerDebugDrawService


class _Phase:
    def __init__(self, phase_mark: str, priority: int = 0):
        self.phase_mark = phase_mark
        self.priority = priority
        self.params = {}

    def set_param(self, name, value):
        self.params[name] = value


class _Material:
    def __init__(self, *phases: _Phase):
        self.phases = list(phases)


class _Mesh:
    is_valid = True


class _DrawCall:
    def __init__(self, phase, geometry_id: int = 0):
        self.phase = phase
        self.geometry_id = geometry_id


class _Component:
    GEOMETRY_REGIONS = 1
    GEOMETRY_SPARSE_BOUNDARY = 2
    GEOMETRY_INNER_CONTOUR = 3
    GEOMETRY_SIMPLIFIED_CONTOURS = 4
    GEOMETRY_BRIDGED_CONTOURS = 5
    GEOMETRY_TRIANGULATED = 6

    def __init__(self):
        self.show_region_voxels = True
        self.show_sparse_boundary = False
        self.show_simplified_contours = True
        self.show_bridged_contours = False
        self.show_triangulated = False
        self._debug_region_voxels_mesh = _Mesh()
        self._debug_sparse_boundary_mesh = None
        self._debug_inner_contour_mesh = None
        self._debug_simplified_contours_mesh = _Mesh()
        self._debug_bridged_contours_mesh = None
        self._debug_triangulated_mesh = None
        self._debug_bounds_min = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        self._debug_bounds_max = np.array([4.0, 5.0, 6.0], dtype=np.float32)
        self.voxel_phase = _Phase("opaque", priority=10)
        self.line_phase = _Phase("line", priority=5)
        self.transparent_phase = _Phase("transparent", priority=20)

    def _get_or_create_debug_material(self):
        return _Material(self.voxel_phase)

    def _get_or_create_line_material(self):
        return _Material(self.line_phase)

    def _get_or_create_transparent_material(self):
        return _Material(self.transparent_phase)


def test_voxelizer_debug_draw_service_collects_enabled_layers(monkeypatch):
    monkeypatch.setattr(voxelizer_debug_draw, "GeometryDrawCall", _DrawCall)
    component = _Component()
    service = VoxelizerDebugDrawService()

    assert service.phase_marks(component) == {"opaque", "line"}

    draws = service.get_geometry_draws(component)
    assert [draw.geometry_id for draw in draws] == [
        component.GEOMETRY_REGIONS,
        component.GEOMETRY_SIMPLIFIED_CONTOURS,
    ]
    assert component.voxel_phase.params["u_color_below"].tolist() == [1.0, 1.0, 1.0, 1.0]
    assert component.voxel_phase.params["u_bounds_min"].tolist() == [1.0, 2.0, 3.0, 0.0]
    assert component.voxel_phase.params["u_bounds_max"].tolist() == [4.0, 5.0, 6.0, 0.0]


def test_voxelizer_debug_draw_service_filters_phase_marks(monkeypatch):
    monkeypatch.setattr(voxelizer_debug_draw, "GeometryDrawCall", _DrawCall)
    component = _Component()
    service = VoxelizerDebugDrawService()

    draws = service.get_geometry_draws(component, phase_mark="line")

    assert [draw.geometry_id for draw in draws] == [
        component.GEOMETRY_SIMPLIFIED_CONTOURS,
    ]
    assert component.voxel_phase.params == {}
