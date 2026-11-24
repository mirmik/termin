#include "web_active_scene.hpp"

#include <algorithm>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <string>

#include <emscripten/emscripten.h>
#include <tcbase/tc_log.hpp>
#include <termin/physics_components/components.hpp>

namespace {
    using namespace termin;
    using physics::RigidBody;

    constexpr double cable_length = 0.69;
    constexpr double mission_seconds = 60.0;
    enum class Phase {
        Active = 1,
        Delivered = 2,
        Timeout = 3
    };

    Entity scene_entity(const char* uuid) {
        auto* pool = tc_scene_entity_pool(web::active_scene());
        const auto id = pool ? tc_entity_pool_find_by_uuid(pool, uuid) : TC_ENTITY_ID_INVALID;
        if (!tc_entity_id_valid(id))
            throw std::runtime_error(std::string("missing salvage scene entity: ") + uuid);
        return Entity(pool, id);
    }

    template <typename T> T& required_component(Entity owner) {
        auto* component = owner.get_component<T>();
        if (!component)
            throw std::runtime_error(std::string("missing physics component on ") + owner.name());
        return *component;
    }

    RigidBody& require_body(RigidBodyComponent& component) {
        auto* body = component.rigid_body();
        if (!body)
            throw std::runtime_error("salvage scene physics has not started");
        return *body;
    }

    Vec3 winch(const RigidBody& sub) {
        return sub.shape_pose().transform_point({0, 0, -.32});
    }

    Vec3 eyelet(const RigidBody& cargo) {
        return cargo.shape_pose().transform_point({0, 0, .21});
    }

    Vec3 free_hook(const RigidBody& sub) {
        return winch(sub) + Vec3{0, 0, -cable_length};
    }

    bool within_reach(const RigidBody& sub, const RigidBody& cargo) {
        return (free_hook(sub) - eyelet(cargo)).norm() <= .30;
    }

    // This compartment is played in a vertical slice. Keep the two dynamic
    // bodies on that plane while leaving pitch, in-plane inertia and contacts
    // to the rigid-body solver.
    void constrain_to_plane(RigidBody& body) {
        body.pose.lin.y = 0;
        body.linear_velocity.y = 0;
        body.angular_velocity.x = 0;
        body.angular_velocity.z = 0;
        body.pose.ang = Quat(0, body.pose.ang.y, 0, body.pose.ang.w).normalized();
    }

    class SalvageMission final : public CxxComponent {
    public:
        SalvageMission(Entity sub, Entity cargo, Entity pad, Entity cable, Entity world)
            : CxxComponent("SalvageMission"),
              sub_(required_component<RigidBodyComponent>(sub)),
              cargo_(required_component<RigidBodyComponent>(cargo)),
              pad_(required_component<RigidBodyComponent>(pad)),
              cable_(cable),
              world_(required_component<PhysicsWorldComponent>(world)) {
            set_has_fixed_update(true);
            set_fixed_update_priority(fixed_update_priority::control);
            set_has_late_update(true);
        }

        void restart() {
            if (!sub_.reset_to_initial_pose() || !cargo_.reset_to_initial_pose() || !pad_.initialized())
                throw std::runtime_error("could not reset the salvage physics bodies");
            world_.set_enabled(true);
            phase_ = Phase::Active;
            thrust_ = {};
            attached_ = false;
            ever_attached_ = false;
            tension_ = 0;
            remaining_ = mission_seconds;
            landed_time_ = 0;
            // Drag in water leaves enough lateral inertia for the recorder to swing.
            require_body(sub_).linear_damping = 2.2;
            require_body(sub_).angular_damping = 4.0;
            require_body(cargo_).linear_damping = .85;
            require_body(cargo_).angular_damping = 2.2;
            late_update(0);
        }

        void control(double x, double z, bool hook) {
            if (!std::isfinite(x) || !std::isfinite(z))
                throw std::invalid_argument("non-finite salvage thrust");
            if (phase_ != Phase::Active)
                return;
            thrust_ = Vec3{std::clamp(x, -1.0, 1.0), 0, std::clamp(z, -1.0, 1.0)};
            thrust_ = thrust_ / std::max(thrust_.norm(), 1.0);
            if (hook && (attached_ || within_reach(require_body(sub_), require_body(cargo_)))) {
                attached_ = !attached_;
                ever_attached_ = true;
                tension_ = 0;
            }
        }

