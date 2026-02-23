/**
 * Main render module bindings.
 *
 * This file aggregates all render-related bindings from separate files.
 * Each bind_* function registers bindings for a specific subsystem.
 */

#include "common.hpp"
#include "termin/render_bindings.hpp"

namespace termin {

void bind_render(nb::module_& m) {
    // Order matters - dependencies must be bound first

    // NOTE: Shared types (Color4, Size2i, TcShader, TcTexture, TcMesh, etc.)
    // are defined in tgfx._tgfx_native and imported in bindings.cpp

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

    // WireframeRenderer
    bind_wireframe(m);

    // FramePass, FrameGraph, RenderContext
    bind_frame_pass(m);

    // tc_pass, tc_frame_graph (C API bindings)
    bind_tc_pass(m);

    // RenderPipeline (C++ class)
    bind_render_pipeline(m);

    // TcScenePipelineTemplate (graph source for scene pipelines)
    bind_scene_pipeline_template(m);

    // MaterialPhase, Material
    bind_material(m);

    // TcMaterial (C-based material wrapper)
    bind_tc_material(m);

    // Register kind handlers for TcMaterial serialization
    register_material_kind_handlers();

    // GeometryDrawCall, PhaseDrawCall
    bind_drawable(m);

    // MeshRenderer, SkinnedMeshRenderer
    bind_renderers(m);

    // SolidPrimitiveRenderer
    bind_solid_primitive(m);

    // RenderEngine
    bind_render_engine(m);

    // RenderingManager (scene pipeline methods)
    bind_rendering_manager(m);
}

} // namespace termin
