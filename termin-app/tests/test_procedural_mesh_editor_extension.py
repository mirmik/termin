from termin.csg.procedural_document import ProceduralMeshDocument
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
        self.overlay_drawers = []

    def add_viewport_click_interceptor(self, callback):
        self.click_interceptors.append(callback)

    def remove_viewport_click_interceptor(self, callback):
        self.click_interceptors.remove(callback)

    def add_viewport_overlay_drawer(self, callback):
        self.overlay_drawers.append(callback)

    def remove_viewport_overlay_drawer(self, callback):
        self.overlay_drawers.remove(callback)

    def request_viewport_update(self):
        self.viewport_updates += 1


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
    panel._on_primitive_param_changed(2.5)

    assert operation.params["size"] == [2.5, 1.0, 1.0]
    assert operation.params["center"] == [0.0, 0.0, 1.25]
    assert component.dirty_count == 2
    assert component.regenerate_count == 2
