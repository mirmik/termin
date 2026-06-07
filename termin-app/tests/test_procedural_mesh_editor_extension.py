from math import isclose

from tcbase._geom_native import Vec3

from termin.csg.procedural_document import ProceduralMeshDocument
from termin.csg.procedural_document import ProceduralPlane
from termin.editor_tcgui.procedural_mesh_editor_extension import ProceduralMeshEditorExtension


class _ComponentRef:
    def __init__(self, component):
        self._component = component

    def to_python(self):
        return self._component


class _Component:
    def __init__(self):
        self.document = ProceduralMeshDocument()
        self.auto_regenerate = True
        self.dirty_count = 0
        self.regenerate_count = 0

    def mark_dirty(self):
        self.dirty_count += 1

    def regenerate_if_needed(self):
        self.regenerate_count += 1
        return True


class _Editor:
    def __init__(self):
        self.viewport_updates = 0
        self.click_interceptors = []
        self.pointer_handlers = []
        self.overlay_drawers = []
        self.viewport_tool_count = 0

    def add_viewport_click_interceptor(self, callback):
        self.click_interceptors.append(callback)

    def remove_viewport_click_interceptor(self, callback):
        self.click_interceptors.remove(callback)

    def add_viewport_pointer_handler(self, callback):
        self.pointer_handlers.append(callback)

    def remove_viewport_pointer_handler(self, callback):
        self.pointer_handlers.remove(callback)

    def add_viewport_overlay_drawer(self, callback):
        self.overlay_drawers.append(callback)

    def remove_viewport_overlay_drawer(self, callback):
        self.overlay_drawers.remove(callback)

    def request_viewport_update(self):
        self.viewport_updates += 1

    def begin_viewport_tool(self):
        self.viewport_tool_count += 1

    def end_viewport_tool(self):
        self.viewport_tool_count -= 1

    def world_ray_from_viewport_point(self, x, y):
        return (
            ((float(x) - 100.0) / 100.0, (float(y) - 100.0) / 100.0, 1.0),
            (0.0, 0.0, -1.0),
        )

    def project_world_point_to_viewport(self, point):
        return (
            100.0 + float(point[0]) * 100.0,
            100.0 + float(point[1]) * 100.0,
        )


class _HeightEditor(_Editor):
    def world_ray_from_viewport_point(self, x, y):
        return (
            ((float(x) - 100.0) / 100.0 - 1.0, 0.0, (float(y) - 100.0) / 100.0),
            (1.0, 0.0, 0.0),
        )

    def project_world_point_to_viewport(self, point):
        return (
            100.0 + float(point[0]) * 100.0,
            100.0 + float(point[2]) * 100.0,
        )


class _Pose:
    def point_to_global(self, point):
        return Vec3(point.x, point.y, point.z)

    def point_to_local(self, point):
        return Vec3(point.x, point.y, point.z)

    def vector_to_local(self, vector):
        return Vec3(vector.x, vector.y, vector.z)


class _Transform:
    def global_pose(self):
        return _Pose()


class _Entity:
    name = "ProceduralMesh"

    def __init__(self):
        self.transform = _Transform()

    def valid(self):
        return True


def test_procedural_mesh_editor_extension_uses_shared_controller_for_document_commands():
    component = _Component()
    editor = _Editor()
    extension = ProceduralMeshEditorExtension()
    extension.attach(editor, None, _ComponentRef(component))
    extension.build_left_panel()

    extension._add_primitive_operation("box")
    first_operation_id = component.document.operations[0].id
    assert component.document is extension._controller.document
    assert extension._controller.selection == ("operation", first_operation_id)
    assert editor.viewport_updates == 1
    assert component.dirty_count == 1
    assert component.regenerate_count == 1

    extension._add_primitive_operation("sphere")
    extension._add_boolean_operation("subtract")
    assert len(component.document.operations) == 3
    assert component.document.operations[-1].kind == "subtract"
    assert component.document.operations[-1].inputs == [
        first_operation_id,
        component.document.operations[1].id,
    ]

    old_document = component.document
    extension._clear_sketch()
    assert component.document is extension._controller.document
    assert component.document is not old_document
    assert component.document.operations == []
    assert component.dirty_count == 4
    assert component.regenerate_count == 4


