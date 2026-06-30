"""Shared UI scaffold for registry-style diagnostics dialogs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tcgui.widgets.button import Button
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.tabs import TabView
from tcgui.widgets.table_widget import TableColumn, TableWidget
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack
from tcgui.widgets.widget import Widget


TableSelectHandler = Callable[[int, Any], None]


class RegistryViewerDialog:
    """Common two-pane shell for registry/resource diagnostics viewers."""

    def __init__(
        self,
        title: str,
        tab_columns: dict[str, list[TableColumn]],
        *,
        content_height: float = 500,
        details_width: float = 400,
        min_width: float = 900,
        details_placeholder: str = "Select an item to view details",
    ) -> None:
        self.title = title
        self.min_width = min_width

        self.content = HStack()
        self.content.spacing = 8
        self.content.preferred_height = px(content_height)

        self.left_panel = VStack()
        self.left_panel.spacing = 4
        self.left_panel.stretch = True

        self.tabs = TabView()
        self.tabs.stretch = True

        self.tab_lists: dict[str, TableWidget] = {}
        for name, columns in tab_columns.items():
            table = TableWidget()
            table.set_columns(columns)
            table.stretch = True
            self.tab_lists[name] = table
            self.tabs.add_tab(name, table)

        self.left_panel.add_child(self.tabs)

        self.status_label = Label()
        self.status_label.text = ""
        self.left_panel.add_child(self.status_label)

        self.content.add_child(self.left_panel)

        self.right_panel = VStack()
        self.right_panel.spacing = 4
        self.right_panel.preferred_width = px(details_width)

        self.details = TextArea()
        self.details.read_only = True
        self.details.word_wrap = False
        self.details.stretch = True
        self.details.placeholder = details_placeholder
        self.right_panel.add_child(self.details)

        self.button_row = HStack()
        self.button_row.spacing = 4
        self.right_panel.add_child(self.button_row)

        self.content.add_child(self.right_panel)

    def add_tab(self, name: str, widget: Widget) -> Widget:
        """Add a non-table tab to the shared tab view."""
        self.tabs.add_tab(name, widget)
        return widget

    def add_button(self, text: str, on_click: Callable[[], None]) -> Button:
        """Add an action button to the details pane."""
        button = Button()
        button.text = text
        button.padding = 6
        button.on_click = on_click
        self.button_row.add_child(button)
        return button

    def set_table_select_handler(self, handler: TableSelectHandler) -> None:
        """Wire the same selection handler to every table tab."""
        for table in self.tab_lists.values():
            table.on_select = handler

    def show(self, ui, *, windowed: bool = True) -> None:
        """Create and show the backing Dialog."""
        dlg = Dialog()
        dlg.title = self.title
        dlg.content = self.content
        dlg.buttons = ["Close"]
        dlg.default_button = "Close"
        dlg.cancel_button = "Close"
        dlg.min_width = self.min_width
        dlg.show(ui, windowed=windowed)
