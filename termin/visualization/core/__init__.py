"""Core scene graph primitives and resource helpers."""

from termin.visualization.core.camera import (
    CameraComponent,
    OrbitCameraController,
    OrthographicCameraComponent,
    PerspectiveCameraComponent,
)
from termin.visualization.core.entity import Component, Entity, InputComponent
from termin.visualization.render.render_context import RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import Mesh2Drawable, MeshDrawable
from termin.visualization.core.picking import id_to_rgb, rgb_to_id
from termin.visualization.core.resources import ResourceManager
from termin.visualization.core.scene import Scene
from termin.visualization.core.serialization import COMPONENT_REGISTRY, serializable
from termin.visualization.core.lighting.light import Light, LightSample, LightShadowParams, LightType
from termin.visualization.core.lighting.attenuation import AttenuationCoefficients

# Display, Viewport, World, Visualization импортируются лениво через __getattr__
# чтобы избежать циклического импорта с platform.window

__all__ = [
    "CameraComponent",
    "OrbitCameraController",
    "OrthographicCameraComponent",
    "PerspectiveCameraComponent",
    "Component",
    "Display",
    "Entity",
    "InputComponent",
    "RenderContext",
    "Material",
    "Mesh2Drawable",
    "MeshDrawable",
    "ResourceManager",
    "Scene",
    "Viewport",
    "Visualization",
    "VisualizationWorld",
    "World",
    "id_to_rgb",
    "rgb_to_id",
    "serializable",
    "COMPONENT_REGISTRY",
    "Light",
    "LightSample",
    "LightShadowParams",
    "LightType",
    "AttenuationCoefficients",
]


def __getattr__(name: str):
    """Ленивый импорт для избежания циклических зависимостей."""
    if name == "Display":
        from termin.visualization.core.display import Display
        return Display
    if name == "Viewport":
        from termin.visualization.core.viewport import Viewport
        return Viewport
    if name in ("World", "Visualization", "VisualizationWorld"):
        from termin.visualization.core import world as world_module
        return getattr(world_module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
