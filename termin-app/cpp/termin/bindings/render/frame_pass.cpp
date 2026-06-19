#include "common.hpp"

namespace termin {

void bind_frame_pass(nb::module_& m) {
    nb::module_ render_passes = nb::module_::import_("termin.render_passes._render_passes_native");
    m.attr("ColliderGizmoPass") = render_passes.attr("ColliderGizmoPass");
}

} // namespace termin
