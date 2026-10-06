import numpy as np

from termin_voxel_components import voxelizer_debug_draw
from termin_voxel_components.voxelizer_debug_draw import VoxelizerDebugDrawService


class _Phase:
    def __init__(self, phase_mark: str, phase: int, priority: int = 0):
        self.phase_mark = phase_mark
        self.phase = phase
        self.priority = priority
        self.params = {}

    def set_param(self, name, value):
        self.params[name] = value


class _Material:
    def __init__(self, *phases: _Phase):
        self.phases = list(phases)


class _Mesh:
    is_valid = True


class _RenderItem:
    def __init__(self, mesh, phase, geometry_id: int = 0):
        self.mesh = mesh
        self.phase = phase
        self.geometry_id = geometry_id

    @staticmethod
    def mesh(mesh, phase, geometry_id: int = 0):
        return _RenderItem(mesh, phase, geometry_id)


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
        self.voxel_phase = _Phase("opaque", 1 << 0, priority=10)
        self.line_phase = _Phase("line", 1 << 16, priority=5)
        self.transparent_phase = _Phase("transparent", 1 << 1, priority=20)

    def _get_or_create_debug_material(self):
        return _Material(self.voxel_phase)

    def _get_or_create_line_material(self):
        return _Material(self.line_phase)

    def _get_or_create_transparent_material(self):
        return _Material(self.transparent_phase)


def test_voxelizer_debug_draw_service_collects_enabled_layers(monkeypatch):
    monkeypatch.setattr(voxelizer_debug_draw, "RenderItem", _RenderItem)
    component = _Component()
    service = VoxelizerDebugDrawService()

    assert service.phase_mask(component) == (1 << 0) | (1 << 16)

    draws = service.collect_render_items(component, 0)
    assert [draw.geometry_id for draw in draws] == [
        component.GEOMETRY_REGIONS,
        component.GEOMETRY_SIMPLIFIED_CONTOURS,
    ]
    assert component.voxel_phase.params["u_color_below"].tolist() == [1.0, 1.0, 1.0, 1.0]
    assert component.voxel_phase.params["u_bounds_min"].tolist() == [1.0, 2.0, 3.0, 0.0]
    assert component.voxel_phase.params["u_bounds_max"].tolist() == [4.0, 5.0, 6.0, 0.0]


def test_voxelizer_debug_draw_service_filters_phase_mask(monkeypatch):
    monkeypatch.setattr(voxelizer_debug_draw, "RenderItem", _RenderItem)
    component = _Component()
    service = VoxelizerDebugDrawService()

    draws = service.collect_render_items(component, 1 << 16)

    assert [draw.geometry_id for draw in draws] == [
        component.GEOMETRY_SIMPLIFIED_CONTOURS,
    ]
    assert component.voxel_phase.params == {}


def test_material_collection_selects_only_rendered_layers_without_render_items(monkeypatch):
    def unexpected_mesh(*args, **kwargs):
        raise AssertionError("material collection constructed a RenderItem")

    class ForbiddenRenderItem:
        mesh = staticmethod(unexpected_mesh)

    monkeypatch.setattr(voxelizer_debug_draw, "RenderItem", ForbiddenRenderItem)
    component = _Component()
    component.show_sparse_boundary = True
    component._debug_sparse_boundary_mesh = _Mesh()
    service = VoxelizerDebugDrawService()

    materials = service.collect_materials(component, 0)
    assert [material.phases[0] for material in materials] == [
        component.voxel_phase,
        component.voxel_phase,
        component.line_phase,
    ]
    # Collection does not configure rendering uniforms or construct geometry.
    assert component.voxel_phase.params == {}
    assert component.line_phase.params == {}
    assert component.transparent_phase.params == {}


def test_material_collection_uses_same_phase_and_valid_geometry_selection(monkeypatch):
    monkeypatch.setattr(voxelizer_debug_draw, "RenderItem", _RenderItem)
    component = _Component()
    service = VoxelizerDebugDrawService()

    materials = service.collect_materials(component, 1 << 16)
    draws = service.collect_render_items(component, 1 << 16)
    assert [material.phases[0] for material in materials] == [draw.phase for draw in draws]

    component._debug_simplified_contours_mesh = None
    assert service.collect_materials(component, 1 << 16) == []
    assert service.collect_render_items(component, 1 << 16) == []
    assert service.collect_materials(component, 1 << 1) == []


def test_voxel_display_material_selection_matches_items(monkeypatch):
    from termin.render.drawable import RenderItemCollectContext
    from termin_voxel_components import display_component
    from termin_voxel_components.display_component import VoxelDisplayComponent

    monkeypatch.setattr(display_component, "RenderItem", _RenderItem)
    component = VoxelDisplayComponent()
    component._voxel_mesh = _Mesh()
    opaque = _Phase("opaque", 1 << 0)
    transparent = _Phase("transparent", 1 << 1)
    component._material = _Material(opaque, transparent)
    context = RenderItemCollectContext(phase=1 << 1)

    assert component.collect_materials(context) == [component._material]
    assert opaque.params == {}
    assert transparent.params == {}
    assert [item.phase for item in component.collect_render_items(context)] == [transparent]
    assert component.collect_materials(RenderItemCollectContext(phase=1 << 16)) == []

    component._voxel_mesh = None
    assert component.collect_materials(context) == []
    assert component.collect_render_items(context) == []
