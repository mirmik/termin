// drawable.cpp - Drawable vtable implementation

#include "drawable.hpp"
#include "tc_shader_handle.hpp"

namespace termin {

// Static callback implementations for drawable vtable

bool Drawable::_cb_has_phase(tc_component* c, const char* phase_mark) {
    if (!c || !c->drawable_ptr) return false;

    Drawable* drawable = static_cast<Drawable*>(c->drawable_ptr);
    return drawable->has_phase(phase_mark ? phase_mark : "");
}

void Drawable::_cb_draw_geometry(tc_component* c, void* render_context, int geometry_id) {
    if (!c || !c->drawable_ptr) return;

    RenderContext* ctx = static_cast<RenderContext*>(render_context);
    if (!ctx) return;

    Drawable* drawable = static_cast<Drawable*>(c->drawable_ptr);
    drawable->draw_geometry(*ctx, geometry_id);
}

void* Drawable::_cb_get_geometry_draws(tc_component* c, const char* phase_mark) {
    if (!c || !c->drawable_ptr) return nullptr;

    Drawable* drawable = static_cast<Drawable*>(c->drawable_ptr);

    // Get draws and cache them
    std::string pm = phase_mark ? phase_mark : "";
    const std::string* pm_ptr = pm.empty() ? nullptr : &pm;
    drawable->_cached_geometry_draws = drawable->get_geometry_draws(pm_ptr);

    return &drawable->_cached_geometry_draws;
}

tc_shader_handle Drawable::_cb_override_shader(tc_component* c, const char* phase_mark, int geometry_id, tc_shader_handle original_shader) {
    if (!c || !c->drawable_ptr) return original_shader;

    Drawable* drawable = static_cast<Drawable*>(c->drawable_ptr);
    TcShader result = drawable->override_shader(
        phase_mark ? phase_mark : "",
        geometry_id,
        TcShader(original_shader)
    );
    return result.handle;
}

// Default model matrix: entity world transform
Mat44f Drawable::get_model_matrix(const Entity& entity) const {
    double m[16];
    entity.transform().world_matrix(m);
    Mat44f result;
    for (int i = 0; i < 16; ++i) {
        result.data[i] = static_cast<float>(m[i]);
    }
    return result;
}

// Static vtable instance
const tc_drawable_vtable Drawable::cxx_drawable_vtable = {
    &Drawable::_cb_has_phase,
    &Drawable::_cb_draw_geometry,
    &Drawable::_cb_get_geometry_draws,
    &Drawable::_cb_override_shader
};

} // namespace termin