def test_procedural_mesh_editor_extension_builds_left_document_tree_panel():
    component = _Component()
    editor = _Editor()
    extension = ProceduralMeshEditorExtension()
    extension.attach(editor, None, _ComponentRef(component))

    right_panel = extension.build_panel()
    left_panel = extension.build_left_panel()

    assert right_panel is not None
    assert left_panel is not None
    assert len(extension._document_tree.root_nodes) == 1
    assert extension._document_tree.root_nodes[0].data == ("info", "empty")

    extension._add_primitive_operation("box")

    operation = component.document.operations[0]
    assert len(extension._document_tree.root_nodes) == 1
    root_node = extension._document_tree.root_nodes[0]
    assert root_node.data == ("operation", operation.id)
    assert extension._document_tree.selected_node is root_node


def test_procedural_mesh_editor_extension_right_panel_edits_shared_primitive_params():
    component = _Component()
    editor = _Editor()
    extension = ProceduralMeshEditorExtension()
    extension.attach(editor, None, _ComponentRef(component))
    extension.build_panel()
    extension.build_left_panel()

    extension._add_primitive_operation("box")

    operation = component.document.operations[0]
    panel = extension._editor_panel
    assert panel.primitive_params_panel.visible is True
    assert panel.primitive_param_inputs["size.x"].value == 1.0

    panel.primitive_param_inputs["size.x"].value = 2.5
    panel.primitive_param_inputs["center.z"].value = 1.25
    panel.primitive_params._on_param_changed(2.5)

    assert operation.params["size"] == [2.5, 1.0, 1.0]
    assert operation.params["center"] == [0.0, 0.0, 1.25]
    assert component.dirty_count == 2
    assert component.regenerate_count == 2


def test_procedural_mesh_editor_extension_drags_selected_contour_point_in_viewport():
    component = _Component()
    contour = component.document.add_contour_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
        ],
        ProceduralPlane(),
    )
    assert contour is not None

    editor = _Editor()
    extension = ProceduralMeshEditorExtension()
    extension.attach(editor, _Entity(), _ComponentRef(component))
    extension.build_panel()
    extension.build_left_panel()
    extension._apply_controller_result(extension._controller.select_node(("contour", contour.id)))

    assert editor.pointer_handlers == [extension._on_viewport_pointer]
    assert extension._on_viewport_pointer("down", 200.0, 200.0, 0.0, 0.0, 0, 1, 0) is True
    assert editor.viewport_tool_count == 1
    assert extension._on_viewport_pointer("up", 250.0, 225.0, 0.0, 0.0, 0, 0, 0) is True

    assert editor.viewport_tool_count == 0
    assert isclose(contour.points[2][0], 1.5, abs_tol=1.0e-6)
    assert isclose(contour.points[2][1], 1.25, abs_tol=1.0e-6)
    assert isclose(extension._editor_panel.contour_point_inputs[(2, "x")].value, 1.5, abs_tol=1.0e-6)
    assert isclose(extension._editor_panel.contour_point_inputs[(2, "y")].value, 1.25, abs_tol=1.0e-6)
    assert component.dirty_count == 1
    assert component.regenerate_count == 1


def test_procedural_mesh_editor_extension_drags_selected_wall_height_in_viewport():
    component = _Component()
    path = component.document.add_path_on_plane_from_points(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
        ],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = component.document.find_sketch_id_for_path(path.id)
    operation = component.document.add_wall_operation_for_sketch(sketch_id, height=3.0, thickness=0.2)
    assert operation is not None

    editor = _HeightEditor()
    extension = ProceduralMeshEditorExtension()
    extension.attach(editor, _Entity(), _ComponentRef(component))
    extension.build_panel()
    extension.build_left_panel()
    extension._apply_controller_result(extension._controller.select_node(("operation", operation.id)))

    assert extension._on_viewport_pointer("down", 200.0, 400.0, 0.0, 0.0, 0, 1, 0) is True
    assert editor.viewport_tool_count == 1
    assert extension._on_viewport_pointer("up", 200.0, 525.0, 0.0, 0.0, 0, 0, 0) is True

    offsets = operation.params["corner_height_offsets"][path.id]
    assert editor.viewport_tool_count == 0
    assert isclose(offsets[1], 1.25, abs_tol=1.0e-6)
    assert isclose(extension._editor_panel.wall_offset_inputs[(path.id, 1)].value, 1.25, abs_tol=1.0e-6)
    assert component.dirty_count == 1
    assert component.regenerate_count == 1
