#include "common.hpp"

namespace termin {

void bind_drawable(nb::module_& m) {
    nb::module_ render_native = nb::module_::import_("termin.render._render_native");
    m.attr("GeometryDrawCall") = render_native.attr("GeometryDrawCall");
    m.attr("PhaseDrawCall") = render_native.attr("PhaseDrawCall");
}

} // namespace termin
