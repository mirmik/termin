"""Inspect Registry Viewer — shows registered types, fields, backends."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.table_widget import TableWidget, TableColumn
from tcgui.widgets.button import Button
from tcgui.widgets.units import px


def show_inspect_registry_viewer(ui) -> None:
    """Show Inspect Registry viewer dialog."""
    from tcbase import log

    try:
        from termin._native.inspect import InspectRegistry
        registry = InspectRegistry.instance()
    except ImportError:
        log.error("InspectRegistry not available")
        return

    content = VStack()
    content.spacing = 4

    # Filter row
    filter_row = HStack()
    filter_row.spacing = 4
    filter_lbl = Label()
    filter_lbl.text = "Filter:"
    filter_row.add_child(filter_lbl)
    filter_input = TextInput()
    filter_input.placeholder = "Type name..."
    filter_input.stretch = True
    filter_row.add_child(filter_input)
    content.add_child(filter_row)

    # Main area: list + details
    main_row = HStack()
    main_row.spacing = 8
    main_row.preferred_height = px(400)

    # Left: types table
    types_list = TableWidget()
    types_list.set_columns([
        TableColumn("Type"),
        TableColumn("Backend", 80),
        TableColumn("Parent"),
        TableColumn("Fields", 80),
    ])
    types_list.preferred_width = px(400)
    types_list.stretch = True

    # Right: details
    details = TextArea()
    details.read_only = True
    details.word_wrap = False
    details.stretch = True
    details.placeholder = "Select a type to view details"

    main_row.add_child(types_list)
    main_row.add_child(details)
    content.add_child(main_row)

    # Status
    status_lbl = Label()
    status_lbl.text = ""
    content.add_child(status_lbl)

    # All types data (for filtering)
    all_rows: list[list[str]] = []
    all_data: list[str] = []

    def _refresh():
        all_rows.clear()
        all_data.clear()
        type_names = registry.types()

        for type_name in sorted(type_names):
            backend = registry.get_type_backend(type_name)
            backend_str = backend.name if hasattr(backend, 'name') else str(backend)
            parent = registry.get_type_parent(type_name) or "-"
            own_fields = registry.fields(type_name)
            all_fields = registry.all_fields(type_name)
            field_count = f"{len(own_fields)}/{len(all_fields)}"

            all_rows.append([type_name, backend_str, parent, field_count])
            all_data.append(type_name)

        _apply_filter()
        status_lbl.text = f"Types: {len(type_names)}"

    def _apply_filter():
        text = filter_input.text.lower()
        if text:
            rows = []
            data = []
            for r, d in zip(all_rows, all_data):
                if text in d.lower():
                    rows.append(r)
                    data.append(d)
            types_list.set_rows(rows, data)
        else:
            types_list.set_rows(list(all_rows), list(all_data))
        details.text = ""

    filter_input.on_text_changed = lambda _: _apply_filter()

    def _on_select(idx, type_name):
        if type_name is None:
            return
        _show_type_details(type_name)

    def _show_type_details(type_name: str):
        backend = registry.get_type_backend(type_name)
        backend_str = backend.name if hasattr(backend, 'name') else str(backend)
        parent = registry.get_type_parent(type_name) or "(none)"
        own_fields = registry.fields(type_name)
        all_fields = registry.all_fields(type_name)

        lines = [
            f"=== {type_name} ===",
            "",
            f"Backend:        {backend_str}",
            f"Parent:         {parent}",
            f"Own fields:     {len(own_fields)}",
            f"Total fields:   {len(all_fields)}",
            "",
            "--- Own Fields ---",
        ]

        if own_fields:
            for f in own_fields:
                lines.append(f"  {f.path}")
                lines.append(f"    label: {f.label}")
                lines.append(f"    kind:  {f.kind}")
                if f.min is not None or f.max is not None:
                    lines.append(f"    range: [{f.min}, {f.max}]")
                if f.step is not None:
                    lines.append(f"    step:  {f.step}")
                if f.choices:
                    choices_str = ", ".join(f"{c.value}={c.label}" for c in f.choices)
                    lines.append(f"    choices: {choices_str}")
                if not f.is_serializable:
                    lines.append(f"    is_serializable: False")
                if not f.is_inspectable:
                    lines.append(f"    is_inspectable: False")
                lines.append("")
        else:
            lines.append("  (none)")
            lines.append("")

        inherited = [f for f in all_fields if f not in own_fields]
        if inherited:
            lines.append("--- Inherited Fields ---")
            for f in inherited:
                lines.append(f"  {f.path} (kind: {f.kind})")
            lines.append("")

        details.text = "\n".join(lines)

    types_list.on_select = _on_select

    # Refresh button
    btn_row = HStack()
    btn_row.spacing = 4
    refresh_btn = Button()
    refresh_btn.text = "Refresh"
    refresh_btn.padding = 6
    refresh_btn.on_click = _refresh
    btn_row.add_child(refresh_btn)
    content.add_child(btn_row)

    _refresh()

    dlg = Dialog()
    dlg.title = "Inspect Registry Viewer"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 800

    dlg.show(ui, windowed=True)
