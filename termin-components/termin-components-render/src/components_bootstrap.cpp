#include <termin/render/components_bootstrap.hpp>

#include <components/components_mesh_bootstrap.hpp>
#include <termin/camera/camera_component.hpp>
#include <termin/camera/orbit_camera_controller.hpp>
#include <termin/lighting/light_component.hpp>
#include <termin/render/line_renderer.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/skinned_mesh_renderer.hpp>
#include <termin/render/world_text_component.hpp>
#include <termin/render/skeleton_components_bootstrap.hpp>
#include <termin/xr/xr_origin_component.hpp>
#include <termin/xr/xr_thumbstick_locomotion_component.hpp>

namespace termin {

void register_builtin_render_component_types() {
    register_builtin_mesh_component_types();
    register_builtin_skeleton_component_types();
    CameraComponent::register_type();
    OrbitCameraController::register_type();
    LightComponent::register_type();
    MeshRenderer::register_type();
    SkinnedMeshRenderer::register_type();
    LineRenderer::register_type();
    WorldTextComponent::register_type();
    XrOriginComponent::register_type();
    XrThumbstickLocomotionComponent::register_type();
}

} // namespace termin
