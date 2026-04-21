"""Qt implementation of DialogService."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QInputDialog, QMessageBox, QWidget

from termin.editor_core.dialog_service import DialogService


class QtDialogService(DialogService):
    _parent: QWidget | None

    def __init__(self, parent: QWidget | None = None):
        self._parent = parent

    def show_error(
        self,
        title: str,
        message: str,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        QMessageBox.critical(self._parent, title, message)
        if on_close is not None:
            on_close()

    def show_input(
        self,
        title: str,
        message: str,
        default: str,
        on_result: Callable[[str | None], None],
    ) -> None:
        text, ok = QInputDialog.getText(self._parent, title, message, text=default)
        on_result(text if ok else None)

    def show_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        on_result: Callable[[str | None], None],
        default: str | None = None,
        cancel: str | None = None,
    ) -> None:
        box = QMessageBox(self._parent)
        box.setWindowTitle(title)
        box.setText(message)

        buttons = {}
        for label in choices:
            if label == cancel:
                role = QMessageBox.ButtonRole.RejectRole
            elif label == default:
                role = QMessageBox.ButtonRole.AcceptRole
            else:
                role = QMessageBox.ButtonRole.ActionRole
            buttons[box.addButton(label, role)] = label

        default_button = next((b for b, lbl in buttons.items() if lbl == default), None)
        if default_button is not None:
            box.setDefaultButton(default_button)

        box.exec()
        clicked = box.clickedButton()
        chosen = buttons.get(clicked)
        if chosen == cancel:
            on_result(None)
        else:
            on_result(chosen)
