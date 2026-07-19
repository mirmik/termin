#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {
void bind_tc_display(nb::module_& m);
void bind_tc_input_manager(nb::module_& m);
void bind_tc_render_surface(nb::module_& m);
void bind_offscreen_render_surface(nb::module_& m);
void bind_input_events(nb::module_& m);
}

NB_MODULE(_display_native, m) {
    m.doc() = "Display native module";
    nb::module_::import_("termin.scene._scene_native");
    nb::module_::import_("termin.viewport._viewport_native");
    nb::module_::import_("tcbase._tcbase_native");
    nb::module_::import_("tgfx._tgfx_native");

    termin::bind_tc_render_surface(m);
    termin::bind_tc_input_manager(m);
    termin::bind_offscreen_render_surface(m);
    termin::bind_tc_display(m);
    termin::bind_input_events(m);
}
