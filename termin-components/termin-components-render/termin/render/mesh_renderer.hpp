#pragma once

#include <memory>
#include <set>
#include <string>
#include <vector>

#include <tc_value.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/quat.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/render_context.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

namespace termin {

class MeshRenderer : public Component, public Drawable {
public:
    TcMesh mesh;
    TcMaterial material;
    bool cast_shadow = true;
    bool _override_material = false;
    TcMaterial _overridden_material;
    tc_value _pending_override_data = {TC_VALUE_NIL, {}};
    bool mesh_offset_enabled = false;
    tc_vec3 mesh_offset_position = {0, 0, 0};
    tc_vec3 mesh_offset_euler = {0, 0, 0};
    tc_vec3 mesh_offset_scale = {1.0, 1.0, 1.0};

    INSPECT_FIELD(MeshRenderer, mesh, "Mesh", "tc_mesh")
    INSPECT_FIELD(MeshRenderer, material, "Material", "tc_material")
    INSPECT_FIELD(MeshRenderer, cast_shadow, "Cast Shadow", "bool")
    INSPECT_FIELD(MeshRenderer, _override_material, "Override Material", "bool")
    INSPECT_FIELD(MeshRenderer, mesh_offset_enabled,  "Mesh Offset",     "bool")
    INSPECT_FIELD(MeshRenderer, mesh_offset_position, "Offset Position", "vec3")
    INSPECT_FIELD(MeshRenderer, mesh_offset_euler,    "Offset Rotation", "vec3")
    INSPECT_FIELD(MeshRenderer, mesh_offset_scale,    "Offset Scale",    "vec3")

private:
    void recreate_overridden_material();
    void apply_pending_override_data();

public:
    MeshRenderer();
    virtual ~MeshRenderer();

    TcMesh& get_mesh() { return mesh; }
    const TcMesh& get_mesh() const { return mesh; }
    void set_mesh(const TcMesh& m);
    void set_mesh_by_name(const std::string& name);

    TcMaterial get_material() const;
    tc_material* get_material_ptr() const;
    TcMaterial get_base_material() const { return material; }
    TcMaterial& get_material_ref() { return material; }
    const TcMaterial& get_material_ref() const { return material; }
    void set_material(const TcMaterial& mat);
    void set_material_by_name(const std::string& name);
    bool override_material() const { return _override_material; }
    void set_override_material(bool value);

    TcMaterial get_overridden_material() const {
        return _override_material ? _overridden_material : TcMaterial();
    }

    std::set<std::string> get_phase_marks() const override;
    std::set<std::string> phase_marks() const { return get_phase_marks(); }
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;
    Mat44f get_model_matrix(const Entity& entity) const override;
    std::vector<tc_material_phase*> get_phases_for_mark(const std::string& phase_mark);
    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override;
    tc_value get_override_data() const;
    void set_override_data(const tc_value* val);
    void try_create_override_material();
};

SERIALIZABLE_FIELD(MeshRenderer, _overridden_material_data, get_override_data(), set_override_data(val))

REGISTER_COMPONENT(MeshRenderer, Component);

} // namespace termin
