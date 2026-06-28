#include <termin/foliage/components_bootstrap.hpp>

#include <termin/foliage/foliage_layer_component.hpp>

namespace termin {

void register_builtin_foliage_component_types() {
    FoliageLayerComponent::register_type();
}

} // namespace termin
