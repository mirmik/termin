#include <cmath>
#include <cstdlib>
#include <iostream>

#include <termin/csg/csg.hpp>

namespace {

bool expect(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << "\n";
        return false;
    }
    return true;
}

bool near(double a, double b, double eps = 1e-6) {
    return std::abs(a - b) <= eps;
}

} // namespace

int main() {
    bool ok = true;

    termin::csg::Solid box = termin::csg::make_box(2.0, 3.0, 4.0);
    ok &= expect(!box.is_empty(), "box should not be empty");
    ok &= expect(box.triangle_count() == 12, "box should have 12 triangles");
    ok &= expect(near(box.volume(), 24.0), "box volume should be 24");

    termin::csg::Solid cut = termin::csg::make_box(1.0, 1.0, 6.0).translated(0.0, 0.0, 0.0);
    termin::csg::Solid difference = termin::csg::subtract(box, cut);
    ok &= expect(!difference.is_empty(), "difference should not be empty");
    ok &= expect(difference.triangle_count() > box.triangle_count(), "difference should add cut faces");

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
    ok &= expect(!extruded.is_empty(), "extruded contour should not be empty");
    ok &= expect(near(extruded.volume(), 30.0), "extruded contour volume should include hole");

    termin::Mesh3 mesh = termin::csg::to_mesh3(extruded, "extruded-test");
    ok &= expect(mesh.is_valid(), "converted Mesh3 should be valid");
    ok &= expect(mesh.has_normals(), "converted Mesh3 should have normals");

    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
