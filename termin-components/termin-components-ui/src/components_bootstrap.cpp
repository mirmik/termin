#include <termin/ui/components_bootstrap.hpp>

#include <termin/ui/ui_component.hpp>

namespace termin {

void register_builtin_ui_component_types() {
    UIComponent::register_type();
}

} // namespace termin
