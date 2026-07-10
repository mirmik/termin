"""DialogService — UI-agnostic dialog interface.

Models and controllers in `editor_core` ask for user input through this
interface. The tcgui frontend provides the concrete implementation.

All methods are callback-based so the modal overlay can satisfy the contract
uniformly. Callbacks receive ``None`` when the user cancels.
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

    def show_open_file(
        self,
        title: str,
        directory: str,
        filter_string: str,
        on_result: Callable[[str | None], None],
    ) -> None:
        """Choose an existing file asynchronously."""
        raise NotImplementedError("this dialog service does not support opening files")

    def show_save_file(
        self,
        title: str,
        directory: str,
        filter_string: str,
        on_result: Callable[[str | None], None],
        *,
        default_name: str = "",
    ) -> None:
        """Choose a destination file asynchronously."""
        raise NotImplementedError("this dialog service does not support saving files")
