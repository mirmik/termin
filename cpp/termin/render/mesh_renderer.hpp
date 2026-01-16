#pragma once

#include <vector>
#include <set>
#include <string>

#include "termin/entity/component_registry.hpp"
#include "termin/entity/component.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"
#include "termin/material/tc_material_handle.hpp"
#include "termin/assets/handles.hpp"
#include "termin/render/drawable.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/mesh_gpu.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "trent/trent.h"
#include <memory>

namespace termin {

/**
 * MeshRenderer - component that renders a mesh with a material.
 *
 * Stores mesh directly as TcMesh (GPU-ready mesh from registry).
 * Supports material override for per-instance customization.
 */
class MeshRenderer : public Component, public Drawable {
public:
    // Mesh to render (GPU-ready, from tc_mesh registry)
    TcMesh mesh;

    // Material for rendering (C-based tc_material)
    TcMaterial material;

    // Shadow casting
    bool cast_shadow = true;

    // Material override (creates a copy of tc_material for per-instance customization)
    bool _override_material = false;
    TcMaterial _overridden_material;
    std::unique_ptr<nos::trent> _pending_override_data;

    // INSPECT_FIELD registrations
    INSPECT_FIELD(MeshRenderer, mesh, "Mesh", "tc_mesh")
    INSPECT_FIELD(MeshRenderer, material, "Material", "tc_material")
    INSPECT_FIELD(MeshRenderer, cast_shadow, "Cast Shadow", "bool")
    INSPECT_FIELD(MeshRenderer, _override_material, "Override Material", "bool")

    MeshRenderer();
    virtual ~MeshRenderer() = default;

    // --- Mesh ---

    /**
     * Get mesh reference.
     */
    TcMesh& get_mesh() { return mesh; }
    const TcMesh& get_mesh() const { return mesh; }

    /**
     * Set mesh directly.
     */
    void set_mesh(const TcMesh& m);

    /**
     * Set mesh by name (lookup in tc_mesh registry).
     */
    void set_mesh_by_name(const std::string& name);

    // --- Material ---

    /**
     * Get current material for rendering.
     * Returns overridden material if override is active, otherwise base material.
     */
    TcMaterial get_material() const;

    /**
     * Get raw tc_material pointer for current material.
     */
    tc_material* get_material_ptr() const;

    /**
     * Get base material.
     */
    TcMaterial get_base_material() const { return material; }

    /**
     * Get material reference.
     */
    TcMaterial& get_material_ref() { return material; }
    const TcMaterial& get_material_ref() const { return material; }

    /**
     * Set material.
     */
    void set_material(const TcMaterial& mat);

    /**
     * Set material by name (lookup in tc_material registry).
     */
    void set_material_by_name(const std::string& name);

    /**
     * Get/set override material flag.
     */
    bool override_material() const { return _override_material; }
    void set_override_material(bool value);

    /**
     * Get overridden material (if override is active).
     */
    TcMaterial get_overridden_material() const {
        return _override_material ? _overridden_material : TcMaterial();
    }

    // --- Phase marks ---

    /**
     * Get all phase marks for this renderer (Drawable interface).
     * Includes material phases + "shadow" if cast_shadow.
     */
    std::set<std::string> get_phase_marks() const override;

    /**
     * Alias for get_phase_marks (legacy).
     */
    std::set<std::string> phase_marks() const { return get_phase_marks(); }

    /**
     * Get GPU mesh cache for direct draw calls.
     */
    MeshGPU& mesh_gpu() { return _mesh_gpu; }

    // --- Rendering ---

    /**
     * Draw geometry with current shader (Drawable interface).
     * Shader is already bound by the pass.
     */
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;

    /**
     * Get material phases for given phase mark.
     * Returns sorted by priority.
     */
    std::vector<tc_material_phase*> get_phases_for_mark(const std::string& phase_mark);

    /**
     * Get geometry draw calls for given phase mark (Drawable interface).
     * Returns sorted by priority.
     * If phase_mark is nullptr, returns all phases.
     */
    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override;

    // For SERIALIZABLE_FIELD (must be public for macro access)
    nos::trent get_override_data() const;
    void set_override_data(const nos::trent& val);

    // Create override material lazily if needed (for deserialization)
    void try_create_override_material();

protected:
    // GPU mesh cache (uploaded buffers)
    MeshGPU _mesh_gpu;

private:
    void recreate_overridden_material();
    void apply_pending_override_data();
};

// Serializable field for override material data (must be after class definition)
SERIALIZABLE_FIELD(MeshRenderer, _overridden_material_data, get_override_data(), set_override_data(val))

REGISTER_COMPONENT(MeshRenderer, Component);
} // namespace termin
