#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

namespace nb = nanobind;

void bind_entity_domain(nb::module_& m);

NB_MODULE(_native, m) {
    nb::set_leak_warnings(false);
    m.doc() = "Termin app-private native startup glue";

    bind_entity_domain(m);
}
