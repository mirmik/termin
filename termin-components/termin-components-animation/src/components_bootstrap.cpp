#include <termin/animation/components_bootstrap.hpp>

#include <termin/animation/animation_player.hpp>
#include <termin/render/skeleton_components_bootstrap.hpp>

namespace termin::animation {

void register_builtin_animation_component_types() {
    termin::register_builtin_skeleton_component_types();
    AnimationPlayer::register_type();
}

} // namespace termin::animation
