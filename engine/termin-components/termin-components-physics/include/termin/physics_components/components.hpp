#pragma once

#include <cstddef>
#include <limits>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/geom/pose3.hpp>
#include <termin/physics/physics_world.hpp>

namespace termin {

    class ColliderComponent;
    class PhysicsWorldComponent;

    class ENTITY_API RigidBodyComponent final : public CxxComponent {
    public:
        double mass = 1.0;
        bool is_static = false;
        // Kept as authored component data for scene/API compatibility. Contact
        // coefficients are currently configured on PhysicsWorldComponent.
        double restitution = 0.3;
        double friction = 0.5;

        RigidBodyComponent();
        ~RigidBodyComponent() override = default;

        static void register_type();
        void start() override;
        void on_destroy() override;

        [[nodiscard]] bool initialized() const noexcept;
        [[nodiscard]] std::size_t body_index() const noexcept;
        [[nodiscard]] physics::RigidBody* rigid_body() noexcept;
        [[nodiscard]] const physics::RigidBody* rigid_body() const noexcept;

        bool sync_to_physics();
        void apply_impulse(const Vec3& impulse);
        void apply_impulse_at_point(const Vec3& impulse, const Vec3& point);

    private:
        friend class PhysicsWorldComponent;

        static constexpr std::size_t invalid_body_index = std::numeric_limits<std::size_t>::max();

        PhysicsWorldComponent* world_component_ = nullptr;
        std::size_t body_index_ = invalid_body_index;
        ColliderComponent* collider_component_ = nullptr;
        colliders::Collider* registered_collider_ = nullptr;
        std::uint64_t registered_collider_revision_ = 0;
        Pose3 last_synced_entity_pose_{};
        bool has_last_synced_entity_pose_ = false;

        [[nodiscard]] bool physics_pose_and_scale(Pose3& pose, Vec3& scale, bool report_error) const;
        [[nodiscard]] bool make_body(physics::RigidBody& body);
        [[nodiscard]] bool ensure_collider_registered();
        void reconcile_external_transform();
        void sync_from_physics();
        void clear_runtime_link();
    };

    class ENTITY_API PhysicsWorldComponent final : public CxxComponent {
    public:
        tc_vec3 gravity{0.0, 0.0, -9.81};
        int iterations = 10;
        double restitution = 0.3;
        double friction = 0.5;

        PhysicsWorldComponent();
        ~PhysicsWorldComponent() override = default;

        static void register_type();
        void start() override;
        void fixed_update(float dt) override;
        void on_destroy() override;

        [[nodiscard]] bool initialized() const noexcept {
            return initialized_;
        }
        [[nodiscard]] physics::PhysicsWorld& physics_world() noexcept {
            return world_;
        }
        [[nodiscard]] const physics::PhysicsWorld& physics_world() const noexcept {
            return world_;
        }

        bool add_rigid_body_component(RigidBodyComponent& component);
        void remove_rigid_body_component(RigidBodyComponent& component);

    private:
        physics::PhysicsWorld world_;
        std::vector<RigidBodyComponent*> bodies_;
        bool initialized_ = false;

        bool rebuild();
        bool register_body(RigidBodyComponent& component);
        void clear_runtime_links();
    };

} // namespace termin
