#include <termin/navmesh/surface_navigation.hpp>

#include <algorithm>
#include <cmath>
#include <limits>

namespace termin {
    namespace {
        bool finite(const Vec3& v) {
            return std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z);
        }

        struct Boundary {
            Vec3 start, tangent, normal, outward;
            double length;
        };

        bool boundary(const Vec3& start,
                      const Vec3& end,
                      const Vec3& normal,
                      const Vec3& interior,
                      double tolerance,
                      Boundary& result) {
            if (!finite(start) || !finite(end) || !finite(normal) || !finite(interior))
                return false;
            const double normal_length = normal.norm();
            const Vec3 edge = end - start;
            const double length = edge.norm();
            if (!std::isfinite(normal_length) || !std::isfinite(length) || normal_length < 1e-12 || length <= tolerance)
                return false;
            result = {start, edge / length, normal / normal_length, {}, length};
            const Vec3 interior_delta = interior - start;
            if (!finite(interior_delta) || std::abs(edge.dot(result.normal)) > tolerance ||
                std::abs(interior_delta.dot(result.normal)) > tolerance)
                return false;
            result.outward = result.tangent.cross(result.normal);
            result.outward = result.outward / result.outward.norm();
            const double interior_distance = (interior - start).dot(result.outward);
            if (std::abs(interior_distance) <= tolerance)
                return false;
            if (interior_distance > 0)
                result.outward = result.outward * -1.0;
            return true;
        }

        // Restrict the seam parameter to the finite strip extruded from this edge.
        bool clip_edge(const Boundary& edge,
                       const Vec3& origin,
                       const Vec3& direction,
                       double tolerance,
                       double& low,
                       double& high) {
            const double slope = direction.dot(edge.tangent);
            const double offset = (origin - edge.start).dot(edge.tangent);
            if (std::abs(slope) < 1e-10)
                return false; // A transverse seam cannot be a nondegenerate edge extension.
            double begin = -offset / slope;
            double end = (edge.length - offset) / slope;
            if (begin > end)
                std::swap(begin, end);
            low = std::max(low, begin);
            high = std::min(high, end);
            return high - low > tolerance;
        }

        Vec3 source_point(const Boundary& edge, const Vec3& point) {
            return edge.start + edge.tangent * (point - edge.start).dot(edge.tangent);
        }
    } // namespace

    SurfaceSeamGeometry extend_surface_seam(const SurfaceSeamInput& input) {
        SurfaceSeamGeometry result;
        auto fail = [&result](const char* reason) {
            result.error = reason;
            return result;
        };
        if (!std::isfinite(input.tolerance) || input.tolerance <= 0 || !std::isfinite(input.max_extension) ||
            input.max_extension < 0)
            return fail("Invalid seam tolerance or maximum extension");
        Boundary a, b;
        if (!boundary(input.a0, input.a1, input.normal_a, input.interior_a, input.tolerance, a) ||
            !boundary(input.b0, input.b1, input.normal_b, input.interior_b, input.tolerance, b))
            return fail("Invalid seam edge, facet normal, or interior point");

        // Use a local origin to avoid cancellation when an entire station is translated.
        Vec3 origin = a.start;
        Vec3 direction = a.normal.cross(b.normal);
        const double sine = direction.norm();
        if (sine > 1e-8) {
            direction = direction / sine;
            // Intersection of n_a.x = 0 and n_b.x = n_b.(b0-a0).
            origin = a.start + direction.cross(a.normal) * ((b.start - a.start).dot(b.normal) / sine);
        } else {
            if (std::abs((b.start - a.start).dot(a.normal)) > input.tolerance ||
                std::abs((input.b1 - a.start).dot(a.normal)) > input.tolerance)
                return fail("Parallel offset facet planes have no surface seam");
            // Equal positive distances from the two boundaries into the gap select
            // the internal angle bisector, including its parallel midline limit.
            const Vec3 bisector_normal = a.outward - b.outward;
            const double squared = bisector_normal.dot(bisector_normal);
            if (squared < 1e-16)
                return fail("Coplanar boundaries do not face a common gap");
            origin = a.start + bisector_normal * (-(b.start - a.start).dot(b.outward) / squared);
            direction = a.normal.cross(bisector_normal);
            direction = direction / direction.norm();
        }

        double low = -std::numeric_limits<double>::infinity();
        double high = std::numeric_limits<double>::infinity();
        if (!clip_edge(a, origin, direction, input.tolerance, low, high) ||
            !clip_edge(b, origin, direction, input.tolerance, low, high))
            return fail("Seam edges have no nondegenerate overlapping interval");
        result.edge0 = origin + direction * low;
        result.edge1 = origin + direction * high;
        result.source_a0 = source_point(a, result.edge0);
        result.source_a1 = source_point(a, result.edge1);
        result.source_b0 = source_point(b, result.edge0);
        result.source_b1 = source_point(b, result.edge1);
        for (const Boundary* edge : {&a, &b}) {
            for (const Vec3& point : {result.edge0, result.edge1}) {
                const double extension = (point - edge->start).dot(edge->outward);
                if (extension < -input.tolerance)
                    return fail("Surface seam would extend a boundary into its facet interior");
                if (extension > input.max_extension + input.tolerance)
                    return fail("Surface seam exceeds maximum boundary extension");
            }
        }
        result.success = true;
        return result;
    }
} // namespace termin
