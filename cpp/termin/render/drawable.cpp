// drawable.cpp - Drawable vtable implementation

#include "drawable.hpp"

namespace termin {

// Static callback implementations for drawable vtable

bool Drawable::_cb_has_phase(tc_component* c, const char* phase_mark) {
    if (!c || c->kind != TC_CXX_COMPONENT) return false;

    CxxComponent* comp = CxxComponent::from_tc(c);
    if (!comp) return false;

    Drawable* drawable = dynamic_cast<Drawable*>(comp);
    if (!drawable) return false;

    return drawable->has_phase(phase_mark ? phase_mark : "");
}

void Drawable::_cb_draw_geometry(tc_component* c, void* render_context, const char* geometry_id) {
    if (!c || c->kind != TC_CXX_COMPONENT) return;

    CxxComponent* comp = CxxComponent::from_tc(c);
    if (!comp) return;

    Drawable* drawable = dynamic_cast<Drawable*>(comp);
    if (!drawable) return;

    RenderContext* ctx = static_cast<RenderContext*>(render_context);
    if (!ctx) return;

    drawable->draw_geometry(*ctx, geometry_id ? geometry_id : "");
}

void* Drawable::_cb_get_geometry_draws(tc_component* c, const char* phase_mark) {
    if (!c || c->kind != TC_CXX_COMPONENT) return nullptr;

    CxxComponent* comp = CxxComponent::from_tc(c);
    if (!comp) return nullptr;

    Drawable* drawable = dynamic_cast<Drawable*>(comp);
    if (!drawable) return nullptr;

    // Get draws and cache them
    std::string pm = phase_mark ? phase_mark : "";
    const std::string* pm_ptr = pm.empty() ? nullptr : &pm;
    drawable->_cached_geometry_draws = drawable->get_geometry_draws(pm_ptr);

    return &drawable->_cached_geometry_draws;
}

// Static vtable instance
const tc_drawable_vtable Drawable::cxx_drawable_vtable = {
    &Drawable::_cb_has_phase,
    &Drawable::_cb_draw_geometry,
    &Drawable::_cb_get_geometry_draws
};

} // namespace termin
