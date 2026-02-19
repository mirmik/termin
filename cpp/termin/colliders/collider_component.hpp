#pragma once

#include "../entity/component.hpp"
#include "../entity/component_registry.hpp"
#include "../entity/entity.hpp"
#include "../geom/general_transform3.hpp"
#include "colliders.hpp"
#include "../collision/collision_world.hpp"
#include "core/tc_scene.h"
#include <memory>
#include <string>
#include <functional>

extern "C" {
#include "tc_types.h"
#include "resources/tc_mesh.h"
}

namespace termin {

// ColliderComponent - attaches a collider primitive to an entity.
// The collider follows the entity's transform via AttachedCollider.
//
// Size is determined by entity scale:
// - Box: box_size * entity.scale (non-uniform)
// - Sphere: unit sphere scaled by min(scale.x, scale.y, scale.z)
// - Capsule: height scaled by scale.z, radius by min(scale.x, scale.y)
class ENTITY_API ColliderComponent : public CxxComponent {
public:
    // Collider type: "Box", "Sphere", "Capsule", "ConvexHull"
    std::string collider_type = "Box";

    // Box size in local coordinates (multiplied by entity scale)
    tc_vec3 box_size = {1.0, 1.0, 1.0};

    // Collider offset (local space, relative to entity origin)
    bool collider_offset_enabled = false;
    tc_vec3 collider_offset_position = {0, 0, 0};
    tc_vec3 collider_offset_euler = {0, 0, 0};  // Euler degrees (XYZ)

private:
    // Owned collider primitive
    std::unique_ptr<colliders::ColliderPrimitive> _collider;

    // Attached collider (combines primitive + transform)
    std::unique_ptr<colliders::AttachedCollider> _attached;

    // Transform reference stored for AttachedCollider pointer stability
    GeneralTransform3 _transform;

    // Cached scene handle for collision world access
    tc_scene_handle _scene_handle = TC_SCENE_HANDLE_INVALID;

public:
    // INSPECT_FIELD registrations
    // Note: collider_type is registered manually in .cpp with choices.
    // Sphere and Capsule sizes are determined by entity scale (no separate fields)

    ColliderComponent();
    ~ColliderComponent() override;

    // Lifecycle
    void on_added() override;
    void on_removed() override;

    // Accessors
    colliders::ColliderPrimitive* collider() const { return _collider.get(); }
    colliders::AttachedCollider* attached_collider() const { return _attached.get(); }

    // Rebuild collider after type or parameter change
    void rebuild_collider();

    // Set collider type and rebuild
    void set_collider_type(const std::string& type);

    // Set box size (full size, not half-size)
    void set_box_size(const tc_vec3& size);
    void set_box_size(double x, double y, double z) { set_box_size(tc_vec3{x, y, z}); }
    Vec3 get_box_size() const { return Vec3{box_size.x, box_size.y, box_size.z}; }

    // Mesh provider callback (set by render_lib to avoid circular dependency)
    // Given an entity, returns tc_mesh* from its MeshRenderer (or nullptr)
    using MeshProviderFn = std::function<tc_mesh*(Entity&)>;
    static MeshProviderFn mesh_provider;

private:
    // Create collider primitive based on current type and parameters
    std::unique_ptr<colliders::ColliderPrimitive> _create_collider() const;

    // Get collision world from scene
    collision::CollisionWorld* _get_collision_world() const;

    // Remove attached collider from collision world
    void _remove_from_collision_world();

    // Add attached collider to collision world
    void _add_to_collision_world();
};

// Field registrations (outside class - callbacks trigger rebuild_collider)
INSPECT_FIELD_CALLBACK(ColliderComponent, tc_vec3, box_size, "Size", "vec3",
    [](ColliderComponent* c) -> tc_vec3& { return c->box_size; },
    [](ColliderComponent* c, const tc_vec3& value) { c->set_box_size(value); },
    0.001, 1000.0, 0.1)

INSPECT_FIELD_CALLBACK(ColliderComponent, bool, collider_offset_enabled, "Collider Offset", "bool",
    [](ColliderComponent* c) -> bool& { return c->collider_offset_enabled; },
    [](ColliderComponent* c, const bool& value) {
        if (c->collider_offset_enabled != value) {
            c->collider_offset_enabled = value;
            c->rebuild_collider();
        }
    })

INSPECT_FIELD_CALLBACK(ColliderComponent, tc_vec3, collider_offset_position, "Offset Position", "vec3",
    [](ColliderComponent* c) -> tc_vec3& { return c->collider_offset_position; },
    [](ColliderComponent* c, const tc_vec3& value) {
        c->collider_offset_position = value;
        c->rebuild_collider();
    })

INSPECT_FIELD_CALLBACK(ColliderComponent, tc_vec3, collider_offset_euler, "Offset Rotation", "vec3",
    [](ColliderComponent* c) -> tc_vec3& { return c->collider_offset_euler; },
    [](ColliderComponent* c, const tc_vec3& value) {
        c->collider_offset_euler = value;
        c->rebuild_collider();
    })

REGISTER_COMPONENT(ColliderComponent, Component);

} // namespace termin
