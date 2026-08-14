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
