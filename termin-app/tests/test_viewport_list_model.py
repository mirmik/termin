from dataclasses import dataclass, field

import pytest

from termin.editor_core.viewport_list_model import ViewportListController, ViewportNodeKind


class _Transform:
    def __init__(self, entity=None) -> None:
        self.entity = entity
        self.children = []


class _Entity:
    def __init__(self, name: str, uuid: str) -> None:
        self.name = name
        self.uuid = uuid
        self.transform = _Transform(self)
        self.alive = True

    def valid(self) -> bool:
        return self.alive


@dataclass
class _RenderTarget:
    name: str
    kind: str = "texture_2d"
    index: int = 1
    generation: int = 1


@dataclass
class _Viewport:
    name: str
    render_target: _RenderTarget | None = None
    internal_entities: _Entity | None = None
    index: int = 1
    generation: int = 1

    def _viewport_handle(self) -> tuple[int, int]:
        return self.index, self.generation


@dataclass
class _Display:
    name: str
    tc_display_ptr: int
    viewports: list[_Viewport] = field(default_factory=list)


def _find_kind(snapshot, kind):
    pending = list(snapshot.roots)
    while pending:
        node = pending.pop(0)
        if node.kind == kind:
            return node
        pending[0:0] = node.children
    raise AssertionError(f"missing node kind {kind}")


def test_viewport_list_snapshot_hierarchy_selection_and_names():
    child = _Entity("Child", "child-uuid")
    root = _Entity("Root", "root-uuid")
    root.transform.children.append(child.transform)
    target = _RenderTarget("MainTarget")
    viewport = _Viewport("Game", target, root)
    display = _Display("Window", 10, [viewport])
    xr_target = _RenderTarget("Headset", "xr_stereo", index=2)
    controller = ViewportListController()

    snapshot = controller.set_displays([display])
    snapshot = controller.set_render_targets([target, xr_target])

    assert snapshot.roots[0].label == "Window"
    assert snapshot.roots[0].children[0].label == "Game (MainTarget)"
    assert snapshot.roots[0].children[0].children[0].label == "Root"
    assert snapshot.roots[0].children[0].children[0].children[0].label == "Child"
    assert snapshot.roots[1].children[1].label == "Headset [XR Stereo]"

    selected = []
    controller.viewport_selected.connect(lambda value: selected.append(value))
    viewport_node = _find_kind(snapshot, ViewportNodeKind.VIEWPORT)
    controller.select(viewport_node.stable_id)
    assert selected == [viewport]
    assert controller.selected_display() is display

    controller.set_display_name(display, "Preview")
    assert controller.snapshot.roots[0].label == "Preview"

    replacement_viewport = _Viewport("Game Reloaded", target, root)
    replacement_display = _Display("Replacement Wrapper", 10, [replacement_viewport])
    controller.set_displays([replacement_display])
    assert controller.snapshot.selected_id == viewport_node.stable_id
    assert controller.snapshot.find(viewport_node.stable_id).value is replacement_viewport
    assert controller.snapshot.roots[0].label == "Preview"


def test_viewport_list_actions_rename_and_stale_selection_reconciliation():
    viewport = _Viewport("Game")
    display = _Display("Window", 11, [viewport])
    target = _RenderTarget("Target")
    controller = ViewportListController()
    controller.set_displays([display])
    snapshot = controller.set_render_targets([target])
    display_node = _find_kind(snapshot, ViewportNodeKind.DISPLAY)
    viewport_node = _find_kind(snapshot, ViewportNodeKind.VIEWPORT)
    target_node = _find_kind(snapshot, ViewportNodeKind.RENDER_TARGET)
    events = []
    controller.viewport_add_requested.connect(lambda value: events.append(("add-vp", value)))
    controller.viewport_remove_requested.connect(lambda value: events.append(("remove-vp", value)))
    controller.render_target_remove_requested.connect(lambda value: events.append(("remove-rt", value)))
    controller.render_target_add_requested.connect(lambda value: events.append(("add-rt", value)))

    controller.select(display_node.stable_id)
    controller.request_add_viewport()
    controller.request_remove(viewport_node.stable_id)
    controller.request_remove(target_node.stable_id)
    controller.request_add_render_target("xr_stereo")
    controller.rename(viewport_node.stable_id, " Renamed ")
    controller.rename(target_node.stable_id, " NewTarget ")

    assert viewport.name == "Renamed"
    assert target.name == "NewTarget"
    assert events == [
        ("add-vp", display),
        ("remove-vp", viewport),
        ("remove-rt", target),
        ("add-rt", "xr_stereo"),
    ]

    controller.select(controller.viewport_stable_id(viewport))
    display.viewports.clear()
    controller.refresh()
    assert controller.snapshot.selected_id is None

    with pytest.raises(ValueError, match="name cannot be empty"):
        controller.rename(target_node.stable_id, "   ")
