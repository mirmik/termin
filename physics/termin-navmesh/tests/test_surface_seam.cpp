#include <termin/navmesh/surface_navigation.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>

using namespace termin;
namespace {
    void require(bool condition, const char* message) {
        if (!condition) {
            std::fprintf(stderr, "%s\n", message);
            std::abort();
        }
    }
    void near(const Vec3& actual, const Vec3& expected, const char* message) {
        require((actual - expected).norm() < 1e-8, message);
    }
    SurfaceSeamInput coplanar() {
        SurfaceSeamInput input;
        input.a0 = {0, 0, 0};
        input.a1 = {4, 0, 0};
        input.b0 = {1, 0.6, 0};
        input.b1 = {3, 0.6, 0};
        input.normal_a = input.normal_b = {0, 0, 1};
        input.interior_a = {2, -1, 0};
        input.interior_b = {2, 1.6, 0};
        return input;
    }
    void rejected(const SurfaceSeamInput& input, const char* message) {
        const auto result = extend_surface_seam(input);
        require(!result.success && !result.error.empty(), message);
    }
    Vec3 rotate(const Vec3& p) {
        // Orthogonal transform without privileging the bake up axis.
        const double c = std::cos(0.73), s = std::sin(0.73);
        return {c * p.x - s * p.z, p.y, s * p.x + c * p.z};
    }
    Vec3 transform(const Vec3& p) {
        return rotate(p) + Vec3{173, -29, 53};
    }
} // namespace

int main() {
    auto input = coplanar();
    auto result = extend_surface_seam(input);
    require(result.success, "parallel coplanar boundaries must join at their midline");
    Vec3 first = result.edge0, second = result.edge1;
    if (first.x > second.x)
        std::swap(first, second);
    near(first, {1, 0.3, 0}, "midline start must clip to shorter edge");
    near(second, {3, 0.3, 0}, "midline end must clip to shorter edge");
    require(std::abs(result.source_a0.x - result.edge0.x) < 1e-8 &&
                std::abs(result.source_b1.x - result.edge1.x) < 1e-8,
            "source points must match clipped seam endpoints");
    std::swap(input.a0, input.a1);
    std::swap(input.b0, input.b1);
    auto reversed = extend_surface_seam(input);
    require(reversed.success, "edge winding must not affect seam construction");
    near(reversed.edge0, result.edge0, "reversed seam first endpoint");
    near(reversed.edge1, result.edge1, "reversed seam second endpoint");

    input = coplanar();
    input.b0 = {1, 0, 0};
    input.b1 = {3, 0, 0};
    input.max_extension = 0;
    result = extend_surface_seam(input);
    require(result.success, "already coincident edges need no extension");
    near(result.edge0, result.source_a0, "zero gap must preserve supporting edge");

    input = coplanar();
    input.a0 = {0, 0.3, 0};
    input.a1 = {4, 0.3, 0};
    input.interior_a = {2, 1, 0};
    input.b0 = {1, 0, 0.3};
    input.b1 = {3, 0, 0.3};
    input.normal_b = {0, -1, 0};
    input.interior_b = {2, 0, 1};
    result = extend_surface_seam(input);
    require(result.success, "folded facets must extend to their plane intersection");
    for (const auto& p : {result.edge0, result.edge1})
        require(std::abs(p.y) < 1e-8 && std::abs(p.z) < 1e-8, "folded seam must lie on both planes");
    near(result.source_a0, {result.edge0.x, .3, 0}, "folded source A");
    near(result.source_b0, {result.edge0.x, 0, .3}, "folded source B");

    auto rotated = input;
    rotated.a0 = transform(input.a0);
    rotated.a1 = transform(input.a1);
    rotated.b0 = transform(input.b0);
    rotated.b1 = transform(input.b1);
    rotated.interior_a = transform(input.interior_a);
    rotated.interior_b = transform(input.interior_b);
    rotated.normal_a = rotate(input.normal_a);
    rotated.normal_b = rotate(input.normal_b);
    const auto rotated_result = extend_surface_seam(rotated);
    require(rotated_result.success, "rigidly transformed seam must remain valid");
    near(rotated_result.edge0, transform(result.edge0), "rigid transform seam start");
    near(rotated_result.edge1, transform(result.edge1), "rigid transform seam end");
    near(rotated_result.source_b1, transform(result.source_b1), "rigid transform source end");
    input.interior_a = {2, -1, 0};
    rejected(input, "folded seam must reject extension into facet interior");

    input = coplanar();
    input.b0 = {1, 0.4, 0};
    input.b1 = {3, 0.8, 0};
    result = extend_surface_seam(input);
    require(result.success, "skew coplanar boundary lines must have an internal bisector");
    const Vec3 edge_b = (input.b1 - input.b0) / (input.b1 - input.b0).norm();
    for (const auto& p : {result.edge0, result.edge1}) {
        const double distance_a = std::abs(p.y);
        const double distance_b = (p - input.b0).cross(edge_b).norm();
        require(std::abs(distance_a - distance_b) < 1e-8, "coplanar seam must be equidistant from skew boundary lines");
    }
    // Splitting a parallel boundary into subdivisions must preserve seam coverage.
    input = coplanar();
    input.b1 = {2, .6, 0};
    const auto left = extend_surface_seam(input);
    input.b0 = {2, .6, 0};
    input.b1 = {3, .6, 0};
    const auto right = extend_surface_seam(input);
    require(left.success && right.success, "unequal subdivisions must each join");
    require((left.edge0 - right.edge1).norm() < 1e-8 || (left.edge1 - right.edge0).norm() < 1e-8,
            "adjacent subdivision seams must share their endpoint");

    input = coplanar();
    input.max_extension = .29;
    rejected(input, "excessive extension must fail with a diagnostic");
    input = coplanar();
    input.b0.z = input.b1.z = input.interior_b.z = .1;
    rejected(input, "parallel offset planes must fail explicitly");
    input = coplanar();
    input.interior_a.y = 1;
    rejected(input, "boundaries facing the same direction must not join");
    input = coplanar();
    input.b0.x = 5;
    input.b1.x = 6;
    rejected(input, "disjoint finite edge intervals must not join");
    input = coplanar();
    input.normal_a = {0, 0, 0};
    rejected(input, "zero normal must fail");
    input = coplanar();
    input.a1 = input.a0;
    rejected(input, "zero length boundary must fail");
    input = coplanar();
    input.interior_b.z = 1;
    rejected(input, "off-plane facet interior must fail");
    input = coplanar();
    input.a0.x = std::numeric_limits<double>::quiet_NaN();
    rejected(input, "nonfinite coordinates must fail");
    return 0;
}
