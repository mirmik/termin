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

class MeshRenderer;

inline void set_mesh_renderer_override_material_from_inspect(MeshRenderer* self, const bool& value);
inline tc_value make_mesh_renderer_inspector_metadata();

class ENTITY_API MeshRenderer : public Component, public Drawable {
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
    INSPECT_FIELD_CALLBACK(
        MeshRenderer,
        bool,
        _override_material,
        "Override Material",
        "bool",
        [](MeshRenderer* self) -> bool& { return self->_override_material; },
        [](MeshRenderer* self, const bool& value) {
            set_mesh_renderer_override_material_from_inspect(self, value);
        })
    INSPECT_FIELD_ACCESSORS(
        MeshRenderer,
        TcMaterial,
        _overridden_material,
        "Overridden Material",
        "tc_material",
        [](MeshRenderer* self) -> TcMaterial {
            return self ? self->_overridden_material : TcMaterial();
        },
        [](MeshRenderer* self, TcMaterial value) {
            if (self) {
                self->_overridden_material = value;
            }
        },
        false,
        true)
    INSPECT_FIELD(MeshRenderer, mesh_offset_enabled,  "Mesh Offset",     "bool")
    INSPECT_FIELD(MeshRenderer, mesh_offset_position, "Offset Position", "vec3")
    INSPECT_FIELD(MeshRenderer, mesh_offset_euler,    "Offset Rotation", "vec3")
    INSPECT_FIELD(MeshRenderer, mesh_offset_scale,    "Offset Scale", "vec3")

private:
    void ensure_override_material_ready();
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

    TcMaterial get_overridden_material() const;

    std::set<std::string> get_phase_marks() const override;
    std::set<std::string> phase_marks() const { return get_phase_marks(); }
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;
    tc_mesh* get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const override {
        (void)phase_mark;
        (void)geometry_id;
        return mesh.get();
    }
    Mat44f get_model_matrix(const Entity& entity) const override;
    std::vector<tc_material_phase*> get_phases_for_mark(const std::string& phase_mark);
    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override;
    tc_value get_override_data() const;
    void set_override_data(const tc_value* val);
    void try_create_override_material();

    SERIALIZABLE_FIELD(MeshRenderer, _overridden_material_data, get_override_data(), set_override_data(val))
};

inline void set_mesh_renderer_override_material_from_inspect(MeshRenderer* self, const bool& value) {
    if (self) {
        self->set_override_material(value);
    }
}

inline tc_value make_mesh_renderer_inspector_layout_field(
    const char* path,
    const char* widget = nullptr,
    const char* visible_if = nullptr
) {
    tc_value item = tc_value_dict_new();
    tc_value_dict_set(&item, "kind", tc_value_string("field"));
    tc_value_dict_set(&item, "path", tc_value_string(path));
    if (widget && widget[0]) {
        tc_value_dict_set(&item, "widget", tc_value_string(widget));
    }
    if (visible_if && visible_if[0]) {
        tc_value_dict_set(&item, "visible_if", tc_value_string(visible_if));
    }
    return item;
}

inline tc_value make_mesh_renderer_inspector_section(const char* label) {
    tc_value item = tc_value_dict_new();
    tc_value_dict_set(&item, "kind", tc_value_string("section"));
    tc_value_dict_set(&item, "label", tc_value_string(label));
    return item;
}

inline tc_value make_mesh_renderer_inspector_separator() {
    tc_value item = tc_value_dict_new();
    tc_value_dict_set(&item, "kind", tc_value_string("separator"));
    return item;
}

inline tc_value make_mesh_renderer_inspector_metadata() {
    tc_value inspector = tc_value_dict_new();

    tc_value fields = tc_value_dict_new();
    tc_value overridden = tc_value_dict_new();
    tc_value_dict_set(&overridden, "visible_if", tc_value_string("_override_material"));
    tc_value_dict_set(&overridden, "widget", tc_value_string("inline_material"));
    tc_value_dict_set(&fields, "_overridden_material", overridden);
    tc_value_dict_set(&inspector, "fields", fields);

    tc_value layout = tc_value_list_new();
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("mesh"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("material"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("cast_shadow"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_section("Material Override"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("_override_material"));
    tc_value_list_push(
        &layout,
        make_mesh_renderer_inspector_layout_field(
            "_overridden_material",
            "inline_material",
            "_override_material"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_separator());
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("mesh_offset_enabled"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("mesh_offset_position"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("mesh_offset_euler"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("mesh_offset_scale"));
    tc_value_dict_set(&inspector, "layout", layout);

    return inspector;
}

INSPECT_TYPE_METADATA(MeshRenderer, inspector, make_mesh_renderer_inspector_metadata())

REGISTER_COMPONENT(MeshRenderer, Component);

} // namespace termin
