"""Rendering component classes (CameraComponent, MeshRenderer, light components)."""

from termin_nanobind.runtime import preload_sdk_libs

# _components_render_native.so has no RPATH — must preload libnanobind + its
# direct C++ deps so the loader sees them in the global symbol namespace
# via SONAME matching before dlopen'ing the binding.
preload_sdk_libs("nanobind", "termin_components_render")

from termin.render_components._components_render_native import (
    CameraComponent,
    ColorToDepthPass,
    DepthOnlyPass,
    DepthPass,
    DepthToColorPass,
    LightComponent,
    LineRenderer,
    LineRenderMode,
    MaterialPass,
    MeshRenderer,
    OrthographicCameraComponent,
    PerspectiveCameraComponent,
    NormalPass,
    WorldTextAnchor,
    WorldTextComponent,
    WorldTextOrientation,
    XrOriginComponent,
    XrThumbstickLocomotionComponent,
)
from termin.render_components.camera import CameraController
from termin.render_components.material_pass import get_texture_inputs_for_material

__all__ = [
    "CameraComponent",
    "CameraController",
    "ColorToDepthPass",
    "DepthOnlyPass",
    "DepthPass",
    "DepthToColorPass",
    "LightComponent",
    "LineRenderer",
    "LineRenderMode",
    "MaterialPass",
    "MeshRenderer",
    "OrthographicCameraComponent",
    "PerspectiveCameraComponent",
    "NormalPass",
    "WorldTextAnchor",
    "WorldTextComponent",
    "WorldTextOrientation",
    "XrOriginComponent",
    "XrThumbstickLocomotionComponent",
    "get_texture_inputs_for_material",
]
