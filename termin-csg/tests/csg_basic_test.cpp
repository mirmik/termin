#include <cmath>

#include "guard_main.h"

#include <termin/csg/csg.hpp>

namespace {

bool near(double a, double b, double eps = 1e-6) {
    return std::abs(a - b) <= eps;
}

} // namespace

TEST_CASE("termin-csg basic primitives and conversions") {
    termin::csg::Solid box = termin::csg::make_box(2.0, 3.0, 4.0);
    CHECK_FALSE(box.is_empty());
    CHECK_EQ(box.triangle_count(), 12u);
    CHECK(near(box.volume(), 24.0));

    termin::csg::Solid sphere = termin::csg::make_sphere(1.0, 16);
    CHECK_FALSE(sphere.is_empty());
    CHECK_GT(sphere.triangle_count(), box.triangle_count());

    termin::csg::Solid cut = termin::csg::make_box(1.0, 1.0, 6.0).translated(0.0, 0.0, 0.0);
    termin::csg::Solid difference = termin::csg::subtract(box, cut);
    CHECK_FALSE(difference.is_empty());
    CHECK_GT(difference.triangle_count(), box.triangle_count());

    termin::csg::Polygon2 outer = {
        {-2.0, -2.0},
        { 2.0, -2.0},
        { 2.0,  2.0},
        {-2.0,  2.0},
    };
    termin::csg::Polygon2 hole = {
        {-0.5, -0.5},
        { 0.5, -0.5},
        { 0.5,  0.5},
        {-0.5,  0.5},
    };
    termin::csg::Solid extruded = termin::csg::extrude(outer, {hole}, 2.0);
    CHECK_FALSE(extruded.is_empty());
    CHECK(near(extruded.volume(), 30.0));

    termin::Mesh3 mesh = termin::csg::to_mesh3(extruded, "extruded-test");
    CHECK(mesh.is_valid());
    CHECK(mesh.has_normals());
}

GUARD_TEST_MAIN();
