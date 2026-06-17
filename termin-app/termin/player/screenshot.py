"""Screenshot helpers for the packaged/player runtime."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from termin.mcp.screenshot import capture_surface_screenshot

if TYPE_CHECKING:
    from termin.player.runtime import PlayerRuntime


def capture_player_screenshot(
    runtime: "PlayerRuntime",
    *,
    output_path: str | None = None,
    include_image: bool = False,
) -> dict[str, object]:
    """Read the player runtime render surface and save it as a PNG image."""
    from termin.visualization.render.manager import RenderingManager

    render_engine = RenderingManager.instance().render_engine
    if render_engine is None:
        raise RuntimeError("No render engine is available")
    render_engine.ensure_tgfx2()
    device = render_engine.tgfx2_device
    if device is None:
        raise RuntimeError("No tgfx2 device is available")

    return capture_surface_screenshot(
        runtime.surface,
        device,
        output_path=output_path,
        include_image=include_image,
        default_dir=Path(tempfile.gettempdir()) / "termin-player-screenshots",
        default_prefix="termin-player",
        log_prefix="PlayerScreenshot",
    )
