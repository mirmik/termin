#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {
void bind_gizmo(nb::module_& m);
void bind_editor_interaction(nb::module_& m);
void bind_frame_graph_debugger(nb::module_& m);
void bind_frame_profiler(nb::module_& m);
void bind_solid_primitive(nb::module_& m);
}

NB_MODULE(_editor_native, m) {
    nb::set_leak_warnings(false);
    m.doc() = "Editor-private native C++ module for Termin";

    termin::bind_solid_primitive(m);
    termin::bind_gizmo(m);
    termin::bind_editor_interaction(m);
    termin::bind_frame_graph_debugger(m);
    termin::bind_frame_profiler(m);
}
