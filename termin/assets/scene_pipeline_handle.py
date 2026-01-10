"""ScenePipelineHandle - Smart reference to RenderPipeline resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline
    from termin.assets.scene_pipeline_asset import ScenePipelineAsset


class ScenePipelineHandle(ResourceHandle["RenderPipeline", "ScenePipelineAsset"]):
    """
    Smart reference to a RenderPipeline.

    Usage:
        handle = ScenePipelineHandle.from_name("my_pipeline")
        handle = ScenePipelineHandle.from_asset(asset)
        handle = ScenePipelineHandle.from_uuid("uuid-string")
        handle = ScenePipelineHandle.from_direct(pipeline)

        pipeline = handle.get()       # Get RenderPipeline
        asset = handle.get_asset()    # Get ScenePipelineAsset
    """

    _asset_getter = "get_scene_pipeline_asset"

    @classmethod
    def from_uuid(cls, uuid: str) -> "ScenePipelineHandle":
        """Create handle by UUID (lookup in ResourceManager)."""
        from termin.assets.resources import ResourceManager

        asset = ResourceManager.instance().get_scene_pipeline_asset_by_uuid(uuid)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    @classmethod
    def from_direct(cls, pipeline: "RenderPipeline") -> "ScenePipelineHandle":
        """Create handle with direct RenderPipeline (no Asset)."""
        handle = cls()
        handle._init_direct(pipeline)
        return handle

    @property
    def pipeline(self) -> "RenderPipeline | None":
        """Convenience property for the pipeline."""
        return self.get()

    def _serialize_direct(self) -> dict:
        """Serialize direct pipeline."""
        if self._direct is None:
            return {}
        return {
            "type": "direct",
            "data": self._direct.serialize(),
        }

    # --- Serialization ---

    def serialize(self) -> dict:
        """Serialize for scene saving."""
        if self._asset is not None:
            return {
                "type": "uuid",
                "uuid": self._asset.uuid,
            }
        elif self._direct is not None:
            return self._serialize_direct()
        return {"type": "none"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "ScenePipelineHandle":
        """Deserialize from saved data."""
        handle_type = data.get("type", "none")

        if handle_type == "uuid":
            uuid = data.get("uuid")
            if uuid:
                return cls.from_uuid(uuid)
        elif handle_type == "name":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "direct":
            return cls._deserialize_direct(data)

        return cls()

    @classmethod
    def _deserialize_direct(cls, data: dict) -> "ScenePipelineHandle":
        """Deserialize direct pipeline."""
        from termin.visualization.render.framegraph.pipeline import RenderPipeline
        from termin.visualization.core.resources import ResourceManager

        pipeline_data = data.get("data", {})
        rm = ResourceManager.instance()
        pipeline = RenderPipeline.deserialize(pipeline_data, rm)

        return cls.from_direct(pipeline)


__all__ = ["ScenePipelineHandle"]
