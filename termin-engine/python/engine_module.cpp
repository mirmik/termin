#include <nanobind/nanobind.h>

#include "termin/bindings/engine/engine_core_bindings.hpp"
#include "termin/bindings/scene/scene_manager_bindings.hpp"

namespace nb = nanobind;

namespace termin {
void bind_rendering_manager(nb::module_& m);
}

NB_MODULE(_engine_native, m) {
    m.doc() = "Engine/runtime native module for termin";

    nb::module_::import_("termin.scene._scene_native");
    nb::module_::import_("termin.display._display_native");
    nb::module_::import_("termin.viewport._viewport_native");
    nb::module_::import_("termin.render_framework._render_framework_native");
    nb::module_::import_("termin.entity._entity_native");

    auto scene_module = m.def_submodule("scene", "Scene management");
    auto render_module = m.def_submodule("render", "Rendering management");

    termin::bind_scene_manager(scene_module);
    termin::bind_rendering_manager(render_module);
    termin::bind_engine_core(m);
}
