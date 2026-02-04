#include "collider_component.hpp"
#include "tc_log.hpp"
#include "tc_entity_pool.h"
#include "tc_inspect_cpp.hpp"
#include <algorithm>

namespace termin {

// Register collider_type field with enum choices
static struct _ColliderTypeFieldRegistrar {
    _ColliderTypeFieldRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "ColliderComponent";
        info.path = "collider_type";
        info.label = "Type";
        info.kind = "enum";

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<ColliderComponent*>(obj);
            return tc_value_string(c->collider_type.c_str());
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<ColliderComponent*>(obj);
            if (value.type == TC_VALUE_STRING) {
                c->set_collider_type(value.data.s);
            }
        };

        info.choices.push_back({"Box", "Box"});
        info.choices.push_back({"Sphere", "Sphere"});
        info.choices.push_back({"Capsule", "Capsule"});

        tc::InspectRegistry::instance().add_field_with_choices("ColliderComponent", std::move(info));
    }
} _collider_type_registrar;

// Register box_size field as vec3
static struct _BoxSizeFieldRegistrar {
    _BoxSizeFieldRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "ColliderComponent";
        info.path = "box_size";
        info.label = "Size";
        info.kind = "vec3";
        info.min = 0.001;
        info.max = 1000.0;
        info.step = 0.1;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<ColliderComponent*>(obj);
            tc_vec3 v = {c->box_size_x, c->box_size_y, c->box_size_z};
            return tc_value_vec3(v);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<ColliderComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->set_box_size(value.data.v3.x, value.data.v3.y, value.data.v3.z);
            } else if (value.type == TC_VALUE_LIST && tc_value_list_size(&value) >= 3) {
                // JSON/Python stores as [x, y, z] list
                tc_value* x = tc_value_list_get(&value, 0);
                tc_value* y = tc_value_list_get(&value, 1);
                tc_value* z = tc_value_list_get(&value, 2);
                auto get_double = [](tc_value* v) -> double {
                    if (!v) return 1.0;
                    if (v->type == TC_VALUE_DOUBLE) return v->data.d;
                    if (v->type == TC_VALUE_FLOAT) return v->data.f;
                    if (v->type == TC_VALUE_INT) return static_cast<double>(v->data.i);
                    return 1.0;
                };
                c->set_box_size(get_double(x), get_double(y), get_double(z));
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("ColliderComponent", std::move(info));
    }
} _box_size_registrar;

ColliderComponent::ColliderComponent() {
    link_type_entry("ColliderComponent");
}

ColliderComponent::~ColliderComponent() {
    _remove_from_collision_world();
}

void ColliderComponent::on_added() {
    CxxComponent::on_added();

    Entity ent = entity();
    if (!ent.valid()) {
        tc::Log::error("ColliderComponent::on_added: entity is invalid");
        return;
    }

    // Store transform for AttachedCollider
    _transform = ent.transform();

    // Get scene handle from pool
    _scene_handle = TC_SCENE_HANDLE_INVALID;
    if (tc_entity_handle_valid(_c.owner)) {
        tc_entity_pool* pool = tc_entity_pool_registry_get(_c.owner.pool);
        if (pool) {
            _scene_handle = tc_entity_pool_get_scene(pool);
        }
    }

    rebuild_collider();
}

void ColliderComponent::on_removed() {
    _remove_from_collision_world();
    _attached.reset();
    _collider.reset();
    _scene_handle = TC_SCENE_HANDLE_INVALID;

    CxxComponent::on_removed();
}

void ColliderComponent::rebuild_collider() {
    // Remove old collider from collision world
    _remove_from_collision_world();
    _attached.reset();

    // Create new collider
    _collider = _create_collider();
    if (!_collider) {
        tc::Log::error("ColliderComponent::rebuild_collider: failed to create collider");
        return;
    }

    // Create attached collider if transform is valid
    if (_transform.valid()) {
        // Get entity ID for collision tracking
        tc_entity_id entity_id = TC_ENTITY_ID_INVALID;
        if (tc_entity_handle_valid(_c.owner)) {
            entity_id = _c.owner.id;
        }

        _attached = std::make_unique<colliders::AttachedCollider>(
            _collider.get(),
            &_transform,
            entity_id
        );
        _add_to_collision_world();
    }
}

void ColliderComponent::set_collider_type(const std::string& type) {
    if (type != collider_type) {
        collider_type = type;
        rebuild_collider();
    }
}

void ColliderComponent::set_box_size(double x, double y, double z) {
    box_size_x = x;
    box_size_y = y;
    box_size_z = z;
    rebuild_collider();
}

std::unique_ptr<colliders::ColliderPrimitive> ColliderComponent::_create_collider() const {
    if (collider_type == "Box") {
        // Box uses box_size as local size (entity scale applied via transform)
        Vec3 half_size{box_size_x / 2.0, box_size_y / 2.0, box_size_z / 2.0};
        return std::make_unique<colliders::BoxCollider>(half_size);
    }
    else if (collider_type == "Sphere") {
        // Sphere uses uniform component of size as diameter
        // radius = min(size.x, size.y, size.z) / 2
        double uniform_size = std::min({box_size_x, box_size_y, box_size_z});
        return std::make_unique<colliders::SphereCollider>(uniform_size / 2.0);
    }
    else if (collider_type == "Capsule") {
        // Capsule: height = size.z, radius = min(size.x, size.y) / 2
        double radius = std::min(box_size_x, box_size_y) / 2.0;
        double half_height = box_size_z / 2.0;
        return std::make_unique<colliders::CapsuleCollider>(radius, half_height);
    }
    else {
        tc::Log::warn("ColliderComponent: unknown collider type '%s', defaulting to Box", collider_type.c_str());
        return std::make_unique<colliders::BoxCollider>(Vec3{0.5, 0.5, 0.5});
    }
}

collision::CollisionWorld* ColliderComponent::_get_collision_world() const {
    if (!tc_scene_alive(_scene_handle)) {
        return nullptr;
    }
    void* cw = tc_scene_get_collision_world(_scene_handle);
    return static_cast<collision::CollisionWorld*>(cw);
}

void ColliderComponent::_remove_from_collision_world() {
    if (!_attached) return;

    collision::CollisionWorld* cw = _get_collision_world();
    if (cw) {
        cw->remove(_attached.get());
    }
}

void ColliderComponent::_add_to_collision_world() {
    if (!_attached) return;

    collision::CollisionWorld* cw = _get_collision_world();
    if (cw) {
        cw->add(_attached.get());
    }
}

} // namespace termin
