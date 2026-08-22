#include <cmath>
#include <limits>

#include <termin/render/world2d_quad_geometry.hpp>

#include "guard_main.h"

namespace {

    bool near(double lhs, double rhs) {
        return std::abs(lhs - rhs) < 1.0e-6;
    }

} // namespace

TEST_CASE("world2d quad bounds stay planar and use all transformed corners") {
    const termin::World2DQuadRect rect{-1.0, -2.0, 1.0, 2.0};
    const termin::Mat44 model = termin::Mat44::translation({3.0, 4.0, 5.0}) * termin::Mat44::scale({-2.0, 7.0, 0.5});

    const termin::AABB bounds = termin::world2d_quad_bounds(rect, model);
    CHECK(near(bounds.min_point.x, 1.0));
    CHECK(near(bounds.max_point.x, 5.0));
    CHECK(near(bounds.min_point.y, 4.0));
    CHECK(near(bounds.max_point.y, 4.0));
    CHECK(near(bounds.min_point.z, 4.0));
    CHECK(near(bounds.max_point.z, 6.0));
}

TEST_CASE("world2d quad bounds preserve affine shear") {
    const termin::World2DQuadRect rect{-1.0, -1.0, 1.0, 1.0};
    termin::Mat44 model = termin::Mat44::identity();
    model(2, 0) = 0.75;
    model(0, 1) = -0.5;
    model(3, 0) = 2.0;
    model(3, 1) = 3.0;
    model(3, 2) = 4.0;

    const termin::AABB bounds = termin::world2d_quad_bounds(rect, model);
    CHECK(near(bounds.min_point.x, 0.25));
    CHECK(near(bounds.max_point.x, 3.75));
    CHECK(near(bounds.min_point.y, 2.5));
    CHECK(near(bounds.max_point.y, 3.5));
    CHECK(near(bounds.min_point.z, 3.0));
    CHECK(near(bounds.max_point.z, 5.0));
}

TEST_CASE("world2d quad ray picking hits exact transformed surface") {
    const termin::World2DQuadRect rect{-1.0, -1.0, 1.0, 1.0};
    const termin::Mat44 model = termin::Mat44::translation({2.0, 3.0, 4.0});

    double ray_parameter = 0.0;
    const termin::Ray3 ray{{2.0, 0.0, 4.0}, {0.0, 1.0, 0.0}};
    REQUIRE(termin::ray_intersects_world2d_quad(ray, rect, model, &ray_parameter));
    CHECK(near(ray_parameter, 3.0));
    CHECK((ray.point_at(ray_parameter) - termin::Vec3{2.0, 3.0, 4.0}).norm() < 1.0e-6);

    CHECK_FALSE(termin::ray_intersects_world2d_quad({{4.0, 0.0, 4.0}, {0.0, 1.0, 0.0}}, rect, model));
}

TEST_CASE("world2d quad ray picking rejects parallel and zero rays") {
    const termin::World2DQuadRect rect{-1.0, -1.0, 1.0, 1.0};
    const termin::Mat44 model = termin::Mat44::identity();

    double ray_parameter = 17.0;
    CHECK_FALSE(termin::ray_intersects_world2d_quad({{0.0, 1.0, 0.0}, {1.0, 0.0, 0.0}}, rect, model, &ray_parameter));
    CHECK(near(ray_parameter, 17.0));
    CHECK_FALSE(termin::ray_intersects_world2d_quad({{0.0, 1.0, 0.0}, {0.0, 0.0, 0.0}}, rect, model, &ray_parameter));
    CHECK(near(ray_parameter, 17.0));
}

TEST_CASE("world2d quad ray picking preserves ray parameterization and accepts the origin") {
    const termin::World2DQuadRect rect{-1.0, -1.0, 1.0, 1.0};
    const termin::Mat44 model = termin::Mat44::translation({0.0, 3.0, 0.0});

    double ray_parameter = -1.0;
    termin::Ray3 non_unit_ray;
    non_unit_ray.origin = {0.0, 0.0, 0.0};
    non_unit_ray.direction = {0.0, 2.0, 0.0};
    REQUIRE(termin::ray_intersects_world2d_quad(non_unit_ray, rect, model, &ray_parameter));
    CHECK(near(ray_parameter, 1.5));
    CHECK((non_unit_ray.point_at(ray_parameter) - termin::Vec3{0.0, 3.0, 0.0}).norm() < 1.0e-6);

    const termin::Ray3 surface_ray{{0.0, 3.0, 0.0}, {0.0, 1.0, 0.0}};
    REQUIRE(termin::ray_intersects_world2d_quad(surface_ray, rect, model, &ray_parameter));
    CHECK(ray_parameter == 0.0);
}

TEST_CASE("world2d quad ray picking rejects backward and non-finite rays without changing output") {
    const termin::World2DQuadRect rect{-1.0, -1.0, 1.0, 1.0};
    const termin::Mat44 model = termin::Mat44::translation({0.0, 3.0, 0.0});
    constexpr double sentinel = 23.0;
    double ray_parameter = sentinel;

    CHECK_FALSE(termin::ray_intersects_world2d_quad({{0.0, 0.0, 0.0}, {0.0, -1.0, 0.0}}, rect, model, &ray_parameter));
    CHECK(near(ray_parameter, sentinel));

    const double nan = std::numeric_limits<double>::quiet_NaN();
    CHECK_FALSE(termin::ray_intersects_world2d_quad({{nan, 0.0, 0.0}, {0.0, 1.0, 0.0}}, rect, model, &ray_parameter));
    CHECK(near(ray_parameter, sentinel));
    CHECK_FALSE(termin::ray_intersects_world2d_quad({{0.0, 0.0, 0.0}, {0.0, nan, 0.0}}, rect, model, &ray_parameter));
    CHECK(near(ray_parameter, sentinel));
}

GUARD_TEST_MAIN();
