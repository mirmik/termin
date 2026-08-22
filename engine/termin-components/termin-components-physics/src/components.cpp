#include <termin/physics_components/components.hpp>

#include <algorithm>
#include <cmath>
#include <string>

#include <components/collider_component.hpp>
#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/physics/mass_properties.hpp>
#include <termin/tc_scene.hpp>

namespace termin {
    namespace {

        constexpr const char* module_owner = "termin-components-physics";

        bool valid_scale(const Vec3& value) {
            return value.is_finite() && value.x > 0.0 && value.y > 0.0 && value.z > 0.0;
        }

        bool poses_near(const Pose3& lhs, const Pose3& rhs) {
            constexpr double translation_tolerance = 1.0e-8;
            constexpr double orientation_tolerance = 1.0e-10;
            Quat lhs_rotation;
            Quat rhs_rotation;
            if (!lhs.ang.try_normalized(lhs_rotation, 1.0e-12) || !rhs.ang.try_normalized(rhs_rotation, 1.0e-12)) {
                return false;
            }
            const double dot = lhs_rotation.dot(rhs_rotation);
            return (lhs.lin - rhs.lin).norm() <= translation_tolerance && 1.0 - std::abs(dot) <= orientation_tolerance;
        }

        template <typename Component>
        void stage_double(tc::InspectFacetBuilder& inspect,
                          double Component::* member,
                          const char* type_name,
                          const char* path,
                          const char* label,
                          double min,
                          double max,
                          double step) {
            tc::stage_inspect_field(inspect, member, type_name, path, label, "double", min, max, step);
        }

    } // namespace

    RigidBodyComponent::RigidBodyComponent()
        : CxxComponent("RigidBodyComponent") {}

    void RigidBodyComponent::register_type() {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<RigidBodyComponent>("RigidBodyComponent", module_owner, "Component");
        descriptor.category("Physics");
        auto& inspect = descriptor.inspect();
        stage_double(inspect, &RigidBodyComponent::mass, "RigidBodyComponent", "mass", "Mass", 0.001, 10000.0, 0.1);
        tc::stage_inspect_field(
            inspect, &RigidBodyComponent::is_static, "RigidBodyComponent", "is_static", "Static", "bool");
        stage_double(inspect,
                     &RigidBodyComponent::restitution,
                     "RigidBodyComponent",
                     "restitution",
                     "Restitution",
                     0.0,
                     1.0,
                     0.05);
        stage_double(
            inspect, &RigidBodyComponent::friction, "RigidBodyComponent", "friction", "Friction", 0.0, 2.0, 0.05);
        (void)descriptor.commit();
    }

    void RigidBodyComponent::start() {
        CxxComponent::start();
        if (world_component_ != nullptr || !entity().valid()) {
            return;
        }
        const TcSceneRef scene = entity().scene();
        if (!scene.valid()) {
            tc::Log::error("[RigidBodyComponent] owner scene is invalid");
            return;
        }
        for (Entity candidate : scene.get_all_entities()) {
            auto* world = candidate.get_component<PhysicsWorldComponent>();
            if (world != nullptr && world->enabled()) {
                (void)world->add_rigid_body_component(*this);
                return;
            }
        }
        tc::Log::error("[RigidBodyComponent] no enabled PhysicsWorldComponent in scene for '%s'", entity().name());
    }

    void RigidBodyComponent::on_destroy() {
        if (world_component_ != nullptr) {
            world_component_->remove_rigid_body_component(*this);
        }
        clear_runtime_link();
        CxxComponent::on_destroy();
    }

    bool RigidBodyComponent::initialized() const noexcept {
        return world_component_ != nullptr && body_index_ != invalid_body_index;
    }

    std::size_t RigidBodyComponent::body_index() const noexcept {
        return body_index_;
    }

    physics::RigidBody* RigidBodyComponent::rigid_body() noexcept {
        if (!initialized()) {
            return nullptr;
        }
        return &world_component_->physics_world().get_body(body_index_);
    }

    const physics::RigidBody* RigidBodyComponent::rigid_body() const noexcept {
        if (!initialized()) {
            return nullptr;
        }
        return &world_component_->physics_world().get_body(body_index_);
    }

