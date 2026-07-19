#pragma once

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/geom/general_transform3.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <termin/colliders/colliders.hpp>
#include <termin/collision/collision_world.hpp>
#include "core/tc_scene.h"
#include <memory>
#include <string>

extern "C" {
#include "tc_types.h"
#include <tgfx/resources/tc_mesh.h>
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

    // Source mesh for ConvexHull collider
    // "Field" uses convex_hull_mesh. "MeshComponent" uses the sibling MeshComponent mesh.
    std::string convex_hull_mesh_source = "Field";
    TcMesh convex_hull_mesh;

private:
    enum class BuildState {
        Detached,
        PendingSource,
        InvalidSource,
        Ready,
    };

    // Owned collider primitive
    std::unique_ptr<colliders::ColliderPrimitive> _collider;

    // Attached collider (combines primitive + transform)
    std::unique_ptr<colliders::AttachedCollider> _attached;

    // Transform reference stored for AttachedCollider pointer stability
    GeneralTransform3 _transform;

    // Cached scene handle for collision world access
    tc_scene_handle _scene_handle = TC_SCENE_HANDLE_INVALID;

    tc_event_subscription _mesh_changed_subscription = {0};
    tc_event_subscription _structure_changed_subscription = {0};
    BuildState _build_state = BuildState::Detached;
    bool _lifecycle_attached = false;
    uint64_t _collider_revision = 0;
    std::string _last_reported_build_error;

public:
    // Inspect fields are registered from register_type().
    // Note: collider_type is registered manually with choices.
    // Sphere and Capsule sizes are determined by entity scale (no separate fields)

    ColliderComponent();
    ~ColliderComponent() override;

    static void register_type();

    // Lifecycle
    void start() override;
    void on_added() override;
    void on_removed() override;

    // Accessors
    colliders::ColliderPrimitive* collider() const { return _collider.get(); }
    colliders::AttachedCollider* attached_collider() const { return _attached.get(); }
    uint64_t collider_revision() const { return _collider_revision; }

    // Rebuild collider after type or parameter change
    void rebuild_collider();

    // Set collider type and rebuild
    void set_collider_type(const std::string& type);

    // Set box size (full size, not half-size)
    void set_box_size(const tc_vec3& size);
    void set_box_size(double x, double y, double z) { set_box_size(tc_vec3{x, y, z}); }
    Vec3 get_box_size() const { return Vec3{box_size.x, box_size.y, box_size.z}; }
    void set_convex_hull_mesh_source(const std::string& source);
    void set_convex_hull_mesh(const TcMesh& mesh);

private:
    bool _uses_mesh_component_mesh() const;

    void _rebuild_collider(bool report_failure);
    void _report_build_failure_once(const std::string& message);
    void _subscribe_to_scene_events();
    void _unsubscribe_from_scene_events();
    void _handle_mesh_component_changed(const tc_event* event);
    void _handle_scene_structure_changed(const tc_event* event);
    static void _mesh_component_changed_callback(const tc_event* event, void* user_data);
    static void _scene_structure_changed_callback(const tc_event* event, void* user_data);

    // Create collider primitive based on current type and parameters
    std::unique_ptr<colliders::ColliderPrimitive> _create_collider(
        std::string& failure_reason,
        bool& source_pending) const;

    // Get collision world from scene
    collision::CollisionWorld* _get_collision_world() const;

    // Remove attached collider from collision world
    void _remove_from_collision_world();

    // Add attached collider to collision world
    void _add_to_collision_world();
};

} // namespace termin
