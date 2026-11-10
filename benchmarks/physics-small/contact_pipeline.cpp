#include "benchmark_common.hpp"

#include <termin/colliders/box_collider.hpp>
#include <termin/colliders/sphere_collider.hpp>
#include <termin/collision/collision_world.hpp>
#include <termin/physics_qopt/articulation3d_dynamics.hpp>
#include <termin/physics_qopt/contact3d.hpp>

#include <algorithm>
#include <cmath>
#include <iostream>
#include <memory>
#include <utility>

using namespace termin;
using namespace termin::physics_qopt;
using namespace termin::robotics;

namespace {
    constexpr double radius = 0.25;
    constexpr double initial_penetration = 1e-6;
    constexpr double gravity = 9.81;
    constexpr double friction = 0.5;
    constexpr double deceleration = friction * gravity / 2.0;

    std::vector<ArticulationUnit3D> slider_units() {
        // The horizontal carriage and vertical slider each weigh 1 kg.
        // Thus M = diag(2,1), with gravity loading only the vertical DOF.
        return {{.parent_unit = articulation_root_frame,
                 .motion_twist_at_unit = {Vec3::zero(), Vec3::unit_x()},
                 .inertia = SpatialInertia3{1.0, {0.1, 0.1, 0.1}, Pose3::identity()},
                 .diagnostic_name = "carriage"},
                {.parent_unit = 0,
                 .motion_twist_at_unit = {Vec3::zero(), Vec3::unit_y()},
                 .inertia = SpatialInertia3{1.0, {0.1, 0.1, 0.1}, Pose3::identity()},
                 .diagnostic_name = "slider"}};
    }

    struct ContactFixture {
        Articulation3D model{slider_units(), {{0.0, radius - initial_penetration}, {1.0, 0.0}}, "slider"};
        DynamicsSystem system;
        colliders::BoxCollider floor{{10.0, 0.5, 10.0}, {Quat::identity(), {0.0, -0.5, 0.0}, {1.0, 1.0, 1.0}}};
        colliders::SphereCollider sphere{radius};
        collision::CollisionWorld collision_world;
        Articulation3DDynamicsContribution* dynamics = nullptr;
        ContactSet3DContribution* contacts = nullptr;

        ContactFixture() {
            auto body = std::make_unique<Articulation3DDynamicsContribution>(model, Vec3{0, -gravity, 0});
            dynamics = body.get();
            require(system.add_contribution(std::move(body)) == DynamicsSystemDiagnostic::None,
                    "contact pipeline body registration failed");
            auto contact_set = std::make_unique<ContactSet3DContribution>("sphere-floor");
            contacts = contact_set.get();
            require(system.add_contribution(std::move(contact_set)) == DynamicsSystemDiagnostic::None,
                    "contact pipeline contact registration failed");
            require(system.finalize() == DynamicsSystemDiagnostic::None, "contact pipeline finalize failed");
            const Pose3& pose = model.unit_poses_world()[1];
            sphere.transform = {pose.ang, pose.lin, {1.0, 1.0, 1.0}};
            collision_world.add(&floor);
            collision_world.add(&sphere);
        }

        std::vector<collision::ContactPatch> query() {
            const Pose3& pose = model.unit_poses_world()[1];
            sphere.transform = {pose.ang, pose.lin, {1.0, 1.0, 1.0}};
            collision_world.update_pose(&sphere);
            auto patches = collision_world.detect_contacts();
            require(collision_world.diagnostics().empty(), "collision pipeline diagnostics");
            return patches;
        }

        void update_contacts(const std::vector<collision::ContactPatch>& patches) {
            std::vector<Contact3D> rows;
            for (const auto& patch : patches) {
                const bool floor_first = patch.collider_a == &floor && patch.collider_b == &sphere;
                require(floor_first || (patch.collider_a == &sphere && patch.collider_b == &floor),
                        "unexpected contact pair");
                require(patch.points.size() == 1, "sphere-floor must have one contact witness");
                const auto& point = patch.points.front();
                const Vec3 static_point = floor_first ? point.point_on_a_world : point.point_on_b_world;
                const Vec3 dynamic_point = floor_first ? point.point_on_b_world : point.point_on_a_world;
                rows.push_back({.key = 1,
                                .group_key = 1,
                                .endpoint_a = ContactEndpoint3D::static_world(static_point),
                                .endpoint_b = ContactEndpoint3D::articulation_unit(
                                    *dynamics, 1, model.unit_poses_world()[1].inverse_transform_point(dynamic_point)),
                                .normal_from_a_to_b_world = floor_first ? patch.normal_world : -patch.normal_world,
                                .signed_gap = point.signed_gap,
                                .friction_coefficient = friction});
            }
            // CollisionWorld emits penetrating pairs only. The live pair keeps
            // a supported contact at exact touching through the solver's cache.
            require(contacts->set_contacts(std::move(rows), {1}) == Contact3DDiagnostic::None,
                    "collision-to-contact update failed");
        }

        DynamicsSystemStepResult step() {
            const auto result = system.step({.time_step = dt,
                                             .position_tolerance = 1e-10,
                                             .velocity_tolerance = 1e-10,
                                             .max_position_iterations = 10});
            require(result.ok(), "full contact dynamics step failed");
            return result;
        }
    };

