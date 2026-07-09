from tcgui.widgets.events import DragEvent, DragPayload
from tcgui.widgets.ui import UI
from tcgui.widgets.widget import Widget

from termin.editor_tcgui.editor_window import EditorWindowTcgui
from termin.editor_tcgui.scene_tree_controller import SceneTreeControllerTcgui


def _project_file_event(path: str, extension: str) -> DragEvent:
    return DragEvent(
        x=12.0,
        y=16.0,
        payload=DragPayload(
            "project_file",
            {
                "path": path,
                "extension": extension,
                "name": path.rsplit("/", 1)[-1],
            },
        ),
    )


class _DropWidget(Widget):
    def __init__(self) -> None:
        super().__init__()
        self.drag_moves: int = 0
        self.drop_events: list[DragEvent] = []

    def on_drag_move(self, event: DragEvent) -> bool:
        self.drag_moves += 1
        return event.payload.kind == "project_file"

    def on_drag_drop(self, event: DragEvent) -> bool:
        self.drop_events.append(event)
        return True


class _Ops:
    def __init__(self) -> None:
        self.glb_drops: list[tuple[str, object | None]] = []
        self.prefab_drops: list[tuple[str, object | None]] = []

    def drop_glb(self, path: str, parent) -> None:
        self.glb_drops.append((path, parent))

    def drop_prefab(self, path: str, parent) -> None:
        self.prefab_drops.append((path, parent))


def test_ui_external_drop_routes_payload_to_widget() -> None:
    ui = UI.__new__(UI)
    ui._root = Widget()
    ui._overlays = []
    ui._tooltip_widget = None

    ui._root.layout(0.0, 0.0, 100.0, 100.0, 100.0, 100.0)
    drop_widget = _DropWidget()
    drop_widget.layout(10.0, 10.0, 20.0, 20.0, 100.0, 100.0)
    ui._root.add_child(drop_widget)

    payload = DragPayload(
        "project_file",
        {"path": "/tmp/Bush.gltf", "extension": ".gltf", "name": "Bush.gltf"},
    )

    assert ui.external_drop(12.0, 16.0, payload)
    assert drop_widget.drag_moves == 1
    assert drop_widget.drop_events[0].payload is payload


def test_viewport_accepts_gltf_drag() -> None:
    win = EditorWindowTcgui.__new__(EditorWindowTcgui)

    assert win._on_viewport_external_drag(_project_file_event("/tmp/Bush.gltf", ".gltf"))
    assert win._on_viewport_external_drag(_project_file_event("/tmp/Bush.glb", ".glb"))
    assert not win._on_viewport_external_drag(_project_file_event("/tmp/Bush.obj", ".obj"))


def test_scene_tree_drops_gltf_as_model() -> None:
    controller = SceneTreeControllerTcgui.__new__(SceneTreeControllerTcgui)
    controller._ops = _Ops()
    event = _project_file_event("/tmp/Bush.gltf", ".gltf")

    assert controller._on_external_drag(event, None, "root")
    assert controller._on_external_drop(event, None, "root")
    assert controller._ops.glb_drops == [("/tmp/Bush.gltf", None)]
    assert controller._ops.prefab_drops == []


def test_scene_tree_drops_prefab_but_not_legacy_tc_prefab() -> None:
    controller = SceneTreeControllerTcgui.__new__(SceneTreeControllerTcgui)
    controller._ops = _Ops()
    prefab_event = _project_file_event("/tmp/Tree.prefab", ".prefab")
    legacy_event = _project_file_event("/tmp/Tree.tc_prefab", ".tc_prefab")

    assert controller._on_external_drag(prefab_event, None, "root")
    assert controller._on_external_drop(prefab_event, None, "root")
    assert not controller._on_external_drag(legacy_event, None, "root")
    assert not controller._on_external_drop(legacy_event, None, "root")
    assert controller._ops.prefab_drops == [("/tmp/Tree.prefab", None)]
