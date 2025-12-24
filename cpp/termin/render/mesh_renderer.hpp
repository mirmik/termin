#pragma once

#include <vector>
#include <set>
#include <string>

#include "termin/entity/component_registry.hpp"
#include "termin/entity/component.hpp"
#include "termin/assets/handles.hpp"
#include "termin/render/material.hpp"
#include "termin/render/drawable.hpp"
#include "termin/render/render_context.hpp"
#include "termin/inspect/inspect_registry.hpp"

namespace termin {

/**
 * MeshRenderer - component that renders a mesh with a material.
 *
 * Stores mesh via MeshHandle and material via MaterialHandle.
 * Supports material override for per-instance customization.
 */
class MeshRenderer : public Component {
public:
    // Mesh to render
    MeshHandle mesh;

    // Material for rendering
    MaterialHandle material;

    // Shadow casting
    bool cast_shadow = true;

    // Material override
    bool _override_material = false;
    Material* _overridden_material = nullptr;

    // INSPECT_FIELD registrations
    INSPECT_FIELD(MeshRenderer, mesh, "Mesh", "mesh")
    INSPECT_FIELD(MeshRenderer, material, "Material", "material")
    INSPECT_FIELD(MeshRenderer, cast_shadow, "Cast Shadow", "bool")

    MeshRenderer();
    virtual ~MeshRenderer() = default;

    // --- Mesh ---

    /**
     * Get mesh handle.
     */
    MeshHandle& mesh_handle() { return mesh; }
    const MeshHandle& mesh_handle() const { return mesh; }

    /**
     * Set mesh by handle.
     */
    void set_mesh(const MeshHandle& handle);

    /**
     * Set mesh by name (lookup in ResourceManager).
     */
    void set_mesh_by_name(const std::string& name);

    // --- Material ---

    /**
     * Get current material for rendering.
     * Returns overridden material if override is active, otherwise base material.
     */
    Material* get_material() const;

    /**
     * Get base material (from handle).
     */
    Material* get_base_material() const;

    /**
     * Get material handle.
     */
    MaterialHandle& material_handle() { return material; }
    const MaterialHandle& material_handle() const { return material; }

    /**
     * Set base material.
     */
    void set_material(Material* material);

    /**
     * Set material by handle.
     */
    void set_material_handle(const MaterialHandle& handle);

    /**
     * Set material by name (lookup in ResourceManager).
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
    Material* overridden_material() const {
        return _override_material ? _overridden_material : nullptr;
    }

    // --- Phase marks ---

    /**
     * Get all phase marks for this renderer.
     * Includes material phases + "shadow" if cast_shadow.
     */
    std::set<std::string> phase_marks() const;

    // --- Rendering ---

    /**
     * Draw geometry with current shader.
     * Shader is already bound by the pass.
     */
    virtual void draw_geometry(const RenderContext& context, const std::string& geometry_id = "");

    /**
     * Get material phases for given phase mark.
     * Returns sorted by priority.
     */
    virtual std::vector<MaterialPhase*> get_phases_for_mark(const std::string& phase_mark);

    /**
     * Get geometry draw calls for given phase mark.
     * Returns sorted by priority.
     * If phase_mark is empty, returns all phases.
     */
    virtual std::vector<GeometryDrawCall> get_geometry_draws(const std::string& phase_mark = "");

    // --- Serialization (py::dict based) ---

    // nos::trent serialize_data() const;
    // void deserialize_data(const nos::trent& data);

private:
    void recreate_overridden_material();
};

REGISTER_COMPONENT(MeshRenderer);
} // namespace termin
