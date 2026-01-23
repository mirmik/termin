"""ExecuteContext - context passed to render passes during execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.ui.canvas import Canvas
    from termin.lighting.light import Light


@dataclass
class ExecuteContext:
    """
    Context passed to RenderFramePass.execute().

    Contains all data needed by passes to render:
    - graphics: graphics backend
    - reads_fbos/writes_fbos: FBO maps for input/output
    - rect: pixel rectangle for rendering
    - scene, camera, viewport: what to render
    - context_key: for VAO/shader caching
    - lights: pre-computed lights
    - canvas: optional 2D canvas
    - layer_mask: which entity layers to render
    """
    graphics: "GraphicsBackend"
    reads_fbos: dict[str, "FramebufferHandle | None"]
    writes_fbos: dict[str, "FramebufferHandle | None"]
    rect: tuple[int, int, int, int]  # (px, py, pw, ph)
    scene: Optional["Scene"]
    camera: Optional["CameraComponent"]
    viewport: Optional["Viewport"] = None
    context_key: int = 0
    lights: Optional[list["Light"]] = None
    canvas: Optional["Canvas"] = None
    layer_mask: int = 0xFFFFFFFFFFFFFFFF
