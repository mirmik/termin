#include "guard_main.h"
#include "termin/colliders/box_collider.hpp"
#include "termin/collision/collision_world.hpp"
#include "termin/collision/contact_patch.hpp"
#include "termin/geom/general_pose3.hpp"
#include <tcbase/tc_log.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <vector>

using guard::Approx;
using termin::GeneralPose3;
using termin::Quat;
using termin::Vec3;
using termin::colliders::BoxCollider;
using namespace termin::collision;

namespace {

    ContactCandidate candidate(double x, double y, double gap, uint32_t feature) {
        ContactCandidate result;
        result.point_on_a_world = {x, y, -gap};
        result.point_on_b_world = {x, y, 0.0};
        result.signed_gap = gap;
        result.features = {feature, feature + 100};
        return result;
    }

    std::vector<uint32_t> feature_ids(const std::vector<ContactCandidate>& candidates) {
        std::vector<uint32_t> result;
        for (const ContactCandidate& point : candidates) {
            result.push_back(point.features.feature_a);
        }
        return result;
    }

    void check_vec_near(const Vec3& actual, const Vec3& expected, double tolerance = 1e-10) {
        CHECK_EQ(actual.x, Approx(expected.x).epsilon(tolerance));
        CHECK_EQ(actual.y, Approx(expected.y).epsilon(tolerance));
        CHECK_EQ(actual.z, Approx(expected.z).epsilon(tolerance));
    }

    class InvalidNormalCollider final : public termin::colliders::Collider {
    public:
        explicit InvalidNormalCollider(const Vec3& normal)
            : normal_(normal) {}

        termin::colliders::ColliderType type() const override {
            return termin::colliders::ColliderType::Sphere;
        }

        termin::colliders::RayHit closest_to_ray(const termin::Ray3&) const override {
            return {};
        }

        termin::colliders::ColliderHit closest_to_collider(const termin::colliders::Collider&) const override {
            return {Vec3::zero(), Vec3::zero(), normal_, -1.0};
        }

        Vec3 center() const override {
            return Vec3::zero();
        }

        termin::AABB aabb() const override {
            return {Vec3{-1.0, -1.0, -1.0}, Vec3{1.0, 1.0, 1.0}};
        }

        termin::colliders::ColliderHit closest_to_box_impl(const BoxCollider&) const override {
            return {Vec3::zero(), Vec3::zero(), normal_, -1.0};
        }

        termin::colliders::ColliderHit closest_to_sphere_impl(
            const termin::colliders::SphereCollider&) const override {
            return {Vec3::zero(), Vec3::zero(), normal_, -1.0};
        }

        termin::colliders::ColliderHit closest_to_capsule_impl(
            const termin::colliders::CapsuleCollider&) const override {
            return {Vec3::zero(), Vec3::zero(), normal_, -1.0};
        }

    private:
        Vec3 normal_;
    };

} // namespace

TEST_CASE("Contact patch reducer preserves one point") {
    const std::array points{candidate(1.0, 2.0, -0.1, 7)};
    const auto reduced = reduce_contact_candidates(points, Vec3::unit_z());

    REQUIRE(reduced.has_value());
    CHECK_EQ(reduced->size(), 1u);
    CHECK_EQ((*reduced)[0].features.feature_a, 7u);
}

TEST_CASE("Contact patch reducer rejects zero and non-finite normals") {
    const std::array points{
        candidate(-1.0, -1.0, -0.1, 0),
        candidate(1.0, -1.0, -0.2, 1),
        candidate(1.0, 1.0, -0.3, 2),
        candidate(-1.0, 1.0, -0.4, 3),
        candidate(0.0, 0.0, -0.5, 4),
    };
    const double infinity = std::numeric_limits<double>::infinity();
    const double nan = std::numeric_limits<double>::quiet_NaN();

    CHECK_FALSE(reduce_contact_candidates(points, Vec3::zero()).has_value());
    CHECK_FALSE(reduce_contact_candidates(points, Vec3{infinity, 0.0, 0.0}).has_value());
    CHECK_FALSE(reduce_contact_candidates(points, Vec3{0.0, nan, 0.0}).has_value());
}

