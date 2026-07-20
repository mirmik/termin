from dataclasses import dataclass, field

from termin.editor_core.viewport_list_model import ViewportListController, ViewportNodeKind
from termin.editor_native import NativeViewportList, build_native_viewport_list
from termin.gui_native import Document, Rect


@dataclass
class _Viewport:
    name: str
    render_target: object | None = None
    internal_entities: object | None = None
    index: int = 1
    generation: int = 1

    def _viewport_handle(self) -> tuple[int, int]:
        return self.index, self.generation


@dataclass
class _Display:
    name: str
    handle: tuple[int, int]
    viewports: list[_Viewport] = field(default_factory=list)


@dataclass
class _RenderTarget:
    name: str
    kind: str = "texture_2d"
    index: int = 1
    generation: int = 1


def test_native_viewport_list_projects_selection_actions_and_rename():
    viewport = _Viewport("Game")
    display = _Display("Window", (10, 1), [viewport])
    target = _RenderTarget("Main")
    controller = ViewportListController()
    controller.set_displays([display])
    controller.set_render_targets([target])
    document = Document()
    dialogs = []

    def show_input(title, message, default, callback):
        dialogs.append((title, message, default))
        callback("Renamed")

    panel = build_native_viewport_list(
        document,
        controller,
        viewport=lambda: Rect(0.0, 0.0, 800.0, 600.0),
        request_render=lambda: None,
        show_input=show_input,
    )
    assert isinstance(panel, NativeViewportList)
    assert panel.tree_widget.visible_count == 4
    assert panel.status_bar.text == "Displays: 1 | Viewports: 1 | Targets: 1"

    display_additions = []
    controller.display_add_requested.connect(lambda: display_additions.append(True))
    panel.execute_action("add-display")
    assert display_additions == [True]

    viewport_node = next(
        node
        for stable_id, node in panel.id_nodes.items()
        if controller.snapshot.find(stable_id).kind == ViewportNodeKind.VIEWPORT
    )
    selected = []
    controller.viewport_selected.connect(selected.append)
    panel.select_node(viewport_node)
    assert selected == [viewport]

    added = []
    controller.viewport_add_requested.connect(added.append)
    panel.context_id = controller.display_stable_id(display)
    panel.execute_action("add-viewport")
    assert added == [display]

    removed_displays = []
    controller.display_remove_requested.connect(removed_displays.append)
    panel.execute_action("remove")
    assert removed_displays == [display]

    panel.context_id = controller.viewport_stable_id(viewport)
    panel.execute_action("rename")
    assert dialogs == [("Rename Viewport", "Name:", "Game")]
    assert viewport.name == "Renamed"

    panel.node_ids.clear()
    panel.id_nodes.clear()
    assert document.destroy_widget_recursive(panel.root.handle)
