from termin.navmesh.display_component import NavMeshDisplayComponent


def test_navmesh_display_overlay_materials_preserve_depth_without_writing_it():
    component = NavMeshDisplayComponent()

    surface_phase = component._get_or_create_material().phases[0]
    contour_phase = component._get_or_create_contour_material().phases[0]

    assert surface_phase.phase_mark == "opaque"
    assert surface_phase.state.depth_test == 1
    assert surface_phase.state.depth_write == 0
    assert surface_phase.state.blend == 1

    assert contour_phase.phase_mark == "opaque"
    assert contour_phase.state.depth_test == 1
    assert contour_phase.state.depth_write == 0
    assert contour_phase.state.blend == 0


class _Phase:
    def __init__(self, phase):
        self.phase = phase
        self.priority = 0
        self.uniforms = {}

    def set_param(self, name, value):
        self.uniforms[name] = value


class _Material:
    def __init__(self, phase):
        self.phases = [_Phase(phase)]
        self.phase_count = 1

    def get_phase(self, index):
        return self.phases[index]


class _Mesh:
    is_valid = True


class _RenderItem:
    @staticmethod
    def mesh(*, mesh, phase, geometry_id):
        return (mesh, phase, geometry_id)


def test_navmesh_surface_collection_uses_prepared_geometry_and_same_selection(monkeypatch):
    from termin.navmesh import display_component, material_component
    from termin.navmesh.material_component import NavMeshMaterialComponent
    from termin.render.drawable import RenderItemCollectContext

    for component, module in (
        (NavMeshDisplayComponent(), display_component),
        (NavMeshMaterialComponent(), material_component),
    ):
        monkeypatch.setattr(module, "RenderItem", _RenderItem)
        component._material = _Material(4)
        rebuilds = []

        def rebuild():
            rebuilds.append(True)
            component._mesh = _Mesh()

        monkeypatch.setattr(component, "_rebuild_mesh", rebuild)
        context = RenderItemCollectContext(phase=4)
        # Collection itself must not allocate geometry while checking dependencies.
        assert component.collect_materials(context) == []
        assert component.collect_render_items(context) == []
        assert rebuilds == []
        component.prepare_render(None)
        assert rebuilds == [True]
        assert component.collect_materials(context) == [component._material]
        items = component.collect_render_items(context)
        assert [item[1] for item in items] == component._material.phases
        assert rebuilds == [True]
        assert component.collect_materials(RenderItemCollectContext(phase=8)) == []
        component._mesh = None
        assert component.collect_materials(context) == []


def test_navmesh_builder_prepares_distance_geometry_before_material_selection(monkeypatch):
    from termin.navmesh import builder_component
    from termin.navmesh.builder_component import NavMeshBuilderComponent
    from termin.render.drawable import RenderItemCollectContext

    component = NavMeshBuilderComponent()
    component.show_region_voxels = False
    component.show_simplified_contours = False
    component.show_triangulated = False
    component.show_watershed_regions = False
    component.show_distance_field = True
    component.show_local_maxima = not component._cached_show_local_maxima
    material = _Material(4)
    monkeypatch.setattr(component, "_get_or_create_debug_material", lambda: material)
    monkeypatch.setattr(builder_component, "RenderItem", _RenderItem)
    rebuilds = []

    def rebuild():
        rebuilds.append(True)
        component._debug_distance_field_mesh = _Mesh()
        component._cached_show_local_maxima = component.show_local_maxima
        component._cached_show_peaks = component.show_peaks

    monkeypatch.setattr(component, "_rebuild_distance_field_from_cache", rebuild)
    context = RenderItemCollectContext(phase=4)
    assert component.collect_materials(context) == []
    assert component.collect_render_items(context) == []
    assert rebuilds == []
    component.prepare_render(None)
    assert component.collect_materials(context) == [material]
    assert material.phases[0].uniforms == {}
    assert [item[1] for item in component.collect_render_items(context)] == material.phases
    assert rebuilds == [True]
    component.prepare_render(None)
    assert rebuilds == [True]
    assert component.collect_materials(RenderItemCollectContext(phase=8)) == []