    void verify_final(const ContactFixture& fixture, int steps) {
        const double elapsed = steps * dt;
        const double sliding_time = std::min(elapsed, 1.0 / deceleration);
        const double expected_speed = std::max(0.0, 1.0 - deceleration * elapsed);
        const double expected_position = sliding_time - 0.5 * deceleration * sliding_time * sliding_time;
        const auto& state = fixture.model.state();
        require(std::abs(state.velocities[0] - expected_speed) < 2e-7, "contact speed oracle failed");
        // The last sliding-to-sticking step has a discrete midpoint stop.
        require(std::abs(state.coordinates[0] - expected_position) < 2 * deceleration * dt * dt,
                "contact displacement oracle failed");
        require(std::abs(state.coordinates[1] - radius) < 2e-8 && std::abs(state.velocities[1]) < 2e-8,
                "contact support oracle failed");
        require(fixture.contacts->states().size() == 1, "supported contact disappeared");
        require(fixture.contacts->states()[0].normal_impulse > 0.0, "supported contact has no normal impulse");
    }
} // namespace

void contact_pipeline(int steps, int warmups, int repeats) {
    std::vector<double> query_times, pipeline_times;
    std::vector<double> final_q, final_v;
    for (int trial = -warmups; trial < repeats; ++trial) {
        ContactFixture query_fixture;
        std::vector<collision::ContactPatch> patches;
        const double query_us = timed(steps, [&] { patches = query_fixture.query(); });
        require(patches.size() == 1 && patches[0].points.size() == 1 && patches[0].points[0].signed_gap < 0,
                "fixed penetrating collision query failed");

        ContactFixture fixture;
        const double pipeline_us = timed(steps, [&] {
            fixture.update_contacts(fixture.query());
            fixture.step();
        });
        verify_final(fixture, steps);
        if (trial >= 0) {
            query_times.push_back(query_us);
            pipeline_times.push_back(pipeline_us);
            if (trial == 0) {
                final_q = fixture.model.state().coordinates;
                final_v = fixture.model.state().velocities;
            } else {
                require(final_q == fixture.model.state().coordinates && final_v == fixture.model.state().velocities,
                        "non-deterministic contact pipeline trajectory");
            }
        }
    }

    // Separate profiling trial: throughput above has no per-stage clocks.
    ContactFixture profile;
    double query_us = 0, refresh_us = 0, dynamics_us = 0, work = 0;
    double previous_energy = profile.dynamics->total_energy();
    std::size_t query_hits = 0, sliding_steps = 0, position_iterations = 0, friction_iterations = 0, profile_step = 0;
    const double total_us = timed(steps, [&] {
        const auto query_start = Clock::now();
        auto patches = profile.query();
        query_us += std::chrono::duration<double, std::micro>(Clock::now() - query_start).count();
        query_hits += !patches.empty();
        const auto refresh_start = Clock::now();
        profile.update_contacts(patches);
        refresh_us += std::chrono::duration<double, std::micro>(Clock::now() - refresh_start).count();
        const auto dynamics_start = Clock::now();
        const auto result = profile.step();
        dynamics_us += std::chrono::duration<double, std::micro>(Clock::now() - dynamics_start).count();
        position_iterations += result.position_iterations;
        friction_iterations += result.friction_projection.iterations;
        require(profile.contacts->states().size() == 1, "contact profile lost support");
        const auto& contact = profile.contacts->states().front();
        sliding_steps += contact.sliding;
        work += contact.friction_work;
        require(contact.friction_work <= 1e-9, "friction increased energy");
        require(profile.model.state().coordinates[1] >= radius - 2e-8, "contact profile penetrated floor");
        const double energy = profile.dynamics->total_energy();
        // Initial position projection removes the 1e-6 penetration, increasing
        // potential energy by at most m*g*penetration before friction losses.
        const double projection_allowance = profile_step == 0 ? gravity * initial_penetration : 0.0;
        require(std::isfinite(energy) && energy <= previous_energy + projection_allowance + 1e-9,
                "contact energy grew unexpectedly");
        previous_energy = energy;
        ++profile_step;
    });
    verify_final(profile, steps);
    require(profile.model.state().coordinates == final_q && profile.model.state().velocities == final_v,
            "contact profiling changed trajectory");
    std::cout << "{\"case\":\"two_prismatic_slider_sphere_floor\",\"dof\":2,\"sphere_radius\":" << radius
              << ",\"friction_coefficient\":" << friction << ",\"initial_penetration\":" << initial_penetration
              << ",\"broad_phase\":\"BVH\",";
    timings_json("collision_query_fixed_penetration", query_times);
    std::cout << ',';
    timings_json("pipeline", pipeline_times);
    std::cout << ",\"final_q\":";
    vector_json(final_q);
    std::cout << ",\"final_v\":";
    vector_json(final_v);
    std::cout << ",\"instrumented_profile_us_per_step\":{\"total\":" << total_us
              << ",\"collision_query\":" << query_us / steps << ",\"contact_refresh\":" << refresh_us / steps
              << ",\"dynamics_step\":" << dynamics_us / steps << "},\"query_hit_steps\":" << query_hits
              << ",\"sliding_steps\":" << sliding_steps << ",\"position_iterations\":" << position_iterations
              << ",\"friction_iterations\":" << friction_iterations << ",\"friction_work_sum\":" << work << '}';
}