    bool RigidBodyComponent::physics_pose_and_scale(Pose3& pose, Vec3& scale, bool report_error) const {
        const Entity owner = entity();
        if (!owner.valid()) {
            if (report_error) {
                tc::Log::error("[RigidBodyComponent] owner entity is invalid");
            }
            return false;
        }
        const auto maybe_scale = owner.transform().decomposed_global_scale();
        if (!maybe_scale.has_value()) {
            if (report_error) {
                tc::Log::error("[RigidBodyComponent] '%s' rejects an affine world transform; rigid physics requires a "
                               "decomposed world basis",
                               owner.name());
            }
            return false;
        }
        if (!valid_scale(*maybe_scale)) {
            if (report_error) {
                tc::Log::error("[RigidBodyComponent] '%s' rejects non-positive or non-finite world scale (%g, %g, %g)",
                               owner.name(),
                               maybe_scale->x,
                               maybe_scale->y,
                               maybe_scale->z);
            }
            return false;
        }
        Pose3 normalized_pose = owner.transform().global_pose();
        Quat normalized_rotation;
        if (!normalized_pose.ang.try_normalized(normalized_rotation, 1.0e-12)) {
            if (report_error) {
                tc::Log::error("[RigidBodyComponent] '%s' rejects a zero or non-finite world rotation", owner.name());
            }
            return false;
        }
        if (!normalized_pose.lin.is_finite()) {
            if (report_error) {
                tc::Log::error("[RigidBodyComponent] '%s' rejects a non-finite world position", owner.name());
            }
            return false;
        }
        normalized_pose.ang = normalized_rotation;

        pose = normalized_pose;
        scale = *maybe_scale;
        return true;
    }

    bool RigidBodyComponent::make_body(physics::RigidBody& body) {
        Pose3 pose;
        Vec3 scale;
        if (!physics_pose_and_scale(pose, scale, true)) {
            return false;
        }
        if (!std::isfinite(mass) || mass <= 0.0) {
            tc::Log::error("[RigidBodyComponent] '%s' rejects invalid mass=%g", entity().name(), mass);
            return false;
        }

        collider_component_ = entity().get_component<ColliderComponent>();
        if (collider_component_ == nullptr) {
            body = physics::RigidBody::create_box(scale, mass, pose, is_static);
            return true;
        }
        const colliders::ColliderPrimitive* primitive = collider_component_->collider();
        if (primitive == nullptr) {
            tc::Log::error(
                "[RigidBodyComponent] '%s' cannot compute mass properties because collider geometry is unavailable",
                entity().name());
            return false;
        }
        SpatialInertia3 properties;
        std::string diagnostic;
        if (!physics::try_compute_mass_properties(*primitive, scale, mass, properties, diagnostic)) {
            tc::Log::error("[RigidBodyComponent] '%s' rejected %s mass properties: %s",
                           entity().name(),
                           collider_component_->collider_type.c_str(),
                           diagnostic.c_str());
            return false;
        }
        body = physics::RigidBody::create_with_mass_properties(properties, pose, is_static);
        return true;
    }

    bool RigidBodyComponent::ensure_collider_registered() {
        if (!initialized()) {
            return false;
        }
        ColliderComponent* current = entity().get_component<ColliderComponent>();
        colliders::Collider* attached = current != nullptr ? current->attached_collider() : nullptr;
        const std::uint64_t revision = current != nullptr ? current->collider_revision() : 0;
        if (current == collider_component_ && attached == registered_collider_ &&
            revision == registered_collider_revision_) {
            return attached != nullptr;
        }

        physics::PhysicsWorld& world = world_component_->physics_world();
        world.unregister_collider(body_index_);
        collider_component_ = current;
        registered_collider_ = attached;
        registered_collider_revision_ = revision;
        if (attached == nullptr) {
            return false;
        }
        world.register_collider(body_index_, attached);
        return true;
    }

