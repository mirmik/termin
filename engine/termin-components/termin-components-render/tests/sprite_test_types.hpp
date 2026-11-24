#pragma once

#include <tc_inspect_cpp.hpp>
#include <termin/entity/unknown_component.hpp>
#include <termin/render/sprite_animator_2d.hpp>
#include <termin/render/sprite_renderer_2d.hpp>

inline void register_sprite_test_types() {
    static const bool initialized = [] {
        tc::init_cpp_inspect_vtable();
        termin::register_builtin_scene_component_types();
        termin::SpriteRenderer2D::register_type();
        termin::SpriteAnimator2D::register_type();
        return true;
    }();
    (void)initialized;
}
