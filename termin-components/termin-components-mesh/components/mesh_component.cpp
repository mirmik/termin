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
    if (!inspect.find_field("MeshComponent", "mesh_offset_enabled")) {
        inspect.add<MeshComponent, bool>(
            "MeshComponent",
            &MeshComponent::mesh_offset_enabled,
            "mesh_offset_enabled",
            "Mesh Offset",
            "bool"
        );
    }
    if (!inspect.find_field("MeshComponent", "mesh_offset_position")) {
        inspect.add<MeshComponent, tc_vec3>(
            "MeshComponent",
            &MeshComponent::mesh_offset_position,
            "mesh_offset_position",
            "Offset Position",
            "vec3"
        );
    }
    if (!inspect.find_field("MeshComponent", "mesh_offset_euler")) {
        inspect.add<MeshComponent, tc_vec3>(
            "MeshComponent",
            &MeshComponent::mesh_offset_euler,
            "mesh_offset_euler",
            "Offset Rotation",
            "vec3"
        );
    }
    if (!inspect.find_field("MeshComponent", "mesh_offset_scale")) {
        inspect.add<MeshComponent, tc_vec3>(
            "MeshComponent",
            &MeshComponent::mesh_offset_scale,
            "mesh_offset_scale",
            "Offset Scale",
            "vec3"
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

Mat44f MeshComponent::get_mesh_offset_matrix() const {
    if (!mesh_offset_enabled) {
        return Mat44f::identity();
    }

    constexpr double deg2rad = 3.14159265358979323846 / 180.0;
    Quat rx = Quat::from_axis_angle(Vec3(1, 0, 0), mesh_offset_euler.x * deg2rad);
    Quat ry = Quat::from_axis_angle(Vec3(0, 1, 0), mesh_offset_euler.y * deg2rad);
    Quat rz = Quat::from_axis_angle(Vec3(0, 0, 1), mesh_offset_euler.z * deg2rad);
    Quat rotation = rz * ry * rx;

    Vec3 pos(mesh_offset_position.x, mesh_offset_position.y, mesh_offset_position.z);
    Vec3 scl(mesh_offset_scale.x, mesh_offset_scale.y, mesh_offset_scale.z);
    return Mat44f::compose(pos, rotation, scl);
}

} // namespace termin