        void fixed_update(float dt) override {
            if (phase_ != Phase::Active)
                return;
            auto& sub = require_body(sub_);
            auto& cargo = require_body(cargo_);
            constrain_to_plane(sub);
            constrain_to_plane(cargo);

            landed_time_ = is_on_pad(cargo) ? landed_time_ + dt : 0.0;
            remaining_ = std::max(0.0, remaining_ - dt);
            if (landed_time_ >= .25 || remaining_ <= 0) {
                phase_ = landed_time_ >= .25 ? Phase::Delivered : Phase::Timeout;
                world_.set_enabled(false);
                return;
            }

            // Automatic ballast trims for the recovered payload. Thrusters
            // accelerate the vehicle; releasing the controls lets drag brake it.
            const double supported_mass = sub.mass + (attached_ ? cargo.mass : 0.0);
            sub.add_force(thrust_ * (sub.mass * 5.6) - world_.gravity * supported_mass);
            const Vec3 up = sub.pose.ang.rotate({0, 0, 1});
            const double pitch = std::atan2(up.x, up.z);
            sub.add_torque({0, -2.8 * pitch - .55 * sub.angular_velocity.y, 0});
            if (attached_)
                pull_cable(sub, cargo);
        }

        void late_update(float) override {
            const auto& sub = require_body(sub_);
            const Vec3 top = winch(sub);
            const Vec3 bottom = attached_ ? eyelet(require_body(cargo_)) : free_hook(sub);
            const Vec3 axis = top - bottom;
            const auto rotation = Quat::from_axis_angle({0, 1, 0}, std::atan2(axis.x, axis.z));
            cable_.transform().set_local_pose(
                {rotation, (top + bottom) * .5, {.038, .038, std::max(.001, axis.norm())}});
        }

        void read(double* out) const {
            if (!out)
                throw std::invalid_argument("missing salvage telemetry buffer");
            const auto& sub = require_body(sub_);
            const auto& cargo = require_body(cargo_);
            out[0] = static_cast<int>(phase_);
            out[1] = remaining_;
            out[2] = attached_;
            out[3] = !attached_ && within_reach(sub, cargo);
            out[4] = sub.position().x;
            out[5] = sub.position().z;
            out[6] = cargo.position().x;
            out[7] = cargo.position().z;
            out[8] = tension_;
        }

    private:
        bool is_on_pad(const RigidBody& cargo) const {
            if (attached_ || !ever_attached_ || cargo.linear_velocity.norm() > .60)
                return false;
            const auto& pad = require_body(pad_);
            // Only an upward support contact counts. Brushing the platform's
            // side while resting on the floor must not complete the dive.
            for (const auto& contact : world_.physics_world().contacts()) {
                if ((contact.body_a == &cargo && contact.body_b == &pad && contact.normal.z < -.7) ||
                    (contact.body_a == &pad && contact.body_b == &cargo && contact.normal.z > .7))
                    return true;
            }
            return false;
        }

        void pull_cable(RigidBody& sub, RigidBody& cargo) {
            const Vec3 a = winch(sub);
            const Vec3 b = eyelet(cargo);
            const Vec3 separation = b - a;
            const double length = separation.norm();
            tension_ = 0;
            if (length <= cable_length)
                return;
            const Vec3 direction = separation / length;
            const double speed = (cargo.point_velocity(b) - sub.point_velocity(a)).dot(direction);
            tension_ = std::max(0.0, 85.0 * (length - cable_length) + 8.0 * speed);
            sub.add_force_at_point(direction * tension_, a);
            cargo.add_force_at_point(direction * -tension_, b);
        }

        RigidBodyComponent& sub_;
        RigidBodyComponent& cargo_;
        RigidBodyComponent& pad_;
        Entity cable_;
        PhysicsWorldComponent& world_;
        Phase phase_ = Phase::Active;
        Vec3 thrust_;
        bool attached_ = false;
        bool ever_attached_ = false;
        double tension_ = 0;
        double remaining_ = mission_seconds;
        double landed_time_ = 0;
    };

    SalvageMission& active_mission() {
        auto entity = scene_entity("salvage-sub");
        auto* mission = entity.get_component<SalvageMission>();
        if (!mission)
            throw std::runtime_error("the salvage mission has not started");
        return *mission;
    }

    std::string last_error;
    template <typename F> int run_command(const char* operation, F command) {
        try {
            command();
            return 1;
        } catch (const std::exception& error) {
            last_error = error.what();
            tc_log_error("[Salvage] %s failed: %s", operation, last_error.c_str());
            return 0;
        }
    }
} // namespace

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_salvage_start() {
    return run_command("start", [] {
        Entity sub = scene_entity("salvage-sub");
        if (auto* mission = sub.get_component<SalvageMission>()) {
            mission->restart();
            return;
        }
        auto mission = std::make_unique<SalvageMission>(sub,
                                                        scene_entity("salvage-cargo"),
                                                        scene_entity("salvage-pad"),
                                                        scene_entity("salvage-cable"),
                                                        scene_entity("salvage-world"));
        mission->restart();
        if (!sub.add_component_ptr_checked(mission->c_component()))
            throw std::runtime_error("could not attach salvage mission to submersible");
        mission.release(); // The scene owns the component.
    });
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_salvage_control(double x, double z, int hook) {
    return run_command("control", [&] { active_mission().control(x, z, hook != 0); });
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_salvage_read(double* output) {
    return run_command("read", [&] { active_mission().read(output); });
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_salvage_error() {
    return last_error.c_str();
}
