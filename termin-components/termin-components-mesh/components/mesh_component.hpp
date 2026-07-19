#pragma once

#include <cstdint>
#include <string>

#include <tc_value.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/quat.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

namespace termin {

inline constexpr const char* TC_EVENT_MESH_COMPONENT_CHANGED =
    "termin.mesh_component.changed";

struct MeshComponentChangedEvent {
    tc_entity_handle entity = TC_ENTITY_HANDLE_INVALID;
    uint64_t revision = 0;
};

class ENTITY_API MeshComponent : public CxxComponent {
public:
    // Read access remains public for existing native render consumers. Writers
    // must use set_mesh(), set_generated_mesh(), or notify_mesh_changed() so
    // dependent components receive a revisioned scene event.
    TcMesh mesh;
    bool mesh_offset_enabled = false;
    tc_vec3 mesh_offset_position = {0, 0, 0};
    tc_vec3 mesh_offset_euler = {0, 0, 0};
    tc_vec3 mesh_offset_scale = {1.0, 1.0, 1.0};

    MeshComponent();
    ~MeshComponent() override = default;

    static void register_type();

    void on_added() override;

    tc_value serialize_data() const override;
    void deserialize_data(
        const tc_value* data,
        tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;

    TcMesh& get_mesh() { return mesh; }
    const TcMesh& get_mesh() const { return mesh; }

    void set_mesh(const TcMesh& value);
    // Generated meshes are provider-owned derived data. Their transient handle
    // is omitted from scene serialization and reconstructed by the provider.
    void set_generated_mesh(const TcMesh& value);
    void set_mesh_by_name(const std::string& name);
    void notify_mesh_changed();

    bool mesh_is_generated() const { return _mesh_generated; }
    uint64_t mesh_revision() const { return _mesh_revision; }

    void set_mesh_offset_enabled(bool value);
    void set_mesh_offset_position(const tc_vec3& value);
    void set_mesh_offset_euler(const tc_vec3& value);
    void set_mesh_offset_scale(const tc_vec3& value);
    Mat44f get_mesh_offset_matrix() const;

private:
    bool _mesh_generated = false;
    uint64_t _mesh_revision = 0;

    void _set_mesh(const TcMesh& value, bool generated);
    void _set_mesh_generated_from_serialization(bool generated);
    void _publish_mesh_changed();
};

} // namespace termin
