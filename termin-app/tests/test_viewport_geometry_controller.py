from types import SimpleNamespace

from termin.editor_core.viewport_geometry_controller import ViewportGeometryController


class _Operations:
    def __init__(self):
        self.drops = []

    def drop_glb(self, path, parent, *, world_position):
        self.drops.append((path, parent, world_position))


def test_viewport_geometry_routes_project_glb_drop_to_scene_operations():
    operations = _Operations()
    scene_tree = SimpleNamespace(operations=operations)
    controller = ViewportGeometryController(
        get_camera=lambda: None,
        get_viewport_widget=lambda: None,
        get_interaction_system=lambda: None,
        get_editor_display=lambda: None,
        get_scene_tree_controller=lambda: scene_tree,
    )

    assert controller.drop_project_file("/project/model.glb", ".GLB", 20.0, 30.0)
    assert operations.drops[0][0:2] == ("/project/model.glb", None)
    assert not controller.drop_project_file("/project/albedo.png", ".png", 20.0, 30.0)
