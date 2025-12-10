"""
External text editor integration.

Opens files in the configured external editor or system default.
"""

from __future__ import annotations

import os
import platform
import subprocess
from typing import Callable

from PyQt6.QtWidgets import QWidget, QMessageBox

from termin.editor.settings import EditorSettings


def open_in_text_editor(
    file_path: str,
    parent: QWidget | None = None,
    log_message: Callable[[str], None] | None = None,
) -> bool:
    """
    Open file in external text editor.

    Uses editor from settings if configured, otherwise system default.

    Args:
        file_path: Path to file to open
        parent: Parent widget for error dialogs
        log_message: Optional callback for logging

    Returns:
        True if successful, False otherwise
    """
    settings = EditorSettings.instance()
    editor = settings.get_text_editor()

    try:
        if editor:
            subprocess.Popen([editor, file_path])
        else:
            system = platform.system()
            if system == "Windows":
                os.startfile(file_path)
            elif system == "Darwin":  # macOS
                subprocess.Popen(["open", file_path])
            else:  # Linux
                subprocess.Popen(["xdg-open", file_path])

        if log_message:
            log_message(f"Opened in editor: {file_path}")
        return True

    except Exception as e:
        if parent is not None:
            QMessageBox.warning(
                parent,
                "Error",
                f"Failed to open file in text editor:\n{file_path}\n\nError: {e}",
            )
        return False
