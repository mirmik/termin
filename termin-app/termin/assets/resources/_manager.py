"""ResourceManager combining all mixins."""

from __future__ import annotations

from ._base import ResourceManagerBase
from ._assets import AssetsMixin
from ._components import ComponentsMixin
from ._pipelines import PipelinesMixin
from ._scene_pipelines import ScenePipelinesMixin
from ._accessors import AccessorsMixin
from ._serialization import SerializationMixin


class ResourceManager(
    ResourceManagerBase,
    AssetsMixin,
    ComponentsMixin,
    PipelinesMixin,
    ScenePipelinesMixin,
    AccessorsMixin,
    SerializationMixin,
):
    """
    Central manager for all resources: materials, meshes, textures, shaders, etc.

    This is a singleton class. Use ResourceManager.instance() to get the instance.
    """
    pass
