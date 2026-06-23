/**
 * Main render module bindings.
 *
 * This file aggregates all render-related bindings from separate files.
 * Each bind_* function registers bindings for a specific subsystem.
 */

#include "common.hpp"
#include "termin/render_bindings.hpp"

extern "C" {
#include "core/tc_scene_render_state.h"
#include "core/tc_scene_render_mount.h"
}

namespace termin {

void bind_render(nb::module_& m) {
    // Register scene extensions that render passes depend on. Idempotent;
    // a no-op if another init path (EngineCore) already registered them.
    // Needed so standalone Python scripts that don't construct an
    // EngineCore still get render_state (skybox, lighting, ...) available.
    tc_scene_render_mount_extension_init();
    tc_scene_render_state_extension_init();

    // Order matters - dependencies must be bound first

    // NOTE: Shared types (Color4, Size2i, TcShader, TcTexture, TcMesh, etc.)
    // are defined in tgfx._tgfx_native and imported in bindings.cpp

    // Camera
    bind_camera(m);

    // Shadow camera
    bind_shadow(m);

    // Register kind handlers for TcMaterial serialization
    register_material_kind_handlers();

}

} // namespace termin
