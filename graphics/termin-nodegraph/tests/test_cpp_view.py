"""Exercise the C++ graph view through the public Python document APIs."""

import gc
import weakref

import pytest

from termin.gui_native import (
    EventResult,
    KeyCode,
    KeyEvent,
    KeyEventType,
    ModifierFlag,
    OffscreenGuiComposition,
    PointerEvent,
    PointerEventType,
    PresentationMetrics,
    Rect,
    Size,
    tc_ui_document_create,
    tc_ui_document_destroy,
)
from termin.nodegraph import Graph, GraphController
from termin.nodegraph.cpp_view import CppNodeGraphView, NodeBodyContent, NodeBodyLayout


@pytest.fixture
def document():
    owner = tc_ui_document_create()
    owner.presentation_metrics = PresentationMetrics.identity(Size(1000.0, 700.0))
    try:
        yield owner
    finally:
        if owner.valid:
            tc_ui_document_destroy(owner)


def _layout(document):
    document.layout_roots(Rect(0.0, 0.0, 1000.0, 700.0))


def _mount(document, view):
    assert document.add_root(view.root_handle)
    _layout(document)


def _pointer(document, phase, position, *, button=0, wheel_y=0.0):
    event = PointerEvent()
    event.type = phase
    event.x, event.y = position
    event.button = button
    event.wheel_y = wheel_y
    return document.dispatch_pointer_event(event)


def _key(document, code, modifiers=0):
    event = KeyEvent()
    event.type = KeyEventType.Down
    event.key = code
    event.modifiers = modifiers
    assert document.dispatch_key_event(event) == EventResult.Handled


def _pair(controller):
    source = controller.create_node("source", node_id="source", x=-300.0, y=-120.0)
    target = controller.create_node("target", node_id="target", x=60.0, y=-120.0)
    assert controller.add_output_socket(source.id, "value-out", "number")
    assert controller.add_input_socket(target.id, "value-in", "number")
    return source, target


def _socket_position(view, node, *, output):
    # One socket at the center of the first 20-unit row under the 26-unit title.
    return view.world_to_screen(node.x + (node.width if output else 0.0), node.y + 36.0)


def _drag(document, source, target):
    assert _pointer(document, PointerEventType.Down, source) == EventResult.Handled
    assert _pointer(document, PointerEventType.Move, target) == EventResult.Handled
    assert _pointer(document, PointerEventType.Up, target) == EventResult.Handled


def test_cpp_view_routes_native_graph_input_and_context(document):
    controller = GraphController()
    source, target = _pair(controller)
    graph = controller.graph
    changes = []
    contexts = []
    redraws = []
    view = CppNodeGraphView(
        document, controller,
        on_graph_changed=lambda revision: changes.append((revision, graph.revision)),
        on_context=contexts.append,
        on_request_render=lambda: redraws.append(graph.revision),
    )
    _mount(document, view)
    try:
        source_port = _socket_position(view, source, output=True)
        target_port = _socket_position(view, target, output=False)
        original_revision = graph.revision
        _drag(document, source_port, target_port)
        assert graph.revision == original_revision + 1
        edge, = graph.edges.values()
        assert (edge.src_node_id, edge.src_socket, edge.dst_node_id, edge.dst_socket) == (
            source.id, "value-out", target.id, "value-in",
        )
        assert changes == [(graph.revision, graph.revision)]

        assert _pointer(document, PointerEventType.Down, target_port, button=1) == EventResult.Handled
        _pointer(document, PointerEventType.Up, target_port, button=1)
        context, = contexts
        assert context["kind"] == "socket"
        assert context["node_id"] == target.id
        assert context["socket_name"] == "value-in"
        assert context["socket_direction"] == "input"
        assert (context["world_x"], context["world_y"]) == pytest.approx((target.x, target.y + 36.0))

        position = view.world_to_screen(target.x + 60.0, target.y + 12.0)
        _drag(document, position, (position[0] + 38.0, position[1] + 16.0))
        moved = graph.nodes[target.id]
        assert (moved.x, moved.y) == pytest.approx((target.x + 38.0, target.y + 16.0))
        _key(document, KeyCode.Delete)
        assert set(graph.nodes) == {source.id}
        assert not graph.edges
        assert changes[-1] == (graph.revision, graph.revision)
        assert all(before == after for before, after in changes)
        assert redraws[-1] == graph.revision

        world = (-150.0, 42.0)
        before_zoom = view.world_to_screen(*world)
        anchor = view.world_to_screen(-20.0, 20.0)
        assert _pointer(document, PointerEventType.Wheel, anchor, wheel_y=1.0) == EventResult.Handled
        after_zoom = view.world_to_screen(*world)
        assert after_zoom != pytest.approx(before_zoom)
        assert view.screen_to_world(*after_zoom) == pytest.approx(world, abs=1.0e-4)
        assert view.world_to_screen(-20.0, 20.0) == pytest.approx(anchor, abs=1.0e-4)
    finally:
        view.close()


