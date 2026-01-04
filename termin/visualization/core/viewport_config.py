"""ViewportConfig - configuration for scene viewport mounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class ViewportConfig:
    """
    Configuration for mounting a scene viewport to a display.

    Stored in Scene.viewport_configs and used by RenderingManager.attach_scene()
    to create viewports on appropriate displays.
    """

    # Display name (RenderingManager will create/find display by this name)
    display_name: str = "Main"

    # Camera entity UUID (looked up in scene during attach)
    camera_uuid: str = ""

    # Normalized region on display (x, y, width, height)
    region: Tuple[float, float, float, float] = field(default=(0.0, 0.0, 1.0, 1.0))

    # Pipeline name (None = use default)
    pipeline_name: str | None = None

    # Viewport depth (for ordering when multiple viewports on same display)
    depth: int = 0

    # Input mode for this viewport ("none", "simple", "editor")
    input_mode: str = "simple"

    # Block input when running in editor mode
    block_input_in_editor: bool = False

    def serialize(self) -> dict:
        """Serialize to dict."""
        result = {
            "display_name": self.display_name,
            "camera_uuid": self.camera_uuid,
            "region": list(self.region),
            "depth": self.depth,
            "input_mode": self.input_mode,
            "block_input_in_editor": self.block_input_in_editor,
        }
        if self.pipeline_name is not None:
            result["pipeline_name"] = self.pipeline_name
        return result

    @classmethod
    def deserialize(cls, data: dict) -> "ViewportConfig":
        """Deserialize from dict."""
        region = data.get("region", [0.0, 0.0, 1.0, 1.0])
        return cls(
            display_name=data.get("display_name", "Main"),
            camera_uuid=data.get("camera_uuid", ""),
            region=tuple(region),
            pipeline_name=data.get("pipeline_name"),
            depth=data.get("depth", 0),
            input_mode=data.get("input_mode", "simple"),
            block_input_in_editor=data.get("block_input_in_editor", False),
        )
