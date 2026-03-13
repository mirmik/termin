#pragma once

#include <string>

#include <tc_value.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/quat.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

namespace termin {

class ENTITY_API MeshComponent : public CxxComponent {
public:
    TcMesh mesh;
    bool mesh_offset_enabled = false;
    tc_vec3 mesh_offset_position = {0, 0, 0};
    tc_vec3 mesh_offset_euler = {0, 0, 0};
    tc_vec3 mesh_offset_scale = {1.0, 1.0, 1.0};

    INSPECT_FIELD(MeshComponent, mesh, "Mesh", "tc_mesh")
    INSPECT_FIELD(MeshComponent, mesh_offset_enabled, "Mesh Offset", "bool")
    INSPECT_FIELD(MeshComponent, mesh_offset_position, "Offset Position", "vec3")
    INSPECT_FIELD(MeshComponent, mesh_offset_euler, "Offset Rotation", "vec3")
    INSPECT_FIELD(MeshComponent, mesh_offset_scale, "Offset Scale", "vec3")

    MeshComponent();
    ~MeshComponent() override = default;

    static void register_type();

    TcMesh& get_mesh() { return mesh; }
    const TcMesh& get_mesh() const { return mesh; }

    void set_mesh(const TcMesh& value);
    void set_mesh_by_name(const std::string& name);
    Mat44f get_mesh_offset_matrix() const;
};

REGISTER_COMPONENT(MeshComponent, Component);

} // namespace termin
