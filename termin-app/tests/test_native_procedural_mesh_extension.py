from __future__ import annotations

from types import SimpleNamespace

import pytest

from tcbase._geom_native import Vec3
from termin.csg.procedural_document import ProceduralMeshDocument, ProceduralPlane
from termin.editor_core.procedural_mesh_editor_extension import ProceduralMeshExtensionModel
from termin.editor_native.component_extensions import NativeComponentExtensionContext
from termin.editor_native.procedural_mesh_extension import (
    project_native_procedural_mesh_extension,
)
from termin.gui_native import Document, EventResult, PointerEvent, PointerEventType, Rect


class _Component:
    def __init__(self) -> None:
        self.document = ProceduralMeshDocument()
        self.auto_regenerate = True
        self.dirty_count = 0
        self.regenerate_count = 0

    def mark_dirty(self) -> None:
        self.dirty_count += 1

    def regenerate_if_needed(self) -> None:
        self.regenerate_count += 1


class _ComponentRef:
    def __init__(self, component: _Component) -> None:
        self._component = component

    def to_python(self) -> _Component:
        return self._component


def _find(root, debug_name: str):
    if root.debug_name == debug_name:
        return root
    for child in root.children:
        found = _find(child, debug_name)
        if found is not None:
            return found
    return None


def _click(widget) -> None:
    widget.bounds = Rect(0.0, 0.0, 80.0, 28.0)
    event = PointerEvent()
    event.x = 4.0
    event.y = 4.0
    event.type = PointerEventType.Down
    assert widget.dispatch_pointer_event(event) == EventResult.Handled
    event.type = PointerEventType.Up
    assert widget.dispatch_pointer_event(event) == EventResult.Handled


def _increment(widget) -> None:
    widget.bounds = Rect(0.0, 0.0, 80.0, 28.0)
    event = PointerEvent()
    event.type = PointerEventType.Down
    event.x = 75.0
    event.y = 4.0
    assert widget.dispatch_pointer_event(event) == EventResult.Handled


class _Pose:
    lin = Vec3(0.0, 0.0, 0.0)

    def point_to_global(self, point):
        return Vec3(point.x, point.y, point.z)

    def point_to_local(self, point):
        return Vec3(point.x, point.y, point.z)

    def vector_to_local(self, vector):
        return Vec3(vector.x, vector.y, vector.z)


class _Entity:
    name = "ProceduralMesh"
    transform = SimpleNamespace(global_pose=lambda: _Pose())

    def valid(self) -> bool:
        return True


class _Geometry:
    def world_ray_from_viewport_point(self, x: float, y: float):
        return (
            Vec3((x - 100.0) / 100.0, (y - 100.0) / 100.0, 1.0),
            Vec3(0.0, 0.0, -1.0),
        )

    def project_world_point_to_viewport(self, point):
        return (100.0 + float(point.x) * 100.0, 100.0 + float(point.y) * 100.0)

    def world_point_on_entity_local_oxy_plane(self, x: float, y: float, _entity):
        return Vec3((x - 100.0) / 100.0, (y - 100.0) / 100.0, 0.0)


def _viewport_pointer(phase: str, x: float, y: float, button: int = 0):
    return SimpleNamespace(
        phase=phase,
        screen=SimpleNamespace(x=x, y=y),
        delta=SimpleNamespace(x=0.0, y=0.0),
        button=button,
        action=1 if phase == "down" else 0,
        mods=0,
    )


def _viewport_click(x: float, y: float):
    return SimpleNamespace(
        entity=None,
        screen=SimpleNamespace(x=x, y=y),
        surface=SimpleNamespace(
            has_mesh_hit=False,
            has_world_point=False,
            mesh_triangle_index=0,
        ),
    )