TEST_CASE("CollisionWorld reports and logs an invalid narrow-phase normal") {
    CollisionWorld world;
    world.set_broad_phase_mode(BroadPhaseMode::Naive);
    InvalidNormalCollider collider_a(Vec3::zero());
    InvalidNormalCollider collider_b(Vec3::zero());
    world.add(&collider_a);
    world.add(&collider_b);

    CHECK(tc_log_capture_start(4));
    const auto patches = world.detect_contacts();
    tc_log_record records[4]{};
    uint64_t dropped = 0;
    const std::size_t record_count = tc_log_capture_drain(records, 4, &dropped);
    tc_log_capture_stop();

    CHECK(patches.empty());
    REQUIRE_EQ(world.diagnostics().size(), 1u);
    CHECK(world.diagnostics()[0].code == CollisionDiagnosticCode::InvalidContactNormal);
    CHECK(world.diagnostics()[0].collider_a == &collider_a);
    CHECK(world.diagnostics()[0].collider_b == &collider_b);
    CHECK_EQ(record_count, 1u);
    CHECK_EQ(dropped, 0u);
    CHECK(records[0].level == TC_LOG_ERROR);
    CHECK(std::string(records[0].message).find("rejected contact pair with invalid normal") != std::string::npos);
}

TEST_CASE("Contact patch reducer is permutation invariant") {
    std::vector<ContactCandidate> points{
        candidate(-2.0, -1.0, -0.10, 0),
        candidate(2.0, -1.0, -0.20, 1),
        candidate(2.0, 1.0, -0.05, 2),
        candidate(-2.0, 1.0, -0.15, 3),
        candidate(0.0, 0.0, -0.30, 4),
        candidate(0.5, 0.2, -0.08, 5),
    };

    const auto forward = reduce_contact_candidates(points, Vec3::unit_z());
    std::reverse(points.begin(), points.end());
    const auto reverse = reduce_contact_candidates(points, Vec3::unit_z());

    REQUIRE(forward.has_value());
    REQUIRE(reverse.has_value());
    CHECK(feature_ids(*forward) == feature_ids(*reverse));
    CHECK_EQ(forward->front().features.feature_a, 4u);
}

TEST_CASE("Contact patch reducer handles line-like candidates") {
    std::vector<ContactCandidate> points;
    for (uint32_t i = 0; i < 7; ++i) {
        points.push_back(candidate(static_cast<double>(i), 1e-14 * i, -0.1, i));
    }

    const auto reduced = reduce_contact_candidates(points, Vec3::unit_z());

    REQUIRE(reduced.has_value());
    CHECK_EQ(reduced->size(), 4u);
    const auto ids = feature_ids(*reduced);
    CHECK(std::find(ids.begin(), ids.end(), 0u) != ids.end());
    CHECK(std::find(ids.begin(), ids.end(), 6u) != ids.end());
}

TEST_CASE("Contact patch reducer handles a near-degenerate patch") {
    std::vector<ContactCandidate> points{
        candidate(0.0, 0.0, -0.3, 0),
        candidate(2e-8, 0.0, -0.2, 1),
        candidate(4e-8, 1e-13, -0.1, 2),
        candidate(6e-8, -1e-13, -0.05, 3),
    };
    ContactPatchReductionConfig config;
    config.max_points = 3;

    const auto forward = reduce_contact_candidates(points, Vec3::unit_z(), config);
    std::reverse(points.begin(), points.end());
    const auto reverse = reduce_contact_candidates(points, Vec3::unit_z(), config);

    REQUIRE(forward.has_value());
    REQUIRE(reverse.has_value());
    CHECK_EQ(forward->size(), 3u);
    CHECK(feature_ids(*forward) == feature_ids(*reverse));
    CHECK_EQ(forward->front().features.feature_a, 0u);
}

TEST_CASE("Contact patch reducer removes duplicate candidates") {
    std::vector<ContactCandidate> points{
        candidate(0.0, 0.0, -0.2, 9),
        candidate(0.0, 0.0, -0.2, 3),
        candidate(1.0, 0.0, -0.1, 4),
    };

    ContactPatchReductionConfig config;
    config.max_points = 8;
    const auto reduced = reduce_contact_candidates(points, Vec3::unit_z(), config);

    REQUIRE(reduced.has_value());
    CHECK_EQ(reduced->size(), 2u);
    CHECK_EQ((*reduced)[0].features.feature_a, 3u);
}

