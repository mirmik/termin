from dataclasses import dataclass, field

from termin.editor_tcgui.viewport_list_widget import ViewportListWidgetTcgui


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


def test_tcgui_viewport_list_is_projection_of_shared_controller():
    viewport = _Viewport("Game")
    display = _Display("Window", (10, 1), [viewport])
    target = _RenderTarget("Target")
    widget = ViewportListWidgetTcgui()
    selected = []
    widget.viewport_selected.connect(selected.append)

    widget.set_displays([display])
    widget.set_render_targets([target])

    assert [root.content.text for root in widget._tree.root_nodes] == [
        "Window",
        "Render Targets",
    ]
    viewport_node = widget._tree.root_nodes[0].subnodes[0]
    widget._on_tree_select(viewport_node)
    assert selected == [viewport]
    assert widget._controller.selected_display() is display

    widget._apply_viewport_rename(viewport, "Renamed")
    assert viewport.name == "Renamed"
    assert widget._tree.root_nodes[0].subnodes[0].content.text.startswith("Renamed")
