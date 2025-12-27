#include <pybind11/pybind11.h>

#include "render_bindings.hpp"
#include "sdl_bindings.hpp"
#include "scene_bindings.hpp"
#include "profiler_bindings.hpp"
#include "skeleton_bindings.hpp"
#include "inspect_bindings.hpp"
#include "assets/assets_bindings.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_native, m) {
    m.doc() = "Native C++ module for termin";

    // Import _mesh_native and re-export as submodule
    // This allows types to be shared across modules
    py::module_ mesh_native = py::module_::import("termin.mesh._mesh_native");
    m.attr("mesh") = mesh_native;

    // Import _graphics_native and re-export as submodule
    // Types like GraphicsBackend, ShaderHandle, etc. are defined there
    py::module_ graphics_native = py::module_::import("termin.graphics._graphics_native");
    m.attr("graphics") = graphics_native;

    // Import _entity_native and re-export as submodule
    // Types like Component, Entity, EntityHandle are defined there
    // Must be imported before render (MeshRenderer inherits Component)
    py::module_ entity_native = py::module_::import("termin.entity._entity_native");
    m.attr("entity") = entity_native;

    // Create submodules
    auto render_module = m.def_submodule("render", "Render module");
    auto platform_module = m.def_submodule("platform", "Platform module");
    auto scene_module = m.def_submodule("scene", "Scene module");
    auto profiler_module = m.def_submodule("profiler", "Profiler module");
    auto skeleton_module = m.def_submodule("skeleton", "Skeleton module");
    auto inspect_module = m.def_submodule("inspect", "Inspect module");
    auto assets_module = m.def_submodule("assets", "Assets module");

    termin::bind_render(render_module);
    termin::bind_sdl(platform_module);
    termin::bind_tc_scene(scene_module);
    termin::bind_profiler(profiler_module);
    termin::bind_skeleton(skeleton_module);
    termin::bind_inspect(inspect_module);
    termin::bind_assets(assets_module);
}
