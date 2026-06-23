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
    OrbitCameraController,
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


def _mesh_renderer_get_phases_for_mark(self, phase_mark):
    return sorted(
        [phase for phase in self.get_material().phases if phase.phase_mark == phase_mark],
        key=lambda phase: phase.priority,
    )


# tc_material_phase is owned by termin.materials. Creating phase wrappers from
# this extension module corrupts the Windows heap on teardown, so route through
# TcMaterial's binding instead.
MeshRenderer.get_phases_for_mark = _mesh_renderer_get_phases_for_mark

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
    "OrbitCameraController",
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
