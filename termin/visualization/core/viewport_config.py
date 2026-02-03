"""ViewportConfig - configuration for scene viewport mounting."""

from __future__ import annotations

from typing import Tuple

# Re-export C++ class
from termin.entity._entity_native import ViewportConfig

__all__ = ["ViewportConfig", "serialize_viewport_config", "deserialize_viewport_config"]


def serialize_viewport_config(config: ViewportConfig) -> dict:
    """Serialize ViewportConfig to dict."""
    result = {
        "name": config.name,
        "display_name": config.display_name,
        "camera_uuid": config.camera_uuid,
        "region": [config.region_x, config.region_y, config.region_w, config.region_h],
        "depth": config.depth,
        "input_mode": config.input_mode,
        "block_input_in_editor": config.block_input_in_editor,
    }
    if config.pipeline_uuid:
        result["pipeline_uuid"] = config.pipeline_uuid
    if config.pipeline_name:
        result["pipeline_name"] = config.pipeline_name
    # Only serialize layer_mask if not all layers
    if config.layer_mask != 0xFFFFFFFFFFFFFFFF:
        result["layer_mask"] = hex(config.layer_mask)
    # Only serialize enabled if False (to keep files clean)
    if not config.enabled:
        result["enabled"] = config.enabled
    return result


def deserialize_viewport_config(data: dict) -> ViewportConfig:
    """Deserialize ViewportConfig from dict."""
    region = data.get("region", [0.0, 0.0, 1.0, 1.0])

    pipeline_uuid = data.get("pipeline_uuid", "")
    pipeline_name = data.get("pipeline_name", "")

    # Backwards compatibility: convert old pipeline_name (asset name) to uuid
    # But preserve special names like "(Editor)"
    if not pipeline_uuid and pipeline_name and not pipeline_name.startswith("("):
        pipeline_uuid = _get_pipeline_uuid_by_name(pipeline_name) or ""
        pipeline_name = ""  # Clear old-style name after conversion

    # Parse layer_mask (may be hex string or int)
    layer_mask_raw = data.get("layer_mask", 0xFFFFFFFFFFFFFFFF)
    if isinstance(layer_mask_raw, str):
        layer_mask = int(layer_mask_raw, 16) if layer_mask_raw.startswith("0x") else int(layer_mask_raw)
    else:
        layer_mask = int(layer_mask_raw)

    return ViewportConfig(
        name=data.get("name", ""),
        display_name=data.get("display_name", "Main"),
        camera_uuid=data.get("camera_uuid", ""),
        region_x=float(region[0]),
        region_y=float(region[1]),
        region_w=float(region[2]),
        region_h=float(region[3]),
        pipeline_uuid=pipeline_uuid,
        pipeline_name=pipeline_name,
        depth=data.get("depth", 0),
        input_mode=data.get("input_mode", "simple"),
        block_input_in_editor=data.get("block_input_in_editor", False),
        layer_mask=layer_mask,
        enabled=data.get("enabled", True),
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
