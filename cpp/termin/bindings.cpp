#include <pybind11/pybind11.h>

#include "mesh_bindings.hpp"
#include "render_bindings.hpp"
#include "sdl_bindings.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_native, m) {
    m.doc() = "Native C++ module for termin";

    // Create submodules
    auto mesh_module = m.def_submodule("mesh", "Mesh module");
    auto render_module = m.def_submodule("render", "Render module");
    auto platform_module = m.def_submodule("platform", "Platform module");

    termin::bind_mesh(mesh_module);
    termin::bind_render(render_module);
    termin::bind_sdl(platform_module);
}
