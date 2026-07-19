#include <components/collider_component.hpp>
#include <components/mesh_component.hpp>
#include <tcbase/tc_log.hpp>
#include "core/tc_entity_pool.h"
#include "physics/tc_collision_world.h"
#include "tc_inspect_cpp.hpp"
#include <algorithm>
#include <cstring>
#include <vector>

namespace termin {

namespace {

// Register collider_type field with enum choices
void register_collider_type_field(tc::InspectFacetBuilder& builder) {
        tc::InspectFieldInfo info;
        info.type_name = "ColliderComponent";
        info.path = "collider_type";
        info.label = "Type";
        info.kind = "enum";

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<ColliderComponent*>(obj);
            return tc_value_string(c->collider_type.c_str());
        };

        info.setter = [](void* obj, tc_value value, void*) -> bool {
            auto* c = static_cast<ColliderComponent*>(obj);
            if (value.type == TC_VALUE_STRING) {
                c->set_collider_type(value.data.s);
                return true;
            }
            return false;
        };

        info.choices.push_back({"Box", "Box"});
        info.choices.push_back({"Sphere", "Sphere"});
        info.choices.push_back({"Capsule", "Capsule"});
        info.choices.push_back({"ConvexHull", "ConvexHull"});

        (void)builder.add_field(std::move(info));
}

// Register ConvexHull mesh source field with enum choices
void register_convex_hull_mesh_source_field(tc::InspectFacetBuilder& builder) {
        tc::InspectFieldInfo info;
        info.type_name = "ColliderComponent";
        info.path = "convex_hull_mesh_source";
        info.label = "Convex Hull Mesh Source";
        info.kind = "enum";

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<ColliderComponent*>(obj);
            return tc_value_string(c->convex_hull_mesh_source.c_str());
        };

        info.setter = [](void* obj, tc_value value, void*) -> bool {
            auto* c = static_cast<ColliderComponent*>(obj);
            if (value.type == TC_VALUE_STRING) {
                c->set_convex_hull_mesh_source(value.data.s);
                return true;
            }
            return false;
        };

        info.choices.push_back({"Field", "Field"});
        info.choices.push_back({"MeshComponent", "MeshComponent"});

        (void)builder.add_field(std::move(info));
}

void register_collider_component_inspect_fields(tc::InspectFacetBuilder& builder) {
    register_collider_type_field(builder);
    register_convex_hull_mesh_source_field(builder);

    builder.add_with_callbacks<ColliderComponent, tc_vec3>(
        "ColliderComponent",
        "box_size",
        "Size",
        "vec3",
        [](ColliderComponent* c) -> tc_vec3& { return c->box_size; },
        [](ColliderComponent* c, const tc_vec3& value) { c->set_box_size(value); },
        0.001,
        1000.0,
        0.1
    );
    builder.add_with_callbacks<ColliderComponent, TcMesh>(
        "ColliderComponent",
        "convex_hull_mesh",
        "Convex Hull Mesh",
        "tc_mesh",
        [](ColliderComponent* c) -> TcMesh& { return c->convex_hull_mesh; },
        [](ColliderComponent* c, const TcMesh& value) { c->set_convex_hull_mesh(value); }
    );
    builder.add_with_callbacks<ColliderComponent, bool>(
        "ColliderComponent",
        "collider_offset_enabled",
        "Collider Offset",
        "bool",
        [](ColliderComponent* c) -> bool& { return c->collider_offset_enabled; },
        [](ColliderComponent* c, const bool& value) {
            if (c->collider_offset_enabled != value) {
                c->collider_offset_enabled = value;
                c->rebuild_collider();
            }
        }
    );
    builder.add_with_callbacks<ColliderComponent, tc_vec3>(
        "ColliderComponent",
        "collider_offset_position",
        "Offset Position",
        "vec3",
        [](ColliderComponent* c) -> tc_vec3& { return c->collider_offset_position; },
        [](ColliderComponent* c, const tc_vec3& value) {
            c->collider_offset_position = value;
            c->rebuild_collider();
        }
    );
    builder.add_with_callbacks<ColliderComponent, tc_vec3>(
        "ColliderComponent",
        "collider_offset_euler",
        "Offset Rotation",
        "vec3",
        [](ColliderComponent* c) -> tc_vec3& { return c->collider_offset_euler; },
        [](ColliderComponent* c, const tc_vec3& value) {
            c->collider_offset_euler = value;
            c->rebuild_collider();
        }
    );
}

} // namespace