def test_cpp_view_parameter_edits_observe_committed_typed_values(document):
    controller = GraphController()
    node = controller.create_node("controls", node_id="controls", x=-120.0, y=-140.0)
    initial = {"enabled": False, "mode": "fast", "count": 1 << 53, "gain": 0.5, "caption": "original"}
    controller.update_node(node.id, params=initial)
    graph = controller.graph
    initial_revision = graph.revision
    events = []
    revisions = []

    def parameter_editors(snapshot):
        assert snapshot.id == node.id
        assert snapshot.params.keys() == initial.keys()
        return [
            {"name": "enabled", "kind": "bool"},
            {"name": "mode", "kind": "enum", "choices": [("fast", "Fast"), ("quality", "Quality")]},
            {"name": "count", "kind": "int", "min": 0, "max": 1.0e18, "step": 1},
            {"name": "gain", "kind": "float", "min": 0.0, "max": 2.0, "step": 0.25},
            {"name": "caption", "kind": "text"},
        ]

    def changed(snapshot, name, value):
        events.append((snapshot.id, name, value, snapshot.params[name], graph.nodes[node.id].params[name]))

    view = CppNodeGraphView(
        document, controller, parameter_editors=parameter_editors,
        on_param_changed=changed, on_graph_changed=revisions.append,
    )
    _mount(document, view)
    try:
        for name, key in (
            ("enabled", KeyCode.Enter),
            ("mode", KeyCode.Down),
            ("count", KeyCode.Up),
            ("gain", KeyCode.Up),
        ):
            parameter = view.parameter_widget(node.id, name)
            assert parameter is not None and parameter.bounds_in_document.width > 0.0
            assert document.set_focus(parameter.handle)
            _key(document, key)

        caption = view.parameter_widget(node.id, "caption")
        assert caption is not None and document.set_focus(caption.handle)
        _key(document, KeyCode.A, int(ModifierFlag.Ctrl))
        assert document.dispatch_text_event("Граф café") == EventResult.Handled
        _key(document, KeyCode.Enter)

        expected = {
            "enabled": True, "mode": "quality", "count": (1 << 53) + 1, "gain": 0.75, "caption": "Граф café",
        }
        assert graph.nodes[node.id].params == expected
        assert events == [(node.id, name, value, value, value) for name, value in expected.items()]
        assert [type(event[2]) for event in events] == [bool, str, int, float, str]
        assert revisions == list(range(initial_revision + 1, initial_revision + 6))
    finally:
        view.close()


def test_cpp_view_replacement_keeps_controller_validator_and_graph_owner(document):
    class Validator:
        def __init__(self):
            self.allow = False
            self.proposals = []

        def validate(self, source_type, target_type, **endpoints):
            self.proposals.append((source_type, target_type, endpoints))
            return self.allow

    validator = Validator()
    original = Graph()
    controller = GraphController(original, validator=validator)
    controller.create_node("original", node_id="original")
    replacement = Graph()
    replacement_owner = weakref.ref(replacement)
    source, target = _pair(GraphController(replacement))
    view = CppNodeGraphView(document, controller)
    _mount(document, view)
    try:
        root = view.root_handle
        view.set_graph(replacement)
        assert controller.graph is replacement and controller.validator is validator
        del replacement
        gc.collect()
        assert replacement_owner() is not None
        assert view.root_handle == root
        _layout(document)
        ports = (
            _socket_position(view, source, output=True),
            _socket_position(view, target, output=False),
        )
        revision = controller.graph.revision
        _drag(document, *ports)
        assert controller.graph.revision == revision
        assert not controller.graph.edges
        assert any(
            (source_type, target_type) == ("number", "number")
            and endpoints["src_socket"] == "value-out"
            and endpoints["dst_socket"] == "value-in"
            for source_type, target_type, endpoints in validator.proposals
        )
        validator.allow = True
        _drag(document, *ports)
        assert controller.graph.revision == revision + 1
        assert len(controller.graph.edges) == 1
        assert list(original.nodes) == ["original"] and not original.edges
    finally:
        view.close()


