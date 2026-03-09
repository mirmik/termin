"""Layers & Flags dialog — configure 64 layer names and 64 flag names."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.tabs import TabView
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.units import px

_COUNT = 64


def _build_names_tab(names: dict, prefix: str) -> tuple[VStack, list[TextInput]]:
    """Build a scrollable list of 64 text inputs."""
    col = VStack()
    col.spacing = 2
    edits: list[TextInput] = []
    for i in range(_COUNT):
        row = HStack()
        row.spacing = 4
        lbl = Label()
        lbl.text = f"{i:2d}"
        lbl.preferred_width = px(24)
        row.add_child(lbl)
        inp = TextInput()
        inp.text = names.get(i, "")
        inp.placeholder = f"{prefix} {i}"
        inp.stretch = True
        row.add_child(inp)
        col.add_child(row)
        edits.append(inp)
    return col, edits


def show_layers_dialog(ui, scene) -> None:
    """Show modal layers & flags dialog."""
    layer_names = scene.layer_names if hasattr(scene, "layer_names") else {}
    flag_names = scene.flag_names if hasattr(scene, "flag_names") else {}

    tabs = TabView()
    tabs.preferred_height = px(400)

    layers_col, layer_edits = _build_names_tab(layer_names, "Layer")
    layers_scroll = ScrollArea()
    layers_scroll.add_child(layers_col)
    tabs.add_tab("Layers", layers_scroll)

    flags_col, flag_edits = _build_names_tab(flag_names, "Flag")
    flags_scroll = ScrollArea()
    flags_scroll.add_child(flags_col)
    tabs.add_tab("Flags", flags_scroll)

    dlg = Dialog()
    dlg.title = "Layers & Flags"
    dlg.content = tabs
    dlg.buttons = ["OK", "Cancel"]
    dlg.default_button = "OK"
    dlg.cancel_button = "Cancel"
    dlg.min_width = 400

    def _on_result(btn: str):
        if btn != "OK":
            return
        for i in range(_COUNT):
            name = layer_edits[i].text.strip()
            scene.set_layer_name(i, name)
        for i in range(_COUNT):
            name = flag_edits[i].text.strip()
            scene.set_flag_name(i, name)

    dlg.on_result = _on_result
    dlg.show(ui, windowed=True)
