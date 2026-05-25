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
    MaterialPass,
    MeshRenderer,
    OrthographicCameraComponent,
    PerspectiveCameraComponent,
    NormalPass,
    XrOriginComponent,
    XrThumbstickLocomotionComponent,
)

__all__ = [
    "CameraComponent",
    "ColorToDepthPass",
    "DepthOnlyPass",
    "DepthPass",
    "DepthToColorPass",
    "LightComponent",
    "LineRenderer",
    "MaterialPass",
    "MeshRenderer",
    "OrthographicCameraComponent",
    "PerspectiveCameraComponent",
    "NormalPass",
    "XrOriginComponent",
    "XrThumbstickLocomotionComponent",
]
