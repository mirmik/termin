"""RenderTargetConfig - configuration for scene render targets."""

from __future__ import annotations

from termin.entity._entity_native import RenderTargetConfig

__all__ = ["RenderTargetConfig", "serialize_render_target_config", "deserialize_render_target_config"]


def serialize_render_target_config(config: RenderTargetConfig) -> dict:
    """Serialize RenderTargetConfig to dict."""
    result = {
        "name": config.name,
        "camera_uuid": config.camera_uuid,
    }
    if config.dynamic_resolution:
        result["dynamic_resolution"] = True
    else:
        result["width"] = config.width
        result["height"] = config.height
    if config.color_format:
        result["color_format"] = config.color_format
    if config.depth_format:
        result["depth_format"] = config.depth_format
    if config.pipeline_uuid:
        result["pipeline_uuid"] = config.pipeline_uuid
    if config.pipeline_name:
        result["pipeline_name"] = config.pipeline_name
    if config.layer_mask != 0xFFFFFFFFFFFFFFFF:
        result["layer_mask"] = hex(config.layer_mask)
    if not config.enabled:
        result["enabled"] = config.enabled
    if config.pipeline_params:
        result["pipeline_params"] = dict(config.pipeline_params)
    return result


def deserialize_render_target_config(data: dict) -> RenderTargetConfig:
    """Deserialize RenderTargetConfig from dict."""
    config = RenderTargetConfig()
    config.name = data.get("name", "")
    config.camera_uuid = data.get("camera_uuid", "")
    config.width = data.get("width", 512)
    config.height = data.get("height", 512)
    config.dynamic_resolution = data.get("dynamic_resolution", False)
    config.color_format = data.get("color_format", "rgba16f")
    config.depth_format = data.get("depth_format", "depth32f")
    config.pipeline_uuid = data.get("pipeline_uuid", "")
    config.pipeline_name = data.get("pipeline_name", "")

    layer_mask_raw = data.get("layer_mask", 0xFFFFFFFFFFFFFFFF)
    if isinstance(layer_mask_raw, str):
        config.layer_mask = int(layer_mask_raw, 16) if layer_mask_raw.startswith("0x") else int(layer_mask_raw)
    else:
        config.layer_mask = int(layer_mask_raw)

    config.enabled = data.get("enabled", True)
    pipeline_params = data.get("pipeline_params", {})
    if isinstance(pipeline_params, dict):
        config.pipeline_params = {
            str(slot): str(value)
            for slot, value in pipeline_params.items()
            if slot and value
        }
    return config
