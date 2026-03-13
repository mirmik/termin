#include <components/mesh_component.hpp>
#include <tc_inspect_cpp.hpp>

namespace termin {

void MeshComponent::register_type() {
    auto& component_registry = ComponentRegistry::instance();
    if (!component_registry.has("MeshComponent")) {
        component_registry.register_native(
            "MeshComponent",
            &CxxComponentFactoryData<MeshComponent>::create,
            nullptr,
            "Component"
        );
    }

    auto& inspect = tc::InspectRegistry::instance();
    inspect.set_type_parent("MeshComponent", "Component");
    if (!inspect.find_field("MeshComponent", "mesh")) {
        inspect.add<MeshComponent, TcMesh>(
            "MeshComponent",
            &MeshComponent::mesh,
            "mesh",
            "Mesh",
            "tc_mesh"
        );
    }
}

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
