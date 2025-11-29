"""Core scene graph primitives and resource helpers."""

from termin.visualization.core.camera import (
    CameraComponent,
    OrbitCameraController,
    OrthographicCameraComponent,
    PerspectiveCameraComponent,
)
from termin.visualization.core.entity import Component, Entity, InputComponent, RenderContext
from termin.visualization.core.line import LineEntity
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import Mesh2Drawable, MeshDrawable
from termin.visualization.core.picking import id_to_rgb, rgb_to_id
from termin.visualization.core.polyline import Polyline, PolylineDrawable
from termin.visualization.core.resources import ResourceManager
from termin.visualization.core.scene import Scene
from termin.visualization.core.serialization import COMPONENT_REGISTRY, serializable
from termin.visualization.core.lighting.light import Light, LightSample, LightShadowParams, LightType
from termin.visualization.core.lighting.attenuation import AttenuationCoefficients

__all__ = [
    "CameraComponent",
    "OrbitCameraController",
    "OrthographicCameraComponent",
    "PerspectiveCameraComponent",
    "Component",
    "Entity",
    "InputComponent",
    "RenderContext",
    "LineEntity",
    "Material",
    "Mesh2Drawable",
    "MeshDrawable",
    "Polyline",
    "PolylineDrawable",
    "ResourceManager",
    "Scene",
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
