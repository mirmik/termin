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
#include <components/mesh_component.hpp>

namespace termin {

class ENTITY_API MeshRenderer : public Component, public Drawable {
public:
    TcMaterial material;
    bool cast_shadow = true;
    bool _override_material = false;
    TcMaterial _overridden_material;
    tc_value _pending_override_data = {TC_VALUE_NIL, {}};
    bool mesh_offset_enabled = false;
    tc_vec3 mesh_offset_position = {0, 0, 0};
    tc_vec3 mesh_offset_euler = {0, 0, 0};
    tc_vec3 mesh_offset_scale = {1.0, 1.0, 1.0};

private:
    MeshComponent* _mesh_component = nullptr;
    // Temporary bridge for constructor calls and legacy scene data before
    // MeshComponent is reachable. Cleared as soon as migration runs.
    TcMesh _pending_mesh_for_component;

    void bind_mesh_component();
    void migrate_legacy_mesh_to_component();
    void migrate_legacy_mesh_value_to_component(const tc_value* data);
    tc_mesh* current_mesh_ptr() const;
    void ensure_override_material_ready();
    void recreate_overridden_material();
    void apply_pending_override_data();

public:
    explicit MeshRenderer(const char* type_name = "MeshRenderer");
    virtual ~MeshRenderer();

    static void register_type();

    TcMesh& get_mesh();
    const TcMesh& get_mesh() const;
    MeshComponent* mesh_component() const { return _mesh_component; }
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
    void on_added() override;
    void start() override;
    void on_editor_start() override;
    void on_scene_active() override;
    void on_render_attach() override;
    tc_value serialize_data() const override;
    void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;
    tc_mesh* get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const override {
        (void)phase_mark;
        (void)geometry_id;
        return current_mesh_ptr();
    }
    Mat44f get_model_matrix(const Entity& entity) const override;
    std::vector<tc_material_phase*> get_phases_for_mark(const std::string& phase_mark);
    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override;
    tc_value get_override_data() const;
    void set_override_data(const tc_value* val);
    void try_create_override_material();

};

} // namespace termin
