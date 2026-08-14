#include <termin/render/components_bootstrap.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/orbit_camera_controller.hpp>
#include <termin/lighting/light_component.hpp>
#include <termin/render/mesh_renderer.hpp>

namespace termin {

    void register_builtin_render_component_types() {
        CameraComponent::register_type();
        OrbitCameraController::register_type();
        LightComponent::register_type();
        MeshRenderer::register_type();
    }

    void register_builtin_render_component_pass_types() {}

} // namespace termin
