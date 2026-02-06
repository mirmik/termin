#include <nanobind/nanobind.h>
#include <nanobind/stl/tuple.h>

extern "C" {
#include "tc_picking.h"
}

#include "render_bindings.hpp"
#ifdef TERMIN_HAS_SDL2
#include "sdl_bindings.hpp"
#endif
#include "bindings/render/tc_render_surface_bindings.hpp"
#include "bindings/render/tc_input_manager_bindings.hpp"
#include "bindings/render/tc_display_bindings.hpp"
#include "bindings/input/simple_display_input_manager_bindings.hpp"
// scene_bindings.hpp - TcScene bindings moved to _entity_native
#include "scene/scene_manager_bindings.hpp"
#include "bindings/engine/engine_core_bindings.hpp"
#include "profiler_bindings.hpp"
#include "skeleton_bindings.hpp"
#include "inspect_bindings.hpp"
#include "log_bindings.hpp"
#include "kind_bindings.hpp"
#include "tc_component_python_bindings.hpp"
#include "assets/assets_bindings.hpp"

namespace nb = nanobind;

namespace termin {
void bind_gizmo(nb::module_& m);
void bind_editor_interaction(nb::module_& m);
void bind_frame_graph_debugger(nb::module_& m);
void cleanup_pass_classes();  // Cleanup function from tc_pass_bindings.cpp (in _native)
}

// Note: Other cleanup functions are in separate modules:
// - cleanup_skeleton_callbacks is in _skeleton_native module
// - cleanup_mesh_callbacks is in _mesh_native module
// - cleanup_component_classes is in entity_lib

// Cleanup function for _native module only
static void cleanup_all_python_objects() {
    termin::cleanup_pass_classes();
}

NB_MODULE(_native, m) {
    nb::set_leak_warnings(false);
    m.doc() = "Native C++ module for termin";

    // Import _geom_native for Vec4 type (used by Material::color)
    nb::module_ geom_native = nb::module_::import_("termin.geombase._geom_native");
    m.attr("geom") = geom_native;

    // Import _mesh_native and re-export as submodule
    // This allows types to be shared across modules
    nb::module_ mesh_native = nb::module_::import_("termin.mesh._mesh_native");
    m.attr("mesh") = mesh_native;

    // Import _graphics_native and re-export as submodule
    // Types like GraphicsBackend, ShaderHandle, etc. are defined there
    nb::module_ graphics_native = nb::module_::import_("termin.graphics._graphics_native");
    m.attr("graphics") = graphics_native;

    // Import _viewport_native for TcViewport type (used by CameraComponent)
    nb::module_ viewport_native = nb::module_::import_("termin.viewport._viewport_native");
    m.attr("viewport") = viewport_native;

    // Import _entity_native and re-export as submodule
    // Types like Component, Entity, EntityHandle are defined there
    // Must be imported before render (MeshRenderer inherits Component)
    nb::module_ entity_native = nb::module_::import_("termin.entity._entity_native");
    m.attr("entity") = entity_native;

    // Note: _skeleton_native and _animation_native are imported from Python
    // before _native is loaded (in termin/__init__.py) to avoid circular imports
    // and ensure kind handlers are registered early.

    // Create submodules
    auto render_module = m.def_submodule("render", "Render module");
    auto platform_module = m.def_submodule("platform", "Platform module");
    auto scene_module = m.def_submodule("scene", "Scene module");
    auto profiler_module = m.def_submodule("profiler", "Profiler module");
    auto skeleton_module = m.def_submodule("skeleton", "Skeleton module");
    auto inspect_module = m.def_submodule("inspect", "Inspect module");
    auto log_module = m.def_submodule("log", "Logging module");
    auto kind_module = m.def_submodule("kind", "Kind serialization module");
    auto component_module = m.def_submodule("component", "Component module");
    auto assets_module = m.def_submodule("assets", "Assets module");
    auto editor_module = m.def_submodule("editor", "Editor module");

    termin::bind_render(render_module);
    termin::bind_gizmo(editor_module);
    termin::bind_editor_interaction(editor_module);
    termin::bind_frame_graph_debugger(editor_module);
    termin::bind_tc_render_surface(render_module);
    termin::bind_tc_input_manager(render_module);
    termin::bind_tc_display(render_module);
    termin::bind_simple_display_input_manager(render_module);
#ifdef TERMIN_HAS_SDL2
    termin::bind_sdl(platform_module);
#endif
    // TcScene and TcSceneLighting are now in _entity_native module
    termin::bind_scene_manager(scene_module);
    termin::bind_engine_core(m);  // EngineCore in root module
    // TcViewport is now in separate _viewport_native module
    termin::bind_profiler(profiler_module);
    termin::bind_skeleton(skeleton_module);
    termin::bind_inspect(inspect_module);
    termin::bind_log(log_module);
    termin::bind_kind(kind_module);
    termin::bind_tc_component_python(component_module);
    termin::bind_assets(assets_module);

    // Picking utilities (id <-> rgb conversion with cache)
    m.def("tc_picking_id_to_rgb", [](int id) {
        int r, g, b;
        tc_picking_id_to_rgb(id, &r, &g, &b);
        return std::make_tuple(r, g, b);
    }, "Convert entity pick ID to RGB (0-255 range), caches for reverse lookup");

    m.def("tc_picking_rgb_to_id", &tc_picking_rgb_to_id,
        "Convert RGB (0-255) back to entity pick ID, returns 0 if not cached");

    m.def("tc_picking_cache_clear", &tc_picking_cache_clear,
        "Clear the picking cache");

    // Register cleanup function to be called before Python shutdown
    m.def("_cleanup_python_objects", &cleanup_all_python_objects,
        "Internal: cleanup all Python objects stored in C++ before shutdown");

    // Register cleanup with Python's atexit module
    nb::module_ atexit = nb::module_::import_("atexit");
    atexit.attr("register")(nb::cpp_function(&cleanup_all_python_objects));
}