    void RigidBodyComponent::reconcile_external_transform() {
        if (!initialized() || is_static) {
            return;
        }
        Pose3 entity_pose;
        Vec3 scale;
        if (!physics_pose_and_scale(entity_pose, scale, true)) {
            return;
        }
        if (has_last_synced_entity_pose_ && !poses_near(entity_pose, last_synced_entity_pose_)) {
            physics::RigidBody& body = world_component_->physics_world().get_body(body_index_);
            body.set_shape_pose(entity_pose);
            body.linear_velocity = Vec3{};
            body.angular_velocity = Vec3{};
            last_synced_entity_pose_ = entity_pose;
        }
    }

    void RigidBodyComponent::sync_from_physics() {
        if (!initialized() || !entity().valid()) {
            return;
        }
        const Pose3 pose = world_component_->physics_world().get_body(body_index_).shape_pose();
        entity().transform().set_global_pose(pose);
        last_synced_entity_pose_ = pose;
        has_last_synced_entity_pose_ = true;
    }

    bool RigidBodyComponent::sync_to_physics() {
        if (!initialized()) {
            return false;
        }
        Pose3 pose;
        Vec3 scale;
        if (!physics_pose_and_scale(pose, scale, true)) {
            return false;
        }
        physics::RigidBody& body = world_component_->physics_world().get_body(body_index_);
        body.set_shape_pose(pose);
        body.linear_velocity = Vec3{};
        body.angular_velocity = Vec3{};
        last_synced_entity_pose_ = pose;
        has_last_synced_entity_pose_ = true;
        return true;
    }

    void RigidBodyComponent::apply_impulse(const Vec3& impulse) {
        if (physics::RigidBody* body = rigid_body(); body != nullptr) {
            body->apply_impulse(impulse);
        }
    }

    void RigidBodyComponent::apply_impulse_at_point(const Vec3& impulse, const Vec3& point) {
        if (physics::RigidBody* body = rigid_body(); body != nullptr) {
            body->apply_impulse_at_point(impulse, point);
        }
    }

    void RigidBodyComponent::clear_runtime_link() {
        world_component_ = nullptr;
        body_index_ = invalid_body_index;
        collider_component_ = nullptr;
        registered_collider_ = nullptr;
        registered_collider_revision_ = 0;
        has_last_synced_entity_pose_ = false;
    }

    PhysicsWorldComponent::PhysicsWorldComponent()
        : CxxComponent("PhysicsWorldComponent") {
        set_has_fixed_update(true);
        (void)set_fixed_update_priority(fixed_update_priority::physics);
    }