def test_native_procedural_mesh_projector_mutates_shared_document_and_state():
    document = Document()
    renders: list[bool] = []
    context = NativeComponentExtensionContext(
        engine=object(),
        document=document,
        request_render=lambda: renders.append(True),
        resource_manager=SimpleNamespace(),
    )
    component = _Component()
    extension = ProceduralMeshExtensionModel()
    extension.attach(context, object(), _ComponentRef(component))

    presentation = project_native_procedural_mesh_extension(extension, document)
    root = presentation.right_panel
    assert root is not None
    assert root.stable_id == "editor.inspector.extension.procedural-mesh"
    summary = _find(root, "native-procedural-summary")
    selection = _find(root, "native-procedural-selection")
    status = _find(root, "native-procedural-status")
    assert summary is not None
    assert selection is not None
    assert status is not None

    box_button = _find(root, "native-procedural-primitive-box")
    assert box_button is not None
    _click(box_button)
    assert component.document is extension.controller.document
    assert len(component.document.operations) == 1
    operation = component.document.operations[0]
    assert extension.snapshot.selection == ("operation", operation.id)
    assert component.dirty_count == 1
    assert component.regenerate_count == 1
    assert "operations=1" in summary.name
    assert selection.name.startswith("Selection: operation ")
    assert status.name == "Status: Box added"
    assert renders

    size_x = _find(root, "native-procedural-param-size-x")
    assert size_x is not None
    _increment(size_x)
    assert component.document.operations[0].params["size"] == pytest.approx([1.1, 1.0, 1.0])
    assert component.dirty_count == 2
    assert component.regenerate_count == 2
    assert status.name == "Status: Parameters updated"

    sphere_button = _find(root, "native-procedural-primitive-sphere")
    subtract_button = _find(root, "native-procedural-boolean-subtract")
    tree_widget = _find(root, "native-procedural-document-tree")
    assert sphere_button is not None
    assert subtract_button is not None
    assert tree_widget is not None
    _click(sphere_button)
    _click(subtract_button)
    assert len(component.document.operations) == 3
    assert extension.snapshot.selection == (
        "operation",
        component.document.operations[-1].id,
    )

    tree_widget.bounds = Rect(0.0, 0.0, 330.0, 176.0)
    event = PointerEvent()
    event.type = PointerEventType.Down
    event.x = 60.0
    event.y = 34.0
    assert tree_widget.dispatch_pointer_event(event) == EventResult.Handled
    assert extension.snapshot.selection == ("operation", operation.id)

    assert extension.clear_document()
    assert component.document.operations == []
    assert component.dirty_count == 5
    assert "operations=0" in summary.name
    extension.detach()


def test_procedural_mesh_model_rejects_commands_without_component_cleanly():
    extension = ProceduralMeshExtensionModel()
    assert not extension.ensure_component_document()


def test_native_procedural_wall_and_transform_params_use_shared_commands():
    component = _Component()
    path = component.document.add_path_on_plane_from_points(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
        ProceduralPlane(),
        purpose="wall",
    )
    assert path is not None
    sketch_id = component.document.find_sketch_id_for_path(path.id)
    operation = component.document.add_wall_operation_for_sketch(
        sketch_id,
        height=3.0,
        thickness=0.2,
    )
    assert operation is not None

    document = Document()
    context = NativeComponentExtensionContext(
        engine=object(),
        document=document,
        request_render=lambda: None,
        resource_manager=SimpleNamespace(),
    )
    extension = ProceduralMeshExtensionModel()
    extension.attach(context, object(), _ComponentRef(component))
    presentation = project_native_procedural_mesh_extension(extension, document)
    root = presentation.right_panel
    assert root is not None
    assert extension.select_node(("operation", operation.id))

    height = _find(root, "native-procedural-param-height")
    assert height is not None
    _increment(height)
    assert operation.params["height"] == pytest.approx(3.1)

    align_left = _find(root, "native-procedural-param-alignment-left")
    assert align_left is not None
    _click(align_left)
    assert operation.params["alignment"] == "left"

    center_x = _find(root, "native-procedural-param-center-x")
    assert center_x is not None
    _increment(center_x)
    assert operation.params["center"] == pytest.approx([0.1, 0.0, 0.0])

    corner = _find(root, f"native-procedural-param-wall-offset-{path.id}-1")
    assert corner is not None
    _increment(corner)
    assert operation.params["corner_height_offsets"][path.id] == pytest.approx([0.0, 0.1])
    assert component.dirty_count == 4
    assert component.regenerate_count == 4
    extension.detach()


def test_native_procedural_extrude_vector_uses_shared_command():
    component = _Component()
    contour = component.document.add_contour_on_plane_from_points(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        ProceduralPlane(),
    )
    assert contour is not None
    document = Document()
    context = NativeComponentExtensionContext(
        engine=object(),
        document=document,
        request_render=lambda: None,
        resource_manager=SimpleNamespace(),
    )
    extension = ProceduralMeshExtensionModel()
    extension.attach(context, object(), _ComponentRef(component))
    presentation = project_native_procedural_mesh_extension(extension, document)
    root = presentation.right_panel
    assert root is not None
    sketch_id = component.document.find_sketch_id_for_contour(contour.id)
    assert extension.select_node(("sketch", sketch_id))
    assert extension.extrude_selected()
    operation = component.document.operations[-1]
    vector_z = _find(root, "native-procedural-param-vector-z")
    assert vector_z is not None
    _increment(vector_z)
    assert operation.params["vector"] == pytest.approx([0.0, 0.0, 1.1])
    assert component.dirty_count == 2
    assert component.regenerate_count == 2
    extension.detach()


