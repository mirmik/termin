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

    nb::module_ framework = nb::module_::import_("termin.render_framework._render_framework_native");
    nb::module_ display_native = nb::module_::import_("termin.display._display_native");

    // NOTE: Shared types (Color4, Size2i, TcShader, TcTexture, TcMesh, etc.)
    // are defined in tgfx._tgfx_native and imported in bindings.cpp

    // Shader parser (MaterialProperty, ShaderPhase, etc.)
    bind_shader_parser(m);

    // Camera
    bind_camera(m);

    // Shadow camera
    bind_shadow(m);

    m.attr("TextureFilter") = framework.attr("TextureFilter");
    m.attr("ResourceSpec") = framework.attr("ResourceSpec");
    m.attr("InternalSymbolTiming") = framework.attr("InternalSymbolTiming");
    m.attr("Rect4i") = framework.attr("Rect4i");
    m.attr("FrameGraphResource") = framework.attr("FrameGraphResource");
    m.attr("ExecuteContext") = framework.attr("ExecuteContext");
    m.attr("FramePass") = framework.attr("FramePass");
    m.attr("RenderContext") = framework.attr("RenderContext");
    m.attr("HDRStats") = framework.attr("HDRStats");
    m.attr("TextureInfo") = framework.attr("TextureInfo");
    m.attr("FrameGraphCapture") = framework.attr("FrameGraphCapture");
    m.attr("FrameGraphPresenter") = framework.attr("FrameGraphPresenter");
    m.attr("FrameGraphDebuggerCore") = framework.attr("FrameGraphDebuggerCore");

    m.attr("Display") = display_native.attr("Display");
    m.attr("FBOSurface") = display_native.attr("FBOSurface");
    m.attr("DisplayInputRouter") = display_native.attr("DisplayInputRouter");
    m.attr("_render_surface_new_from_python") = display_native.attr("_render_surface_new_from_python");
    m.attr("_render_surface_free_external") = display_native.attr("_render_surface_free_external");
    m.attr("_render_surface_get_ptr") = display_native.attr("_render_surface_get_ptr");
    m.attr("_render_surface_set_input_manager") = display_native.attr("_render_surface_set_input_manager");
    m.attr("_render_surface_set_on_resize") = display_native.attr("_render_surface_set_on_resize");
    m.attr("_render_surface_notify_resize") = display_native.attr("_render_surface_notify_resize");
    m.attr("_render_surface_get_input_manager") = display_native.attr("_render_surface_get_input_manager");
    m.attr("_input_manager_create_vtable") = display_native.attr("_input_manager_create_vtable");
    m.attr("_input_manager_new") = display_native.attr("_input_manager_new");
    m.attr("_input_manager_free") = display_native.attr("_input_manager_free");
    m.attr("_input_manager_on_mouse_button") = display_native.attr("_input_manager_on_mouse_button");
    m.attr("_input_manager_on_mouse_move") = display_native.attr("_input_manager_on_mouse_move");
    m.attr("_input_manager_on_scroll") = display_native.attr("_input_manager_on_scroll");
    m.attr("_input_manager_on_key") = display_native.attr("_input_manager_on_key");
    m.attr("_input_manager_on_char") = display_native.attr("_input_manager_on_char");
    m.attr("_display_input_router_new") = display_native.attr("_display_input_router_new");
    m.attr("_display_input_router_free") = display_native.attr("_display_input_router_free");
    m.attr("_display_input_router_base") = display_native.attr("_display_input_router_base");
    m.attr("_viewport_input_manager_new") = display_native.attr("_viewport_input_manager_new");
    m.attr("_viewport_input_manager_free") = display_native.attr("_viewport_input_manager_free");
    m.attr("_viewport_get_input_manager") = display_native.attr("_viewport_get_input_manager");
    m.attr("_display_get_surface_ptr") = display_native.attr("_display_get_surface_ptr");
    m.attr("TC_INPUT_RELEASE") = display_native.attr("TC_INPUT_RELEASE");
    m.attr("TC_INPUT_PRESS") = display_native.attr("TC_INPUT_PRESS");
    m.attr("TC_INPUT_REPEAT") = display_native.attr("TC_INPUT_REPEAT");
    m.attr("TC_MOUSE_BUTTON_LEFT") = display_native.attr("TC_MOUSE_BUTTON_LEFT");
    m.attr("TC_MOUSE_BUTTON_RIGHT") = display_native.attr("TC_MOUSE_BUTTON_RIGHT");
    m.attr("TC_MOUSE_BUTTON_MIDDLE") = display_native.attr("TC_MOUSE_BUTTON_MIDDLE");
    m.attr("TC_MOD_SHIFT") = display_native.attr("TC_MOD_SHIFT");
    m.attr("TC_MOD_CONTROL") = display_native.attr("TC_MOD_CONTROL");
    m.attr("TC_MOD_ALT") = display_native.attr("TC_MOD_ALT");
    m.attr("TC_MOD_SUPER") = display_native.attr("TC_MOD_SUPER");

    // ImmediateRenderer
    bind_immediate(m);

    // FramePass, FrameGraph, RenderContext
    bind_frame_pass(m);

    // RenderPipeline — re-export from _render_framework_native
    {
        nb::module_ rf = nb::module_::import_("termin.render_framework._render_framework_native");
        m.attr("RenderPipeline") = rf.attr("RenderPipeline");
        m.attr("compile_graph_from_json") = rf.attr("compile_graph_from_json");
    }


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

    nb::module_ engine_native = nb::module_::import_("termin.engine._engine_native");
    nb::module_ engine_render = nb::borrow<nb::module_>(engine_native.attr("render"));
    m.attr("RenderingManager") = engine_render.attr("RenderingManager");
    m.attr("ViewportRenderState") = engine_render.attr("ViewportRenderState");
}

} // namespace termin
