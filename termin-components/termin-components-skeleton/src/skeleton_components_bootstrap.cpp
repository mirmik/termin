#include <termin/render/skeleton_components_bootstrap.hpp>

#include <termin/render/skeleton_controller.hpp>

namespace termin {

void register_builtin_skeleton_component_types() {
    SkeletonController::register_type();
}

} // namespace termin
