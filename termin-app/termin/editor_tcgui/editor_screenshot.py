"""Screenshot helpers for the tcgui editor viewport."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from termin.mcp.screenshot import capture_surface_screenshot


def capture_editor_viewport_screenshot(
    editor: Any,
    *,
    output_path: str | None = None,
    include_image: bool = False,
) -> dict[str, object]:
    """Read the editor display output and save it as a PNG image."""
    display = editor._editor_display
    device = editor._ctx.device
    return capture_surface_screenshot(
        display,
        device,
        output_path=output_path,
        include_image=include_image,
        default_dir=Path(tempfile.gettempdir()) / "termin-editor-screenshots",
        default_prefix="termin-editor",
        log_prefix="EditorScreenshot",
    )