def test_native_procedural_plane_contour_and_path_point_params():
    component = _Component()
    contour = component.document.add_contour_on_plane_from_points(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        ProceduralPlane(),
    )
    path = component.document.add_path_on_plane_from_points(
        [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        ProceduralPlane(),
        purpose="wall",
    )
    assert contour is not None
    assert path is not None
    document = Document()
    context = NativeComponentExtensionContext(
        engine=object(),
        document=document,
        request_render=lambda: None,
        resource_manager=SimpleNamespace(),
    )
    extension = ProceduralMeshExtensionModel()
    extension.attach(context, object(), _ComponentRef(component))
    presentation = project_native_procedural_mesh_extension(extension, document)
    root = presentation.right_panel
    assert root is not None

    sketch_id = component.document.find_sketch_id_for_contour(contour.id)
    assert extension.select_node(("plane", sketch_id))
    origin_x = _find(root, "native-procedural-param-origin-x")
    assert origin_x is not None
    _increment(origin_x)
    sketch = component.document.find_sketch(sketch_id)
    assert sketch is not None
    assert sketch.plane.origin == pytest.approx((0.1, 0.0, 0.0))

    assert extension.select_node(("contour", contour.id))
    contour_x = _find(root, "native-procedural-param-point-1-x")
    assert contour_x is not None
    _increment(contour_x)
    assert contour.points[1] == pytest.approx((1.1, 0.0))

    assert extension.select_node(("path", path.id))
    path_y = _find(root, "native-procedural-param-point-0-y")
    assert path_y is not None
    _increment(path_y)
    assert path.points[0] == pytest.approx((0.0, 0.1))
    assert component.dirty_count == 3
    assert component.regenerate_count == 3
    extension.detach()


def test_native_procedural_viewport_drag_uses_shared_interaction_and_updates_panel():
    component = _Component()
    contour = component.document.add_contour_on_plane_from_points(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        ProceduralPlane(),
    )
    assert contour is not None
    document = Document()
    tool_states: list[int] = []
    context = NativeComponentExtensionContext(
        engine=object(),
        document=document,
        request_render=lambda: None,
        resource_manager=SimpleNamespace(),
        viewport_geometry=_Geometry(),
        on_viewport_tool_state_changed=tool_states.append,
    )
    extension = ProceduralMeshExtensionModel()
    extension.attach(context, _Entity(), _ComponentRef(component))
    presentation = project_native_procedural_mesh_extension(extension, document)
    root = presentation.right_panel
    assert root is not None
    assert extension.select_node(("contour", contour.id))

    assert context.dispatch_viewport_pointer(_viewport_pointer("down", 200.0, 200.0))
    assert context.active_viewport_tools == 1
    assert context.dispatch_viewport_pointer(_viewport_pointer("up", 250.0, 225.0))

    assert context.active_viewport_tools == 0
    assert tool_states == [1, 0]
    assert contour.points[2] == pytest.approx((1.5, 1.25))
    point_x = _find(root, "native-procedural-param-point-2-x")
    point_y = _find(root, "native-procedural-param-point-2-y")
    status = _find(root, "native-procedural-status")
    assert point_x is not None
    assert point_y is not None
    assert status is not None
    assert status.name == "Status: Contour point P2 moved"
    assert component.dirty_count == 1
    assert component.regenerate_count == 1
    extension.detach()


def test_native_procedural_draw_click_uses_native_geometry_fallback():
    component = _Component()
    context = NativeComponentExtensionContext(
        engine=object(),
        document=Document(),
        request_render=lambda: None,
        resource_manager=SimpleNamespace(),
        viewport_geometry=_Geometry(),
    )
    extension = ProceduralMeshExtensionModel()
    extension.attach(context, _Entity(), _ComponentRef(component))

    assert extension.start_draw_sketch()
    assert context.dispatch_viewport_click(_viewport_click(150.0, 175.0))
    assert extension.controller.draft.points == pytest.approx([(0.5, 0.75, 0.0)])
    assert extension.snapshot.mode == "draw_sketch"
    extension.detach()
