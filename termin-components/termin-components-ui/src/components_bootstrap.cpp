#include <termin/ui/components_bootstrap.hpp>

#include <termin/ui/ui_component.hpp>
#include <termin/ui/world_ui_surface_component.hpp>

namespace termin {

void register_builtin_ui_component_types() {
    UIComponent::register_type();
    WorldUiSurfaceComponent::register_type();
}

} // namespace termin
