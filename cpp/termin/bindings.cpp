#include <pybind11/pybind11.h>

#include "render_bindings.hpp"
#include "sdl_bindings.hpp"
#include "entity_bindings.hpp"
#include "scene_bindings.hpp"
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

    // Create submodules
    auto render_module = m.def_submodule("render", "Render module");
    auto platform_module = m.def_submodule("platform", "Platform module");
    auto entity_module = m.def_submodule("entity", "Entity module");
    auto scene_module = m.def_submodule("scene", "Scene module");
    auto skeleton_module = m.def_submodule("skeleton", "Skeleton module");
    auto inspect_module = m.def_submodule("inspect", "Inspect module");
    auto assets_module = m.def_submodule("assets", "Assets module");

    termin::bind_entity(entity_module);  // Must be before render (MeshRenderer inherits Component)
    termin::bind_render(render_module);
    termin::bind_sdl(platform_module);
    termin::bind_scene(scene_module);
    termin::bind_skeleton(skeleton_module);
    termin::bind_inspect(inspect_module);
    termin::bind_assets(assets_module);
}
