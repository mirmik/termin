#pragma once

#include <string>
#include <set>
#include <vector>
#include <memory>

#include "termin/render/material.hpp"
#include "termin/render/render_context.hpp"
#include "termin/entity/entity.hpp"

namespace termin {

class GraphicsBackend;

/**
 * Geometry draw call - links a MaterialPhase to a geometry ID.
 *
 * Used by Drawable to specify which geometry to draw with which material phase.
 */
struct GeometryDrawCall {
    MaterialPhase* phase = nullptr;
    std::string geometry_id;

    GeometryDrawCall() = default;
    GeometryDrawCall(MaterialPhase* p, const std::string& gid = "")
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
     * @param geometry_id Identifier for which geometry to draw (empty = default)
     */
    virtual void draw_geometry(const RenderContext& context, const std::string& geometry_id = "") = 0;

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
     * Check if this drawable participates in a given phase.
     */
    bool has_phase(const std::string& phase_mark) const {
        auto marks = get_phase_marks();
        return marks.find(phase_mark) != marks.end();
    }
};

// Draw call for passes - combines entity, drawable, phase, and geometry.
struct PhaseDrawCall {
    Entity entity;
    Drawable* drawable = nullptr;
    MaterialPhase* phase = nullptr;
    int priority = 0;
    std::string geometry_id;
};

} // namespace termin
