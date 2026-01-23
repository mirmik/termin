#include <nanobind/nanobind.h>
#include <nanobind/stl/tuple.h>

extern "C" {
#include "tc_picking.h"
}

#include "render_bindings.hpp"
#include "sdl_bindings.hpp"
#include "scene_bindings.hpp"
#include "tc_viewport_bindings.hpp"
#include "profiler_bindings.hpp"
#include "skeleton_bindings.hpp"
#include "inspect_bindings.hpp"
#include "log_bindings.hpp"
#include "kind_bindings.hpp"
#include "tc_component_python_bindings.hpp"
#include "assets/assets_bindings.hpp"

namespace nb = nanobind;

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

    termin::bind_render(render_module);
    termin::bind_sdl(platform_module);
    termin::bind_tc_scene(scene_module);
    termin::bind_tc_viewport(scene_module);
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
}
