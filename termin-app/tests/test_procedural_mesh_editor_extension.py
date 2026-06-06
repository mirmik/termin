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
