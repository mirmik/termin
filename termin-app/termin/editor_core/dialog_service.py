"""DialogService — UI-agnostic dialog interface.

Models and controllers in `editor_core` ask for user input through this
interface. Qt and tcgui provide concrete implementations in their own
packages.

All methods are callback-based so both sync (Qt `exec()`) and async (tcgui
modal overlay) backends can satisfy the contract uniformly. Callbacks
receive ``None`` when the user cancels.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class DialogService(ABC):
    @abstractmethod
    def show_error(
        self,
        title: str,
        message: str,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        """Show a modal error message."""

    @abstractmethod
    def show_input(
        self,
        title: str,
        message: str,
        default: str,
        on_result: Callable[[str | None], None],
    ) -> None:
        """Ask the user for a text value.

        ``on_result`` is called with the entered string on OK, or ``None`` on
        Cancel.
        """

    @abstractmethod
    def show_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        on_result: Callable[[str | None], None],
        default: str | None = None,
        cancel: str | None = None,
    ) -> None:
        """Show a multi-button choice dialog.

        ``on_result`` is called with the chosen label, or ``None`` if the user
        dismissed the dialog. ``cancel`` names the label that counts as a
        dismissal — useful for keyboard Esc.
        """
