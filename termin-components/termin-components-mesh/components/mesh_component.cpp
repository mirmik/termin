#include <components/mesh_component.hpp>

namespace termin {

MeshComponent::MeshComponent() {
    link_type_entry("MeshComponent");
}

void MeshComponent::set_mesh(const TcMesh& value) {
    mesh = value;
}

void MeshComponent::set_mesh_by_name(const std::string& name) {
    tc_mesh_handle h = tc_mesh_find_by_name(name.c_str());
    if (tc_mesh_handle_is_invalid(h)) {
        mesh = TcMesh();
        return;
    }
    mesh = TcMesh(h);
}

} // namespace termin
