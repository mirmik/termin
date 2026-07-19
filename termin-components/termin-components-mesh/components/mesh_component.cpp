#include <components/mesh_component.hpp>
#include <tc_inspect_cpp.hpp>
#include <core/tc_scene.h>
#include <termin/tc_scene.hpp>

namespace termin {

void MeshComponent::register_type() {
    auto descriptor = ComponentTypeDescriptorBuilder::native<MeshComponent>(
        "MeshComponent", "termin-components-mesh", "Component");
    auto& inspect = descriptor.inspect();
    if (!inspect.find_field("MeshComponent", "mesh_generated")) {
        tc::InspectFieldSpec spec = tc::inspect_field_spec(
            "MeshComponent",
            "mesh_generated",
            "Generated Mesh",
            "bool"
        );
        spec.is_inspectable = false;
        inspect.add_with_callbacks<MeshComponent, bool>(
            spec,
            [](MeshComponent* c) { return c->mesh_is_generated(); },
            [](MeshComponent* c, bool generated) {
                c->_set_mesh_generated_from_serialization(generated);
            }
        );
    }
    if (!inspect.find_field("MeshComponent", "mesh")) {
        inspect.add_with_callbacks<MeshComponent, TcMesh>(
            "MeshComponent",
            "mesh",
            "Mesh",
            "tc_mesh",
            [](MeshComponent* c) -> TcMesh& { return c->mesh; },
            [](MeshComponent* c, const TcMesh& value) {
                if (c->mesh_is_generated() && !value.is_valid()) {
                    c->set_generated_mesh(value);
                } else {
                    c->set_mesh(value);
                }
            }
        );
    }
    if (!inspect.find_field("MeshComponent", "mesh_offset_enabled")) {
        inspect.add_with_callbacks<MeshComponent, bool>(
            "MeshComponent",
            "mesh_offset_enabled",
            "Mesh Offset",
            "bool",
            [](MeshComponent* c) { return c->mesh_offset_enabled; },
            [](MeshComponent* c, bool value) { c->set_mesh_offset_enabled(value); }
        );
    }
    if (!inspect.find_field("MeshComponent", "mesh_offset_position")) {
        inspect.add_with_callbacks<MeshComponent, tc_vec3>(
            "MeshComponent",
            "mesh_offset_position",
            "Offset Position",
            "vec3",
            [](MeshComponent* c) -> tc_vec3& { return c->mesh_offset_position; },
            [](MeshComponent* c, const tc_vec3& value) {
                c->set_mesh_offset_position(value);
            }
        );
    }
    if (!inspect.find_field("MeshComponent", "mesh_offset_euler")) {
        inspect.add_with_callbacks<MeshComponent, tc_vec3>(
            "MeshComponent",
            "mesh_offset_euler",
            "Offset Rotation",
            "vec3",
            [](MeshComponent* c) -> tc_vec3& { return c->mesh_offset_euler; },
            [](MeshComponent* c, const tc_vec3& value) {
                c->set_mesh_offset_euler(value);
            }
        );
    }
    if (!inspect.find_field("MeshComponent", "mesh_offset_scale")) {
        inspect.add_with_callbacks<MeshComponent, tc_vec3>(
            "MeshComponent",
            "mesh_offset_scale",
            "Offset Scale",
            "vec3",
            [](MeshComponent* c) -> tc_vec3& { return c->mesh_offset_scale; },
            [](MeshComponent* c, const tc_vec3& value) {
                c->set_mesh_offset_scale(value);
            }
        );
    }
    (void)descriptor.commit();
}

MeshComponent::MeshComponent()
    : CxxComponent("MeshComponent")
{}

void MeshComponent::on_added() {
    CxxComponent::on_added();
    _publish_mesh_changed();
}

tc_value MeshComponent::serialize_data() const {
    tc_value data = CxxComponent::serialize_data();
    if (_mesh_generated && data.type == TC_VALUE_DICT) {
        tc_value_dict_set(&data, "mesh", TcMesh().serialize_to_value());
    }
    return data;
}

void MeshComponent::deserialize_data(const tc_value* data, tc_scene_handle scene) {
    if (!data || data->type != TC_VALUE_DICT) {
        CxxComponent::deserialize_data(data, scene);
        return;
    }

    tc_value* generated_value = tc_value_dict_get(
        const_cast<tc_value*>(data),
        "mesh_generated"
    );
    const bool generated = generated_value &&
        generated_value->type == TC_VALUE_BOOL &&
        generated_value->data.b;
    if (!generated) {
        CxxComponent::deserialize_data(data, scene);
        return;
    }

    // Generated geometry is reconstructed by its provider component. Filter
    // the transient handle before generic inspect deserialization so field
    // registration order cannot accidentally resolve it as an asset.
    _mesh_generated = true;
    tc_value filtered = tc_value_copy(data);
    tc_value_dict_set(&filtered, "mesh", TcMesh().serialize_to_value());
    CxxComponent::deserialize_data(&filtered, scene);
    tc_value_free(&filtered);
}

void MeshComponent::set_mesh(const TcMesh& value) {
    _set_mesh(value, false);
}

void MeshComponent::set_generated_mesh(const TcMesh& value) {
    _set_mesh(value, true);
}

void MeshComponent::_set_mesh(const TcMesh& value, bool generated) {
    mesh = value;
    _mesh_generated = generated;
    notify_mesh_changed();
}

void MeshComponent::_set_mesh_generated_from_serialization(bool generated) {
    _mesh_generated = generated;
}

void MeshComponent::notify_mesh_changed() {
    ++_mesh_revision;
    _publish_mesh_changed();

    TcSceneRef owner_scene = entity().scene();
    if (owner_scene.valid()) {
        owner_scene.request_render();
    }
}

void MeshComponent::_publish_mesh_changed() {
    Entity owner = entity();
    if (!owner.valid()) {
        return;
    }

    TcSceneRef owner_scene = owner.scene();
    if (!owner_scene.valid()) {
        return;
    }

    MeshComponentChangedEvent payload{
        _c.owner,
        _mesh_revision,
    };
    tc_event event{
        TC_EVENT_MESH_COMPONENT_CHANGED,
        this,
        &payload,
        sizeof(payload),
        0,
    };
    tc_scene_publish_event(owner_scene._h, &event);
}

void MeshComponent::set_mesh_by_name(const std::string& name) {
    tc_mesh_handle h = tc_mesh_find_by_name(name.c_str());
    if (tc_mesh_handle_is_invalid(h)) {
        set_mesh(TcMesh());
        return;
    }
    set_mesh(TcMesh(h));
}

void MeshComponent::set_mesh_offset_enabled(bool value) {
    if (mesh_offset_enabled == value) {
        return;
    }
    mesh_offset_enabled = value;
    notify_mesh_changed();
}

void MeshComponent::set_mesh_offset_position(const tc_vec3& value) {
    mesh_offset_position = value;
    notify_mesh_changed();
}

void MeshComponent::set_mesh_offset_euler(const tc_vec3& value) {
    mesh_offset_euler = value;
    notify_mesh_changed();
}

void MeshComponent::set_mesh_offset_scale(const tc_vec3& value) {
    mesh_offset_scale = value;
    notify_mesh_changed();
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