def test_cpp_view_body_portal_survives_rebuild_and_retires_with_node(document):
    controller = GraphController()
    node = controller.create_node("preview", title="Preview", x=-100.0, y=-100.0)
    controller.set_node_param(node.id, "enabled", True)
    calls = []
    updates = []

    class Update:
        def __call__(self, node):
            updates.append(node.title)

    def provide(owner, snapshot):
        update = Update()
        calls.append((snapshot.id, weakref.ref(update)))
        body = owner.create_button("Body state")
        return NodeBodyContent(body.widget, NodeBodyLayout(height=48.0), update)

    view = CppNodeGraphView(document, controller, body_content_provider=provide)
    _mount(document, view)
    try:
        body = view.body_widget(node.id)
        parameter = view.parameter_widget(node.id, "enabled")
        assert body is not None and parameter is not None
        assert body.bounds_in_document.height == pytest.approx(48.0)
        assert document.hit_test(
            body.bounds_in_document.x + 10.0, body.bounds_in_document.y + 10.0,
        ) == body.handle
        assert len(calls) == 1 and calls[0][0] == node.id
        assert calls[0][1]() is not None

        controller.update_node(node.id, title="Updated")
        assert view.sync()
        _layout(document)
        assert updates == ["Updated"]
        assert view.body_widget(node.id).handle == body.handle
        assert body.alive
        assert not parameter.alive
        assert view.parameter_widget(node.id, "enabled").alive

        assert controller.remove_node(node.id)
        view.rebuild()
        assert not body.alive
        assert view.body_widget(node.id) is None
        gc.collect()
        assert calls[0][1]() is None
    finally:
        view.close()


def test_cpp_view_rejects_body_from_another_document(document):
    controller = GraphController()
    controller.create_node("preview")
    foreign_document = tc_ui_document_create()
    try:
        foreign = foreign_document.create_button("Foreign body")

        def provide(_owner, _snapshot):
            return NodeBodyContent(foreign.widget, NodeBodyLayout(height=30.0))

        live_before = document.live_widget_count
        with pytest.raises((RuntimeError, ValueError)):
            CppNodeGraphView(document, controller, body_content_provider=provide)
        assert foreign.widget.alive
        assert document.live_widget_count == live_before
    finally:
        tc_ui_document_destroy(foreign_document)


@pytest.mark.parametrize("teardown", ["close", "root", "document"])
def test_cpp_view_teardown_invalidates_handles_and_releases_callbacks(document, teardown):
    controller = GraphController()
    node = controller.create_node("controls", x=-120.0, y=-120.0)
    controller.set_node_param(node.id, "enabled", True)

    class Observer:
        def __call__(self, _revision):
            return None

    observer = Observer()
    observer_ref = weakref.ref(observer)
    view = CppNodeGraphView(document, controller, on_graph_changed=observer)
    _mount(document, view)
    root = document.ref(view.root_handle)
    parameter = view.parameter_widget(node.id, "enabled")
    assert parameter is not None
    del observer
    gc.collect()
    assert observer_ref() is not None

    if teardown == "document":
        tc_ui_document_destroy(document)
    elif teardown == "root":
        assert document.destroy_widget_recursive(root.handle)
    else:
        view.close()
    assert view.closed
    assert not root.alive and not parameter.alive
    gc.collect()
    assert observer_ref() is None
    view.close()


def test_cpp_view_document_releases_callback_cycle_on_root_removal(document):
    controller = GraphController()
    controller.create_node("controls", x=-120.0, y=-120.0)

    def create_view():
        def observer(_revision):
            return view.closed

        view = CppNodeGraphView(document, controller, on_graph_changed=observer)
        _mount(document, view)
        return weakref.ref(view), weakref.ref(observer), view.root_handle

    view, callback, root = create_view()
    gc.collect()
    assert view() is not None and callback() is not None
    assert document.is_alive(root)
    assert document.destroy_widget_recursive(root)
    gc.collect()
    assert view() is None and callback() is None
    assert not document.is_alive(root)


