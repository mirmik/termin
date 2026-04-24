"""tcgui implementation of DialogService."""
from __future__ import annotations

from typing import Callable

from tcgui.widgets.input_dialog import show_input_dialog
from tcgui.widgets.message_box import MessageBox

from termin.editor_core.dialog_service import DialogService


class TcguiDialogService(DialogService):
    """Async dialog service for the tcgui editor.

    ``ui`` is the tcgui UI instance the dialogs attach to. It must be set
    before any dialog is shown (typically from EditorWindowTcgui once the UI
    is constructed).
    """

    def __init__(self):
        self.ui = None

    def show_error(
        self,
        title: str,
        message: str,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        MessageBox.error(
            self.ui,
            title=title,
            message=message,
            on_result=lambda _btn: on_close() if on_close is not None else None,
        )

    def show_input(
        self,
        title: str,
        message: str,
        default: str,
        on_result: Callable[[str | None], None],
    ) -> None:
        show_input_dialog(
            self.ui,
            title=title,
            message=message,
            default=default,
            on_result=on_result,
        )

    def show_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        on_result: Callable[[str | None], None],
        default: str | None = None,
        cancel: str | None = None,
    ) -> None:
        def _on_button(btn: str) -> None:
            if btn == cancel:
                on_result(None)
            else:
                on_result(btn)

        MessageBox.question(
            self.ui,
            title=title,
            message=message,
            buttons=choices,
            on_result=_on_button,
        )
