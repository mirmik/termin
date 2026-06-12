#include "common.hpp"

namespace termin {

void bind_renderers(nb::module_& m) {
    nb::object render_components = nb::module_::import_("termin.render_components._components_render_native");
    m.attr("SkinnedMeshRenderer") = render_components.attr("SkinnedMeshRenderer");
}

} // namespace termin