    void PhysicsWorldComponent::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<PhysicsWorldComponent>(
            "PhysicsWorldComponent", module_owner, "Component");
        descriptor.category("Physics");
        auto& inspect = descriptor.inspect();
        tc::stage_inspect_field(
            inspect, &PhysicsWorldComponent::gravity, "PhysicsWorldComponent", "gravity", "Gravity", "vec3");
        tc::stage_inspect_field(inspect,
                                &PhysicsWorldComponent::iterations,
                                "PhysicsWorldComponent",
                                "iterations",
                                "Iterations",
                                "int",
                                1,
                                100,
                                1);
        stage_double(inspect,
                     &PhysicsWorldComponent::restitution,
                     "PhysicsWorldComponent",
                     "restitution",
                     "Restitution",
                     0.0,
                     1.0,
                     0.05);
        stage_double(
            inspect, &PhysicsWorldComponent::friction, "PhysicsWorldComponent", "friction", "Friction", 0.0, 2.0, 0.05);
        (void)descriptor.commit();
    }

    void PhysicsWorldComponent::start() {
        CxxComponent::start();
        initialized_ = rebuild();
        if (!initialized_) {
            tc::Log::error("[PhysicsWorldComponent] failed to initialize native game physics world");
        }
    }

    void PhysicsWorldComponent::fixed_update(float dt) {
        if (!initialized_ || !enabled()) {
            return;
        }
        if (!std::isfinite(dt) || dt <= 0.0F) {
            tc::Log::error("[PhysicsWorldComponent] received invalid fixed dt=%g", static_cast<double>(dt));
            return;
        }
        world_.gravity = Vec3{gravity.x, gravity.y, gravity.z};
        world_.solver_iterations = std::max(iterations, 1);
        world_.restitution = std::clamp(restitution, 0.0, 1.0);
        world_.friction = std::max(friction, 0.0);
        for (RigidBodyComponent* body : bodies_) {
            if (body != nullptr && body->enabled()) {
                (void)body->ensure_collider_registered();
                body->reconcile_external_transform();
            }
        }
        world_.step(static_cast<double>(dt));
        for (RigidBodyComponent* body : bodies_) {
            if (body != nullptr && body->enabled()) {
                body->sync_from_physics();
            }
        }
    }

    void PhysicsWorldComponent::on_destroy() {
        initialized_ = false;
        clear_runtime_links();
        world_.clear();
        world_.set_collision_world(nullptr);
        CxxComponent::on_destroy();
    }

    bool PhysicsWorldComponent::rebuild() {
        clear_runtime_links();
        world_.clear();
        const Entity owner = entity();
        if (!owner.valid() || !owner.scene().valid()) {
            tc::Log::error("[PhysicsWorldComponent] owner scene is invalid");
            return false;
        }
        collision::CollisionWorld* collision_world = collision::CollisionWorld::from_scene(owner.scene().handle());
        if (collision_world == nullptr) {
            tc::Log::error("[PhysicsWorldComponent] scene has no CollisionWorld extension");
            return false;
        }
        world_.set_collision_world(collision_world);
        world_.gravity = Vec3{gravity.x, gravity.y, gravity.z};
        world_.solver_iterations = std::max(iterations, 1);
        world_.restitution = std::clamp(restitution, 0.0, 1.0);
        world_.friction = std::max(friction, 0.0);

        bool success = true;
        for (Entity candidate : owner.scene().get_all_entities()) {
            auto* body = candidate.get_component<RigidBodyComponent>();
            if (body != nullptr && body->enabled()) {
                success = register_body(*body) && success;
            }
        }
        return success;
    }

    bool PhysicsWorldComponent::register_body(RigidBodyComponent& component) {
        if (component.world_component_ != nullptr) {
            if (component.world_component_ == this) {
                return true;
            }
            tc::Log::error("[PhysicsWorldComponent] body '%s' belongs to another physics world",
                           component.entity().name());
            return false;
        }
        physics::RigidBody body;
        if (!component.make_body(body)) {
            return false;
        }
        component.world_component_ = this;
        component.body_index_ = world_.add_body(body);
        bodies_.push_back(&component);
        Pose3 pose;
        Vec3 scale;
        if (component.physics_pose_and_scale(pose, scale, false)) {
            component.last_synced_entity_pose_ = pose;
            component.has_last_synced_entity_pose_ = true;
        }
        (void)component.ensure_collider_registered();
        return true;
    }

    bool PhysicsWorldComponent::add_rigid_body_component(RigidBodyComponent& component) {
        if (!initialized_) {
            return false;
        }
        return register_body(component);
    }

    void PhysicsWorldComponent::remove_rigid_body_component(RigidBodyComponent& component) {
        const auto found = std::find(bodies_.begin(), bodies_.end(), &component);
        if (found == bodies_.end()) {
            component.clear_runtime_link();
            return;
        }
        // PhysicsWorld body indices are intentionally compact and externally
        // observable. Rebuild the known survivors to keep every component index
        // coherent instead of leaving tombstones or dangling collider mappings.
        std::vector<RigidBodyComponent*> survivors;
        survivors.reserve(bodies_.size() - 1);
        for (RigidBodyComponent* body : bodies_) {
            if (body != nullptr && body != &component) {
                survivors.push_back(body);
            }
        }
        clear_runtime_links();
        world_.clear();
        bool success = true;
        for (RigidBodyComponent* body : survivors) {
            success = register_body(*body) && success;
        }
        initialized_ = success;
    }

    void PhysicsWorldComponent::clear_runtime_links() {
        for (RigidBodyComponent* body : bodies_) {
            if (body != nullptr && body->world_component_ == this) {
                body->clear_runtime_link();
            }
        }
        bodies_.clear();
    }

} // namespace termin
