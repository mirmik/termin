#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace tmesh_bindings {
    void bind_mesh(nb::module_& m);
}

NB_MODULE(_mesh_native, m) {
    m.doc() = "termin-mesh native Python bindings";

    tmesh_bindings::bind_mesh(m);

    // Import log from tcbase
    nb::module_ tcbase = nb::module_::import_("termin.base._base_native");
    m.attr("log") = tcbase.attr("log");
}
