"""Shared application-icon setup for Termin's SDL windows."""

from __future__ import annotations

from pathlib import Path

from tcbase import log


_ICON_PATH = Path(__file__).resolve().parents[1] / "resources" / "icons" / "termin-editor-icon.bmp"


def editor_icon_path() -> Path:
    """Return the packaged BMP used by SDL for editor-family windows."""

    return _ICON_PATH


def apply_editor_window_icon(window) -> bool:
    """Apply the packaged editor icon, logging a visible error on failure."""

    path = editor_icon_path()
    if not path.is_file():
        log.error(f"[application_icon] packaged editor icon is missing: {path}")
        return False

    try:
        window.set_icon_bmp(str(path))
    except RuntimeError as error:
        log.error(f"[application_icon] failed to apply editor icon: {error}")
        return False
    return True
