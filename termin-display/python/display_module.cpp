#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {
void bind_tc_display(nb::module_& m);
void bind_tc_input_manager(nb::module_& m);
void bind_tc_render_surface(nb::module_& m);
void bind_display_input_router(nb::module_& m);
}

NB_MODULE(_display_native, m) {
    m.doc() = "Display native module";

    termin::bind_tc_render_surface(m);
    termin::bind_tc_input_manager(m);
    termin::bind_tc_display(m);
    termin::bind_display_input_router(m);
}
