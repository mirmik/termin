#include <pybind11/pybind11.h>

#include "mesh_bindings.hpp"
#include "render_bindings.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_native, m) {
    m.doc() = "Native C++ module for termin";

    termin::bind_mesh(m);
    termin::bind_render(m);
}
