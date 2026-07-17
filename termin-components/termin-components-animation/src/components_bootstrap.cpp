#include <termin/animation/components_bootstrap.hpp>

#include <termin/animation/animation_player.hpp>

namespace termin::animation {

void register_builtin_animation_component_types() {
    AnimationPlayer::register_type();
}

} // namespace termin::animation
