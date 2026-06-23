// App domain bindings for _native module.
//
// Core ECS/input/render component types are owned by their domain packages and
// should be imported from termin.scene, termin.input, and termin.render_components.
// This module keeps only app-level inspect registration and process cleanup.

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <utility>
#include <tcbase/tc_log.hpp>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include "termin/inspect/tc_kind.hpp"

namespace nb = nanobind;
using namespace termin;

void bind_entity_domain(nb::module_& m) {
    // Register CxxComponent base fields in InspectRegistry.
    tc::InspectFieldInfo display_name_field;
    display_name_field.type_name = "Component";
    display_name_field.path = "display_name";
    display_name_field.label = "Name";
    display_name_field.kind = "string";
    display_name_field.is_serializable = false;
    display_name_field.is_inspectable = true;
    display_name_field.getter = [](void* obj) -> tc_value {
        return tc_value_string(static_cast<CxxComponent*>(obj)->display_name().c_str());
    };
    display_name_field.setter = [](void* obj, tc_value value, void*) {
        if (value.type == TC_VALUE_STRING) {
            static_cast<CxxComponent*>(obj)->set_display_name(value.data.s ? value.data.s : "");
        }
    };
    tc::InspectRegistry::instance().add_field_with_choices("Component", std::move(display_name_field));

    tc::InspectRegistry::instance().add_with_accessors<CxxComponent, bool>(
        "Component", "enabled", "Enabled", "bool",
        [](CxxComponent* c) { return c->enabled(); },
        [](CxxComponent* c, bool v) { c->set_enabled(v); }
    );

    // Register atexit handler
    nb::object atexit_mod = nb::module_::import_("atexit");
    nb::object cleanup_fn = nb::cpp_function([]() {
        ComponentRegistry::instance().clear();
        tc::KindRegistry::instance().clear_python();
    });
    atexit_mod.attr("register")(cleanup_fn);

    (void)m;
}
