/**
 * Main render module bindings.
 *
 * This file aggregates all render-related bindings from separate files.
 * Each bind_* function registers bindings for a specific subsystem.
 */

#include "common.hpp"
#include "termin/render_bindings.hpp"

namespace termin {

void bind_render(py::module_& m) {
    // Order matters - dependencies must be bound first

    // Basic types, enums, RenderState
    bind_render_types(m);

    // Graphics backend, handles, OpenGL
    bind_graphics_backend(m);

    // ShaderProgram
    bind_shader(m);

    // Shader parser (MaterialProperty, ShaderPhase, etc.)
    bind_shader_parser(m);

    // Camera
    bind_camera(m);

    // Shadow camera
    bind_shadow(m);

    // ResourceSpec
    bind_resource_spec(m);

    // ImmediateRenderer
    bind_immediate(m);

    // FramePass, FrameGraph, RenderContext
    bind_frame_pass(m);

    // MaterialPhase, Material
    bind_material(m);

    // GeometryDrawCall, PhaseDrawCall
    bind_drawable(m);

    // MeshGPU, TextureGPU
    bind_gpu(m);

    // MeshRenderer, SkinnedMeshRenderer
    bind_renderers(m);
}

} // namespace termin
