from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, List


@dataclass
class FrameExecutionContext:
    graphics: "GraphicsBackend"
    window: "Window"
    viewport: "Viewport"
    rect: Tuple[int, int, int, int]  # (px, py, pw, ph)

    # карта ресурс -> FBO (или None, если это swapchain/экран)
    fbos: Dict[str, "FramebufferHandle" | None]


@dataclass
class FrameContext:
    window: "Window"
    viewport: "Viewport"
    rect: Tuple[int, int, int, int]
    size: Tuple[int, int]
    graphics: "GraphicsBackend"
    fbos: Dict[str, Any] = field(default_factory=dict)
    # Предвычисленные источники света для текущего кадра/вьюпорта.
    lights: List["Light"] | None = None
