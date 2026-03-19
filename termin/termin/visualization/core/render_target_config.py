"""RenderTargetConfig - configuration for scene render targets."""

from __future__ import annotations

from termin.entity._entity_native import RenderTargetConfig

__all__ = ["RenderTargetConfig", "serialize_render_target_config", "deserialize_render_target_config"]


def serialize_render_target_config(config: RenderTargetConfig) -> dict:
    """Serialize RenderTargetConfig to dict."""
    result = {
        "name": config.name,
        "camera_uuid": config.camera_uuid,
        "width": config.width,
        "height": config.height,
    }
    if config.pipeline_uuid:
        result["pipeline_uuid"] = config.pipeline_uuid
    if config.pipeline_name:
        result["pipeline_name"] = config.pipeline_name
    if config.layer_mask != 0xFFFFFFFFFFFFFFFF:
        result["layer_mask"] = hex(config.layer_mask)
    if not config.enabled:
        result["enabled"] = config.enabled
    return result


def deserialize_render_target_config(data: dict) -> RenderTargetConfig:
    """Deserialize RenderTargetConfig from dict."""
    config = RenderTargetConfig()
    config.name = data.get("name", "")
    config.camera_uuid = data.get("camera_uuid", "")
    config.width = data.get("width", 512)
    config.height = data.get("height", 512)
    config.pipeline_uuid = data.get("pipeline_uuid", "")
    config.pipeline_name = data.get("pipeline_name", "")

    layer_mask_raw = data.get("layer_mask", 0xFFFFFFFFFFFFFFFF)
    if isinstance(layer_mask_raw, str):
        config.layer_mask = int(layer_mask_raw, 16) if layer_mask_raw.startswith("0x") else int(layer_mask_raw)
    else:
        config.layer_mask = int(layer_mask_raw)

    config.enabled = data.get("enabled", True)
    return config
