"""About dialog for the Termin editor."""

from __future__ import annotations

import os
from importlib import metadata

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack


def _package_version() -> str:
    try:
        return metadata.version("termin-app")
    except metadata.PackageNotFoundError:
        return "development"


def _value_row(name: str, value: str) -> HStack:
    row = HStack()
    row.spacing = 8

    label = Label()
    label.text = name
    label.preferred_width = px(160)
    row.add_child(label)

    text = Label()
    text.text = value
    text.stretch = True
    row.add_child(text)

    return row


def show_about_dialog(ui, *, backend_name: str | None = None) -> None:
    """Show the editor About dialog."""
    env_backend = os.environ.get("TERMIN_BACKEND")
    resolved_env_backend = env_backend if env_backend else "(unset: compiled default)"
    resolved_backend_name = backend_name if backend_name else "unknown"

    content = VStack()
    content.spacing = 8

    title = Label()
    title.text = "Termin Editor"
    content.add_child(title)

    blurb = Label()
    blurb.text = "A suspiciously practical editor for projects that keep moving."
    content.add_child(blurb)

    content.add_child(_value_row("Version", _package_version()))
    content.add_child(_value_row("TERMIN_BACKEND", resolved_env_backend))
    content.add_child(_value_row("Active backend", resolved_backend_name))

    dlg = Dialog()
    dlg.title = "About Termin"
    dlg.content = content
    dlg.buttons = ["OK"]
    dlg.default_button = "OK"
    dlg.cancel_button = "OK"
    dlg.min_width = 460
    dlg.show(ui, windowed=True)
