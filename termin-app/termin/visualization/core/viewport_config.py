"""ViewportConfig - configuration for scene viewport mounting."""

from __future__ import annotations

# Re-export C++ class
from termin.entity._entity_native import ViewportConfig

__all__ = ["ViewportConfig", "serialize_viewport_config", "deserialize_viewport_config"]


def serialize_viewport_config(config: ViewportConfig) -> dict:
    """Serialize ViewportConfig to dict."""
    result = {
        "name": config.name,
        "display_name": config.display_name,
        "region": [config.region_x, config.region_y, config.region_w, config.region_h],
        "depth": config.depth,
        "input_mode": config.input_mode,
        "block_input_in_editor": config.block_input_in_editor,
    }
    if config.render_target_name:
        result["render_target_name"] = config.render_target_name
    if not config.enabled:
        result["enabled"] = config.enabled
    return result


def deserialize_viewport_config(data: dict) -> ViewportConfig:
    """Deserialize ViewportConfig from dict."""
    region = data.get("region", [0.0, 0.0, 1.0, 1.0])

    config = ViewportConfig()
    config.name = data.get("name", "")
    config.display_name = data.get("display_name", "Main")
    config.render_target_name = data.get("render_target_name", "")
    config.region_x = float(region[0])
    config.region_y = float(region[1])
    config.region_w = float(region[2])
    config.region_h = float(region[3])
    config.depth = data.get("depth", 0)
    config.input_mode = data.get("input_mode", "simple")
    config.block_input_in_editor = data.get("block_input_in_editor", False)
    config.enabled = data.get("enabled", True)
    return config
