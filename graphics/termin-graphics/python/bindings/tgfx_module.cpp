// tgfx_module.cpp - Main module for _graphics_native Python bindings
#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace tgfx_bindings {
    void bind_types(nb::module_& m);
    void bind_render_state(nb::module_& m);
    void bind_shader(nb::module_& m);
    void bind_texture(nb::module_& m);
    void bind_tgfx2(nb::module_& m);
    void bind_immediate(nb::module_& m);
} // namespace tgfx_bindings

NB_MODULE(_graphics_native, m) {
    m.doc() = "termin-graphics native Python bindings";

    nb::module_::import_("termin.base._base_native");
    nb::module_::import_("termin.base._geom_native");

    tgfx_bindings::bind_types(m);
    tgfx_bindings::bind_render_state(m);
    tgfx_bindings::bind_shader(m);
    tgfx_bindings::bind_texture(m);
    tgfx_bindings::bind_tgfx2(m);
    tgfx_bindings::bind_immediate(m);

    // Import log from the canonical base module.
    nb::module_ base = nb::module_::import_("termin.base._base_native");
    m.attr("log") = base.attr("log");
}
