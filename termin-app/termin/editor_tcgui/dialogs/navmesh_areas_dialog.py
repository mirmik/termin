"""NavMesh Areas dialog - configure Detour area names."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack


def show_navmesh_areas_dialog(
    ui,
    on_changed: Callable[[], None] | None = None,
) -> None:
    """Show project-level navmesh area names dialog."""
    from termin.navmesh.settings import NAVMESH_AREA_COUNT, NavigationSettingsManager

    manager = NavigationSettingsManager.instance()

    col = VStack()
    col.spacing = 2
    edits: list[TextInput] = []

    for area_index in range(NAVMESH_AREA_COUNT):
        row = HStack()
        row.spacing = 4

        label = Label()
        label.text = f"{area_index:2d}"
        label.preferred_width = px(28)
        row.add_child(label)

        edit = TextInput()
        edit.text = manager.settings.navmesh_area_names[area_index]
        edit.placeholder = f"Area {area_index}"
        edit.stretch = True
        row.add_child(edit)

        col.add_child(row)
        edits.append(edit)

    scroll = ScrollArea()
    scroll.add_child(col)
    scroll.preferred_height = px(400)

    dlg = Dialog()
    dlg.title = "NavMesh Areas"
    dlg.content = scroll
    dlg.buttons = ["OK", "Cancel"]
    dlg.default_button = "OK"
    dlg.cancel_button = "Cancel"
    dlg.min_width = 420

    def _on_result(btn: str):
        if btn != "OK":
            return
        for area_index in range(NAVMESH_AREA_COUNT):
            manager.set_navmesh_area_name(area_index, edits[area_index].text)
        manager.save()
        if on_changed is not None:
            on_changed()

    dlg.on_result = _on_result
    dlg.show(ui, windowed=True)
