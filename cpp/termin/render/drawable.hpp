#pragma once

#include <string>
#include <set>
#include <vector>
#include <memory>

#include "termin/render/material.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"
#include "../../../core_c/include/tc_component.h"

namespace termin {

class GraphicsBackend;

/**
 * Geometry draw call - links a MaterialPhase to a geometry ID.
 *
 * Used by Drawable to specify which geometry to draw with which material phase.
 * geometry_id: 0 = default/all geometry, >0 = specific geometry slot
 */
struct GeometryDrawCall {
    MaterialPhase* phase = nullptr;
    int geometry_id = 0;

    GeometryDrawCall() = default;
    GeometryDrawCall(MaterialPhase* p, int gid = 0)
        : phase(p), geometry_id(gid) {}
};

/**
 * Drawable interface for components that can render geometry.
 *
 * Protocol (interface) for render components like MeshRenderer, LineRenderer.
 * Frame passes use this to collect and render objects.
 *
 * Attributes:
 *   phase_marks: Set of phase names this drawable participates in
 *                (e.g., {"opaque", "shadow"}, {"transparent"}, {"editor"})
 *
 * Methods:
 *   draw_geometry: Draw the geometry (shader already bound by pass)
 *   get_geometry_draws: Return MaterialPhases for ColorPass
 */
class Drawable {
public:
    // Cached geometry draws for get_geometry_draws vtable callback
    // (vtable returns pointer to this, caller must not free)
    mutable std::vector<GeometryDrawCall> _cached_geometry_draws;

    virtual ~Drawable() = default;

    /**
     * Get set of phase marks this drawable participates in.
     *
     * Examples:
     * - {"opaque"} - only opaque pass
     * - {"opaque", "shadow"} - opaque and shadow passes
     * - {"transparent"} - transparent pass
     * - {"editor"} - editor-only rendering
     */
    virtual std::set<std::string> get_phase_marks() const = 0;

    /**
     * Draw geometry.
     *
     * Shader and material are already bound by the pass before calling.
     * Drawable should just draw its geometry (mesh, lines, etc.)
     *
     * @param context Render context with view/projection matrices
     * @param geometry_id Geometry slot to draw (0 = default/all)
     */
    virtual void draw_geometry(const RenderContext& context, int geometry_id = 0) = 0;

    /**
     * Get geometry draw calls for this drawable.
     *
     * Used by ColorPass to get materials and geometries.
     * ShadowPass ignores this and uses its own shader.
     *
     * @param phase_mark Filter by phase mark (nullptr = all phases)
     * @return List of GeometryDrawCall sorted by priority
     */
    virtual std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) = 0;

    /**
     * Override shader for a draw call.
     *
     * Called by pass before applying uniforms. Allows drawable to substitute
     * a different shader (e.g., with skinning injected).
     *
     * @param phase_mark Current phase mark
     * @param geometry_id Geometry slot being drawn (0 = default)
     * @param original_shader Shader the pass intends to use
     * @return Shader to use (original or modified)
     */
    virtual TcShader override_shader(
        const std::string& phase_mark,
        int geometry_id,
        TcShader original_shader
    ) {
        return original_shader;  // Default: no override
    }

    /**
     * Check if this drawable participates in a given phase.
     */
    bool has_phase(const std::string& phase_mark) const {
        auto marks = get_phase_marks();
        return marks.find(phase_mark) != marks.end();
    }

    // Static drawable vtable for C components
    static const tc_drawable_vtable cxx_drawable_vtable;

protected:
    // Set drawable_vtable on the C component (call from subclass constructor)
    void install_drawable_vtable(tc_component* c) {
        if (c) {
            c->drawable_vtable = &cxx_drawable_vtable;
        }
    }

private:
    // Static callbacks for drawable vtable
    static bool _cb_has_phase(tc_component* c, const char* phase_mark);
    static void _cb_draw_geometry(tc_component* c, void* render_context, int geometry_id);
    static void* _cb_get_geometry_draws(tc_component* c, const char* phase_mark);
    static tc_shader_handle _cb_override_shader(tc_component* c, const char* phase_mark, int geometry_id, tc_shader_handle original_shader);
};

// Draw call for passes - combines entity, component, phase, and geometry.
struct PhaseDrawCall {
    Entity entity;
    tc_component* component = nullptr;  // Component with drawable_vtable
    MaterialPhase* phase = nullptr;
    int priority = 0;
    int geometry_id = 0;
};

} // namespace termin
