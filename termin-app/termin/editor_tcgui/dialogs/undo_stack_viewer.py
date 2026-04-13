"""Undo Stack Viewer — debug dialog showing done/undone commands."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.vstack import VStack
from tcgui.widgets.label import Label
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.button import Button
from tcgui.widgets.units import px

from termin.editor.undo_stack import UndoStack


def show_undo_stack_viewer(ui, undo_stack: UndoStack) -> None:
    """Show non-modal undo stack viewer."""
    content = VStack()
    content.spacing = 4

    cols = HStack()
    cols.spacing = 8
    cols.preferred_height = px(300)

    # Done (undo) column
    done_col = VStack()
    done_col.spacing = 2
    done_col.stretch = True
    done_lbl = Label()
    done_lbl.text = "Done (Undo)"
    done_col.add_child(done_lbl)
    done_list = ListWidget()
    done_list.stretch = True
    done_list.item_height = 22
    done_col.add_child(done_list)
    cols.add_child(done_col)

    # Undone (redo) column
    undone_col = VStack()
    undone_col.spacing = 2
    undone_col.stretch = True
    undone_lbl = Label()
    undone_lbl.text = "Undone (Redo)"
    undone_col.add_child(undone_lbl)
    undone_list = ListWidget()
    undone_list.stretch = True
    undone_list.item_height = 22
    undone_col.add_child(undone_list)
    cols.add_child(undone_col)

    content.add_child(cols)

    # Refresh button
    refresh_btn = Button()
    refresh_btn.text = "Refresh"
    refresh_btn.padding = 6

    def _refresh():
        done_items = []
        for i, cmd in enumerate(undo_stack.done_commands):
            text = cmd.text if cmd.text else cmd.__class__.__name__
            done_items.append({"text": f"[undo #{i}] {text}"})
        done_list.set_items(done_items)

        undone_items = []
        for i, cmd in enumerate(undo_stack.undone_commands):
            text = cmd.text if cmd.text else cmd.__class__.__name__
            undone_items.append({"text": f"[redo #{i}] {text}"})
        undone_list.set_items(undone_items)

    _refresh()
    refresh_btn.on_click = _refresh
    content.add_child(refresh_btn)

    dlg = Dialog()
    dlg.title = "Undo/Redo Stack"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 500

    dlg.show(ui, windowed=True)