def test_cpp_view_rejects_structural_reentry_from_input_callback(document):
    controller = GraphController()
    node = controller.create_node("controls", x=-120.0, y=-120.0)
    controller.set_node_param(node.id, "enabled", False)
    errors = []

    def observer(_revision):
        for mutate in (view.rebuild, view.close):
            try:
                mutate()
            except RuntimeError as error:
                errors.append(str(error))

    view = CppNodeGraphView(document, controller, on_graph_changed=observer)
    _mount(document, view)
    try:
        parameter = view.parameter_widget(node.id, "enabled")
        assert document.set_focus(parameter.handle)
        _key(document, KeyCode.Enter)
        assert controller.graph.nodes[node.id].params["enabled"] is True
        assert len(errors) == 2
        assert all("callback" in error for error in errors)
        assert not view.closed and parameter.alive
    finally:
        view.close()


def test_cpp_view_guards_lazy_presentation_descriptors(document):
    controller = GraphController()
    node = controller.create_node("controls")
    controller.set_node_param(node.id, "caption", "text")
    blocked = []
    view = None

    def editors(_snapshot):
        if view is not None:
            with pytest.raises(RuntimeError, match="callback"):
                view.close()
            blocked.append(True)
        yield {"name": "caption", "kind": "text"}

    view = CppNodeGraphView(document, controller, parameter_editors=editors)
    try:
        assert view.rebuild()
        assert blocked and view.parameter_widget(node.id, "caption") is not None
    finally:
        view.close()


def test_cpp_view_failed_replacement_releases_native_view(document):
    controller = GraphController()
    controller.create_node("original")
    replacement = Graph()
    GraphController(replacement).create_node("replacement")

    def provide(owner, node):
        if node.kind == "replacement":
            raise ValueError("invalid replacement body")
        button = owner.create_button("Existing body")
        return NodeBodyContent(button.widget, NodeBodyLayout(height=30.0))

    view = CppNodeGraphView(document, controller, body_content_provider=provide)
    root = view.root_handle
    with pytest.raises(RuntimeError, match="replace"):
        view.set_graph(replacement)
    assert controller.graph is replacement
    assert view.closed and not document.is_alive(root)
    assert document.live_widget_count == 0


def test_cpp_view_presentation_callbacks_reach_native_pixels():
    controller = GraphController()
    source, _ = _pair(controller)
    palettes = []
    sockets = []
    labels = []
    caption = "Custom label"

    def node_palette(node):
        palettes.append(node.id)
        return {"body": (1.0, 0.0, 0.0, 1.0)}

    def socket_color(node, socket, direction):
        sockets.append((node.id, socket.name, direction, socket.is_input))
        return (0.0, 1.0, 0.0, 1.0)

    def socket_label(node, socket, direction):
        labels.append((node.id, socket.name, direction))
        return caption

    app = OffscreenGuiComposition(width=1000, height=700, continuous_rendering=False)
    try:
        document = app.document
        view = CppNodeGraphView(
            document, controller, node_palette=node_palette, socket_color=socket_color,
            socket_label=socket_label,
        )
        try:
            assert document.add_root(view.root_handle)
            assert app.render_frame()
            pixels = app.read_frame_rgba_float()
            bx, by = view.world_to_screen(source.x + 60.0, source.y + 100.0)
            sx, sy = _socket_position(view, source, output=True)
            assert pixels[int(by), int(bx), :3] == pytest.approx((1.0, 0.0, 0.0), abs=0.02)
            assert pixels[int(sy), int(sx), :3] == pytest.approx((0.0, 1.0, 0.0), abs=0.02)
            assert set(palettes) == {"source", "target"}
            assert ("source", "value-out", "output", False) in sockets
            assert ("target", "value-in", "input", True) in sockets
            assert ("target", "value-in", "input") in labels

            # Only the text changed. Compare the pixels inside the output
            # label row, away from its marker, to verify the label override.
            label_range = slice(int(sy) - 7, int(sy) + 8), slice(int(sx) - 90, int(sx) - 8)
            before = pixels[label_range].copy()
            caption = "I"
            view.rebuild()
            assert app.render_frame()
            after = app.read_frame_rgba_float()[label_range]
            assert (abs(before - after) > 0.1).any()
        finally:
            view.close()
    finally:
        app.close()
