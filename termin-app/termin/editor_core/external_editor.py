"""
External text editor integration.

Opens files in the configured external editor or system default.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Callable

from tcbase import log

from termin.editor_core.settings import EditorSettings


def open_in_text_editor(
    file_path: str,
    log_message: Callable[[str], None] | None = None,
) -> bool:
    """
    Open file in external text editor.

    Uses editor from settings if configured, otherwise system default.

    Args:
        file_path: Path to file to open
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
        log.error(f"Failed to open file in text editor: {file_path}: {e}")
        return False


def reveal_in_file_manager(path: str | Path) -> bool:
    """Reveal a project path using the platform file manager."""
    target = Path(path)
    try:
        system = platform.system()
        if system == "Windows":
            if target.is_file():
                subprocess.Popen(["explorer", "/select,", str(target)])
            else:
                subprocess.Popen(["explorer", str(target)])
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target.parent if target.is_file() else target)])
        return True
    except Exception as exc:
        log.error(f"Failed to reveal path in file manager: {target}: {exc}")
        return False