ColliderComponent::ColliderComponent()
    : CxxComponent("ColliderComponent")
{}

void ColliderComponent::register_type() {
    auto descriptor = ComponentTypeDescriptorBuilder::native<ColliderComponent>(
        "ColliderComponent", "termin-components-collision", "Component");
    descriptor.category("Collision");
    register_collider_component_inspect_fields(descriptor.inspect());
    (void)descriptor.commit();
}

ColliderComponent::~ColliderComponent() {
    _unsubscribe_from_scene_events();
    _remove_from_collision_world();
}

void ColliderComponent::start() {
    if (_build_state != BuildState::Ready) {
        _rebuild_collider(true);
    }
}

void ColliderComponent::on_added() {
    CxxComponent::on_added();

    _lifecycle_attached = true;

    Entity ent = entity();
    if (!ent.valid()) {
        tc::Log::error("ColliderComponent::on_added: entity is invalid");
        _lifecycle_attached = false;
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

    _subscribe_to_scene_events();
    _rebuild_collider(false);
}

void ColliderComponent::on_removed() {
    _unsubscribe_from_scene_events();
    _remove_from_collision_world();
    _attached.reset();
    _collider.reset();
    _scene_handle = TC_SCENE_HANDLE_INVALID;
    _lifecycle_attached = false;
    _build_state = BuildState::Detached;
    _last_reported_build_error.clear();

    CxxComponent::on_removed();
}

void ColliderComponent::rebuild_collider() {
    _rebuild_collider(true);
}

void ColliderComponent::_rebuild_collider(bool report_failure) {
    const bool detached = !_lifecycle_attached;
    if (detached && collider_type == "ConvexHull") {
        _attached.reset();
        _collider.reset();
        _build_state = BuildState::Detached;
        return;
    }

    // Remove old collider from collision world
    _remove_from_collision_world();
    _attached.reset();

    // Create new collider
    std::string failure_reason;
    bool source_pending = false;
    _collider = _create_collider(failure_reason, source_pending);
    if (!_collider) {
        _build_state = source_pending
            ? BuildState::PendingSource
            : BuildState::InvalidSource;
        if (report_failure) {
            _report_build_failure_once(failure_reason);
        }
        return;
    }

    _build_state = BuildState::Ready;
    ++_collider_revision;
    _last_reported_build_error.clear();

    if (detached) {
        return;
    }

    // MeshComponent-sourced convex hulls already follow the render mesh local data.
    // In that mode Collider Offset is intentionally ignored to avoid a second offset stack.
    if (collider_offset_enabled && !_uses_mesh_component_mesh()) {
        _collider->transform.lin = Vec3(
            collider_offset_position.x,
            collider_offset_position.y,
            collider_offset_position.z
        );

        constexpr double deg2rad = 3.14159265358979323846 / 180.0;
        Quat rx = Quat::from_axis_angle(Vec3(1,0,0), collider_offset_euler.x * deg2rad);
        Quat ry = Quat::from_axis_angle(Vec3(0,1,0), collider_offset_euler.y * deg2rad);
        Quat rz = Quat::from_axis_angle(Vec3(0,0,1), collider_offset_euler.z * deg2rad);
        _collider->transform.ang = rz * ry * rx;
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

void ColliderComponent::_report_build_failure_once(const std::string& message) {
    if (message.empty() || message == _last_reported_build_error) {
        return;
    }
    _last_reported_build_error = message;
    tc::Log::error("ColliderComponent: %s", message.c_str());
}

void ColliderComponent::set_collider_type(const std::string& type) {
    if (type != collider_type) {
        collider_type = type;
        _rebuild_collider(true);
    }
}

void ColliderComponent::set_box_size(const tc_vec3& size) {
    box_size = size;
    _rebuild_collider(true);
}

void ColliderComponent::set_convex_hull_mesh_source(const std::string& source) {
    if (source != convex_hull_mesh_source) {
        convex_hull_mesh_source = source;
        _rebuild_collider(true);
    }
}

void ColliderComponent::set_convex_hull_mesh(const TcMesh& mesh) {
    convex_hull_mesh = mesh;
    _rebuild_collider(true);
}

bool ColliderComponent::_uses_mesh_component_mesh() const {
    return collider_type == "ConvexHull" && convex_hull_mesh_source == "MeshComponent";
}

std::unique_ptr<colliders::ColliderPrimitive> ColliderComponent::_create_collider(
    std::string& failure_reason,
    bool& source_pending) const {
    failure_reason.clear();
    source_pending = false;

    if (collider_type == "Box") {
        // Box uses box_size as local size (entity scale applied via transform)
        Vec3 half_size{box_size.x / 2.0, box_size.y / 2.0, box_size.z / 2.0};
        return std::make_unique<colliders::BoxCollider>(half_size);
    }
    else if (collider_type == "Sphere") {
        // Sphere uses uniform component of size as diameter
        // radius = min(size.x, size.y, size.z) / 2
        double uniform_size = std::min({box_size.x, box_size.y, box_size.z});
        return std::make_unique<colliders::SphereCollider>(uniform_size / 2.0);
    }
    else if (collider_type == "Capsule") {
        // Capsule: height = size.z, radius = min(size.x, size.y) / 2
        double radius = std::min(box_size.x, box_size.y) / 2.0;
        double half_height = box_size.z / 2.0;
        return std::make_unique<colliders::CapsuleCollider>(half_height, radius);
    }
    else if (collider_type == "ConvexHull") {
        tc_mesh* m = nullptr;
        Mat44f mesh_offset = Mat44f::identity();
        bool from_mesh_component = false;

        if (convex_hull_mesh_source == "MeshComponent") {
            Entity ent = entity();
            if (!ent.valid()) {
                failure_reason = "ConvexHull MeshComponent source requires a valid entity";
                return nullptr;
            }

            MeshComponent* mesh_component = ent.get_component<MeshComponent>();
            if (!mesh_component) {
                failure_reason =
                    "ConvexHull MeshComponent source requires MeshComponent on the same entity";
                source_pending = true;
                return nullptr;
            }

            m = mesh_component->mesh.get();
            mesh_offset = mesh_component->get_mesh_offset_matrix();
            from_mesh_component = true;
        }
        else {
            m = convex_hull_mesh.get();
        }

        if (!m || !m->vertices || m->vertex_count == 0) {
            failure_reason = "ConvexHull requires source mesh with loaded vertex data";
            source_pending = true;
            return nullptr;
        }

        // Find "position" attribute in vertex layout
        const tc_vertex_attrib* pos_attrib = tc_vertex_layout_find(&m->layout, "position");
        if (!pos_attrib || pos_attrib->size < 3) {
            failure_reason = "ConvexHull mesh has no position attribute (or size < 3)";
            return nullptr;
        }

        // Extract position data from interleaved vertex buffer
        std::vector<Vec3> points;
        points.reserve(m->vertex_count);
        const char* raw = static_cast<const char*>(m->vertices);
        uint16_t stride = m->layout.stride;
        uint16_t offset = pos_attrib->offset;

        for (size_t i = 0; i < m->vertex_count; ++i) {
            const float* pos = reinterpret_cast<const float*>(raw + i * stride + offset);
            Vec3 point{pos[0], pos[1], pos[2]};
            if (from_mesh_component) {
                point = mesh_offset.transform_point(point);
            }
            else {
                point = Vec3(
                    point.x * box_size.x,
                    point.y * box_size.y,
                    point.z * box_size.z);
            }
            points.push_back(point);
        }

        return std::make_unique<colliders::ConvexHullCollider>(
            colliders::ConvexHullCollider::from_points(points));
    }
    else {
        tc::Log::warn("ColliderComponent: unknown collider type '%s', defaulting to Box", collider_type.c_str());
        return std::make_unique<colliders::BoxCollider>(Vec3{0.5, 0.5, 0.5});
    }
}

void ColliderComponent::_subscribe_to_scene_events() {
    _unsubscribe_from_scene_events();
    if (!tc_scene_alive(_scene_handle)) {
        return;
    }

    tc_event_bus* bus = tc_scene_event_bus(_scene_handle);
    if (!bus) {
        tc::Log::error("ColliderComponent: scene event bus is unavailable");
        return;
    }

    _mesh_changed_subscription = tc_event_bus_subscribe(
        bus,
        TC_EVENT_MESH_COMPONENT_CHANGED,
        &_mesh_component_changed_callback,
        this
    );
    if (!tc_event_subscription_valid(_mesh_changed_subscription)) {
        tc::Log::error("ColliderComponent: failed to subscribe to MeshComponent changes");
    }

    _structure_changed_subscription = tc_event_bus_subscribe(
        bus,
        TC_EVENT_SCENE_STRUCTURE_CHANGED,
        &_scene_structure_changed_callback,
        this
    );
    if (!tc_event_subscription_valid(_structure_changed_subscription)) {
        tc::Log::error("ColliderComponent: failed to subscribe to scene structure changes");
    }
}

void ColliderComponent::_unsubscribe_from_scene_events() {
    if (!tc_scene_alive(_scene_handle)) {
        _mesh_changed_subscription = {0};
        _structure_changed_subscription = {0};
        return;
    }

    tc_event_bus* bus = tc_scene_event_bus(_scene_handle);
    if (bus) {
        if (tc_event_subscription_valid(_mesh_changed_subscription)) {
            tc_event_bus_unsubscribe(bus, _mesh_changed_subscription);
        }
        if (tc_event_subscription_valid(_structure_changed_subscription)) {
            tc_event_bus_unsubscribe(bus, _structure_changed_subscription);
        }
    }
    _mesh_changed_subscription = {0};
    _structure_changed_subscription = {0};
}

void ColliderComponent::_mesh_component_changed_callback(
    const tc_event* event,
    void* user_data) {
    auto* self = static_cast<ColliderComponent*>(user_data);
    if (self) {
        self->_handle_mesh_component_changed(event);
    }
}

void ColliderComponent::_scene_structure_changed_callback(
    const tc_event* event,
    void* user_data) {
    auto* self = static_cast<ColliderComponent*>(user_data);
    if (self) {
        self->_handle_scene_structure_changed(event);
    }
}

void ColliderComponent::_handle_mesh_component_changed(const tc_event* event) {
    if (!_lifecycle_attached || !_uses_mesh_component_mesh() || !event ||
        event->payload_size != sizeof(MeshComponentChangedEvent)) {
        return;
    }

    const auto* payload = static_cast<const MeshComponentChangedEvent*>(event->payload);
    if (!payload || !tc_entity_handle_eq(payload->entity, _c.owner)) {
        return;
    }

    _rebuild_collider(started());
}

void ColliderComponent::_handle_scene_structure_changed(const tc_event* event) {
    if (!_lifecycle_attached || !_uses_mesh_component_mesh() || !event ||
        event->payload_size != sizeof(tc_scene_structure_changed_event)) {
        return;
    }

    const auto* payload = static_cast<const tc_scene_structure_changed_event*>(event->payload);
    if (!payload || payload->entity.index != _c.owner.id.index ||
        payload->entity.generation != _c.owner.id.generation ||
        !payload->component_type ||
        std::strcmp(payload->component_type, "MeshComponent") != 0) {
        return;
    }

    if (payload->kind == TC_SCENE_STRUCTURE_COMPONENT_ADDED ||
        payload->kind == TC_SCENE_STRUCTURE_COMPONENT_REMOVED) {
        _rebuild_collider(started());
    }
}

collision::CollisionWorld* ColliderComponent::_get_collision_world() const {
    if (!tc_scene_alive(_scene_handle)) {
        return nullptr;
    }
    void* cw = tc_collision_world_get_scene(_scene_handle);
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