TEST_CASE("Contact patch reducer covers a planar patch") {
    std::vector<ContactCandidate> points{
        candidate(-2.0, -2.0, -0.1, 0),
        candidate(2.0, -2.0, -0.1, 1),
        candidate(2.0, 2.0, -0.1, 2),
        candidate(-2.0, 2.0, -0.1, 3),
        candidate(0.0, 0.0, -0.3, 4),
        candidate(0.2, 0.1, -0.2, 5),
    };

    const auto reduced = reduce_contact_candidates(points, Vec3::unit_z());
    REQUIRE(reduced.has_value());
    const auto ids = feature_ids(*reduced);

    CHECK_EQ(reduced->size(), 4u);
    CHECK_EQ(reduced->front().features.feature_a, 4u);
    int corner_count = 0;
    for (uint32_t id = 0; id < 4; ++id) {
        corner_count += std::find(ids.begin(), ids.end(), id) != ids.end() ? 1 : 0;
    }
    CHECK(corner_count >= 3);
}

TEST_CASE("Contact patch reduction is rigid-transform invariant") {
    const Quat rotation = Quat::from_axis_angle(Vec3{1.0, 2.0, 3.0}.normalized(), 0.73);
    const Vec3 translation{4.0, -2.0, 7.0};
    std::vector<ContactCandidate> original{
        candidate(-2.0, -1.0, -0.10, 0),
        candidate(2.0, -1.0, -0.20, 1),
        candidate(2.0, 1.0, -0.05, 2),
        candidate(-2.0, 1.0, -0.15, 3),
        candidate(0.0, 0.0, -0.30, 4),
        candidate(0.5, 0.2, -0.08, 5),
    };

    std::vector<ContactCandidate> transformed = original;
    for (ContactCandidate& point : transformed) {
        point.point_on_a_world = rotation.rotate(point.point_on_a_world) + translation;
        point.point_on_b_world = rotation.rotate(point.point_on_b_world) + translation;
    }

    const auto reduced_original = reduce_contact_candidates(original, Vec3::unit_z());
    const auto reduced_transformed = reduce_contact_candidates(transformed, rotation.rotate(Vec3::unit_z()));

    REQUIRE(reduced_original.has_value());
    REQUIRE(reduced_transformed.has_value());
    CHECK(feature_ids(*reduced_original) == feature_ids(*reduced_transformed));
    for (std::size_t i = 0; i < reduced_original->size(); ++i) {
        check_vec_near((*reduced_transformed)[i].point_on_a_world,
                       rotation.rotate((*reduced_original)[i].point_on_a_world) + translation);
        check_vec_near((*reduced_transformed)[i].point_on_b_world,
                       rotation.rotate((*reduced_original)[i].point_on_b_world) + translation);
        CHECK_EQ((*reduced_transformed)[i].signed_gap,
                 Approx((*reduced_original)[i].signed_gap).epsilon(1e-12));
    }
}

TEST_CASE("CollisionWorld box-box contact uses a reduced geometric patch") {
    CollisionWorld world;
    BoxCollider box_a(Vec3{2.0, 2.0, 1.0});
    BoxCollider box_b(Vec3{2.0, 2.0, 1.0},
                      GeneralPose3(Quat::from_axis_angle(Vec3::unit_z(), 0.3), Vec3{0.2, 0.1, 1.5}));
    world.add(&box_a);
    world.add(&box_b);

    const auto patches = world.detect_contacts();

    CHECK_EQ(patches.size(), 1u);
    CHECK(!patches[0].points.empty());
    CHECK(patches[0].points.size() <= 4u);
    for (const ContactCandidate& point : patches[0].points) {
        const double geometric_gap = (point.point_on_b_world - point.point_on_a_world).dot(patches[0].normal_world);
        CHECK_EQ(point.signed_gap, Approx(geometric_gap).epsilon(1e-10));
    }
}
