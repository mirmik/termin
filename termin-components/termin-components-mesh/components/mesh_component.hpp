#pragma once

#include <string>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

namespace termin {

class ENTITY_API MeshComponent : public CxxComponent {
public:
    TcMesh mesh;

    INSPECT_FIELD(MeshComponent, mesh, "Mesh", "tc_mesh")

    MeshComponent();
    ~MeshComponent() override = default;

    static void register_type();

    TcMesh& get_mesh() { return mesh; }
    const TcMesh& get_mesh() const { return mesh; }

    void set_mesh(const TcMesh& value);
    void set_mesh_by_name(const std::string& name);
};

REGISTER_COMPONENT(MeshComponent, Component);

} // namespace termin
