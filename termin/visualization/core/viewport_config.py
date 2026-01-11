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

    # Viewport name (used for scene pipeline targeting)
    name: str = ""

    # Display name (RenderingManager will create/find display by this name)
    display_name: str = "Main"

    # Camera entity UUID (looked up in scene during attach)
    camera_uuid: str = ""

    # Normalized region on display (x, y, width, height)
    region: Tuple[float, float, float, float] = field(default=(0.0, 0.0, 1.0, 1.0))

    # Pipeline UUID (None = use default or pipeline_name)
    pipeline_uuid: str | None = None

    # Pipeline name for special pipelines (e.g., "(Editor)")
    # Used when pipeline_uuid is None
    pipeline_name: str | None = None

    # Viewport depth (for ordering when multiple viewports on same display)
    depth: int = 0

    # Input mode for this viewport ("none", "simple", "editor")
    input_mode: str = "simple"

    # Block input when running in editor mode
    block_input_in_editor: bool = False

    # Layer mask (which entity layers to render)
    layer_mask: int = 0xFFFFFFFFFFFFFFFF

    def serialize(self) -> dict:
        """Serialize to dict."""
        result = {
            "name": self.name,
            "display_name": self.display_name,
            "camera_uuid": self.camera_uuid,
            "region": list(self.region),
            "depth": self.depth,
            "input_mode": self.input_mode,
            "block_input_in_editor": self.block_input_in_editor,
        }
        if self.pipeline_uuid is not None:
            result["pipeline_uuid"] = self.pipeline_uuid
        if self.pipeline_name is not None:
            result["pipeline_name"] = self.pipeline_name
        # Only serialize layer_mask if not all layers
        if self.layer_mask != 0xFFFFFFFFFFFFFFFF:
            result["layer_mask"] = hex(self.layer_mask)
        return result

    @classmethod
    def deserialize(cls, data: dict) -> "ViewportConfig":
        """Deserialize from dict."""
        region = data.get("region", [0.0, 0.0, 1.0, 1.0])

        pipeline_uuid = data.get("pipeline_uuid")
        pipeline_name = data.get("pipeline_name")

        # Backwards compatibility: convert old pipeline_name (asset name) to uuid
        # But preserve special names like "(Editor)"
        if pipeline_uuid is None and pipeline_name and not pipeline_name.startswith("("):
            pipeline_uuid = _get_pipeline_uuid_by_name(pipeline_name)
            pipeline_name = None  # Clear old-style name after conversion

        # Parse layer_mask (may be hex string or int)
        layer_mask_raw = data.get("layer_mask", 0xFFFFFFFFFFFFFFFF)
        if isinstance(layer_mask_raw, str):
            layer_mask = int(layer_mask_raw, 16) if layer_mask_raw.startswith("0x") else int(layer_mask_raw)
        else:
            layer_mask = int(layer_mask_raw)

        return cls(
            name=data.get("name", ""),
            display_name=data.get("display_name", "Main"),
            camera_uuid=data.get("camera_uuid", ""),
            region=tuple(region),
            pipeline_uuid=pipeline_uuid,
            pipeline_name=pipeline_name,
            depth=data.get("depth", 0),
            input_mode=data.get("input_mode", "simple"),
            block_input_in_editor=data.get("block_input_in_editor", False),
            layer_mask=layer_mask,
        )


def _get_pipeline_uuid_by_name(name: str) -> str | None:
    """Helper for backwards compatibility: get pipeline UUID by name."""
    try:
        from termin.assets.resources import ResourceManager
        rm = ResourceManager.instance()
        asset = rm.get_pipeline_asset(name)
        if asset is not None:
            return asset.uuid
    except Exception:
        pass
    return None
