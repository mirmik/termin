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

extern "C" {
#include "tc_types.h"
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
    // Collider type: "Box", "Sphere", "Capsule"
    std::string collider_type = "Box";

    // Box size in local coordinates (multiplied by entity scale)
    double box_size_x = 1.0;
    double box_size_y = 1.0;
    double box_size_z = 1.0;

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
    // Note: collider_type and box_size are registered manually in .cpp with choices/vec3
    // Sphere and Capsule sizes are determined by entity scale (no separate fields)
    // collider_offset fields are registered manually in .cpp (need rebuild_collider on set)

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
    void set_box_size(double x, double y, double z);
    Vec3 get_box_size() const { return Vec3{box_size_x, box_size_y, box_size_z}; }

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

REGISTER_COMPONENT(ColliderComponent, Component);

} // namespace termin
