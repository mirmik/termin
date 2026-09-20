#include <tcbase/tc_log.hpp>
#include <termin/navmesh/surface_navigation.hpp>

#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>
#include <utility>

namespace termin {
    namespace {
        constexpr double epsilon = 1e-7;
        constexpr size_t absent = std::numeric_limits<size_t>::max();
        struct Point2 {
            double x = 0, y = 0;
            Point2 operator+(Point2 p) const {
                return {x + p.x, y + p.y};
            }
            Point2 operator-(Point2 p) const {
                return {x - p.x, y - p.y};
            }
            Point2 operator*(double t) const {
                return {x * t, y * t};
            }
            double dot(Point2 p) const {
                return x * p.x + y * p.y;
            }
            double cross(Point2 p) const {
                return x * p.y - y * p.x;
            }
            double length() const {
                return std::hypot(x, y);
            }
        };
        struct Frame {
            Vec3 origin, u, v;
            Point2 base, x{1, 0}, y{0, 1};
            Point2 map(Vec3 p) const {
                const auto d = p - origin;
                return base + x * d.dot(u) + y * d.dot(v);
            }
        };
        struct Gate {
            Point2 a, b;
        };
        Vec3 center(const SurfaceFace& face) {
            Vec3 result;
            for (const auto& p : face.vertices)
                result += p;
            return face.vertices.empty() ? result : result / static_cast<double>(face.vertices.size());
        }
        bool face_frame(const SurfaceFace& face, Frame& frame) {
            if (face.vertices.size() < 3)
                return false;
            frame.origin = face.vertices[0];
            Vec3 normal;
            for (size_t i = 1; i + 1 < face.vertices.size(); ++i) {
                const Vec3 u = face.vertices[i] - frame.origin;
                if (u.cross(face.vertices[i + 1] - frame.origin).try_normalized(normal, epsilon * epsilon) &&
                    u.try_normalized(frame.u, epsilon)) {
                    frame.v = normal.cross(frame.u);
                    for (const auto& p : face.vertices)
                        if (!p.is_finite() || std::abs((p - frame.origin).dot(normal)) > epsilon * 10)
                            return false;
                    return true;
                }
            }
            return false;
        }
        Vec3 closest_segment(Vec3 a, Vec3 b, Vec3 p) {
            const Vec3 d = b - a;
            const double sq = d.norm_squared();
            return sq <= epsilon * epsilon ? a : a + d * std::clamp((p - a).dot(d) / sq, 0.0, 1.0);
        }
        bool typed(const SurfaceFace& face) {
            return face.poly_type != 0 || face.vertices.size() < 3;
        }
        SurfacePath failure(const char* error) {
            tc_log_error("[SurfaceNavigation] %s", error);
            SurfacePath result;
            result.error = error;
            return result;
        }

        // Return the intersection interval along segment p--q. Collinear gates retain
        // their complete interval: selecting crossings greedily in occurrence order is
        // essential when a developed corridor overlaps itself.
        bool intersection(Point2 p, Point2 q, Gate gate, double& lo, double& hi) {
            const Point2 d = q - p, e = gate.b - gate.a, r = gate.a - p;
            const double d2 = d.dot(d), e2 = e.dot(e);
            if (d2 <= epsilon * epsilon) {
                double s = e2 > epsilon * epsilon ? std::clamp((p - gate.a).dot(e) / e2, 0.0, 1.0) : 0;
                if ((gate.a + e * s - p).length() > epsilon)
                    return false;
                lo = 0;
                hi = 1;
                return true;
            }
            const double determinant = d.cross(e);
            if (std::abs(determinant) > 1e-12 * d.length() * e.length()) {
                const double t = r.cross(e) / determinant, s = r.cross(d) / determinant;
                if (t < -epsilon || t > 1 + epsilon || s < -epsilon || s > 1 + epsilon)
                    return false;
                lo = hi = std::clamp(t, 0.0, 1.0);
                return true;
            }
            if (std::abs(r.cross(d)) > epsilon * d.length())
                return false;
            const double a = r.dot(d) / d2, b = (gate.b - p).dot(d) / d2;
            lo = std::max(0.0, std::min(a, b));
            hi = std::min(1.0, std::max(a, b));
            return lo <= hi + epsilon;
        }
        bool visible(const std::vector<Gate>& gates,
                     size_t from,
                     Point2 p,
                     size_t to,
                     Point2 q,
                     std::vector<Point2>* crossings = nullptr) {
            double previous = 0;
            // q is the selected point of the destination gate by construction.
            // Re-intersecting that gate divides almost collinear endpoint
            // differences and can reject an exact endpoint through roundoff.
            // Only intervening gates impose visibility constraints.
            for (size_t k = from + 1; k < to; ++k) {
                double lo, hi;
                if (!intersection(p, q, gates[k], lo, hi))
                    return false;
                const double t = std::max(previous, lo);
                if (t > hi + epsilon)
                    return false;
                previous = std::clamp(t, 0.0, 1.0);
                if (crossings)
                    crossings->push_back(p + (q - p) * previous);
            }
            if (crossings)
                crossings->push_back(q);
            return true;
        }

        bool surface_run(const SurfaceGraph& graph,
                         const SurfaceCorridor& corridor,
                         size_t first,
                         size_t last,
                         Vec3 start,
                         Vec3 end,
                         SurfacePath& output) {
            Frame frame;
            if (!face_frame(graph.faces[corridor.faces[first]], frame)) {
                tc_log_error("[SurfaceNavigation] cannot construct frame for corridor occurrence %zu face %zu",
                             first, corridor.faces[first]);
                return false;
            }
            std::vector<Gate> gates;
            const Point2 start2 = frame.map(start);
            gates.push_back({start2, start2});
            for (size_t i = first; i < last; ++i) {
                const auto& portal = graph.portals[corridor.portals[i]];
                const Point2 a = frame.map(portal.a), b = frame.map(portal.b);
                const Point2 edge = b - a;
                const double length = edge.length();
                if (length <= epsilon) {
                    tc_log_error("[SurfaceNavigation] collapsed developed portal %zu at occurrence %zu: length=%.17g",
                                 corridor.portals[i], i, length);
                    return false;
                }
                gates.push_back({a, b});
                const Point2 direction = edge * (1.0 / length);
                const Point2 perpendicular{-direction.y, direction.x};
                const double old_side = (frame.map(center(graph.faces[corridor.faces[i]])) - a).dot(perpendicular);
                Frame next;
                if (!face_frame(graph.faces[corridor.faces[i + 1]], next)) {
                    tc_log_error("[SurfaceNavigation] cannot construct next frame at occurrence %zu face %zu",
                                 i + 1, corridor.faces[i + 1]);
                    return false;
                }
                next.origin = portal.a;
                next.u = (portal.b - portal.a).normalized();
                const Vec3 inward = center(graph.faces[corridor.faces[i + 1]]) - portal.a;
                if (!(inward - next.u * inward.dot(next.u)).try_normalized(next.v, epsilon) ||
                    std::abs(old_side) <= epsilon) {
                    tc_log_error("[SurfaceNavigation] degenerate hinge portal %zu at occurrence %zu faces %zu -> %zu: "
                                 "old_side=%.17g inward=%.17g developed_length=%.17g spatial_length=%.17g",
                                 corridor.portals[i], i, corridor.faces[i], corridor.faces[i + 1], old_side,
                                 (inward - next.u * inward.dot(next.u)).norm(), length, (portal.b - portal.a).norm());
                    return false;
                }
                next.base = a;
                next.x = direction;
                next.y = perpendicular * (old_side > 0 ? -1.0 : 1.0);
                frame = next;
            }
            const Point2 end2 = frame.map(end);
            gates.push_back({end2, end2});
            struct Node {
                size_t gate;
                Point2 point;
            };
            std::vector<Node> nodes{{0, start2}};
            for (size_t i = 1; i + 1 < gates.size(); ++i) {
                nodes.push_back({i, gates[i].a});
                nodes.push_back({i, gates[i].b});
            }
            nodes.push_back({gates.size() - 1, end2});
            std::vector<size_t> route;
            if (visible(gates, 0, start2, gates.size() - 1, end2)) {
                route = {0, nodes.size() - 1};
            } else {
                // A shortest path in a fixed convex-face corridor bends only at portal
                // endpoints. Nodes are occurrences, not coordinates: coincident points
                // in different sheets must never be merged.
                std::vector<double> distance(nodes.size(), std::numeric_limits<double>::infinity());
                std::vector<size_t> previous(nodes.size(), absent);
                distance[0] = 0;
                for (size_t j = 1; j < nodes.size(); ++j) {
                    for (size_t i = 0; i < j; ++i) {
                        if (nodes[i].gate >= nodes[j].gate || !std::isfinite(distance[i]))
                            continue;
                        const double candidate = distance[i] + (nodes[j].point - nodes[i].point).length();
                        if (candidate >= distance[j] ||
                            !visible(gates, nodes[i].gate, nodes[i].point, nodes[j].gate, nodes[j].point))
                            continue;
                        distance[j] = candidate;
                        previous[j] = i;
                    }
                }
                if (!std::isfinite(distance.back())) {
                    tc_log_error("[SurfaceNavigation] visibility graph disconnected for occurrences %zu..%zu (%zu gates)",
                                 first, last, gates.size());
                    return false;
                }
                for (size_t i = nodes.size() - 1; i != absent; i = previous[i])
                    route.push_back(i);
                std::reverse(route.begin(), route.end());
            }
            for (size_t i = 1; i < route.size(); ++i) {
                const Node &a = nodes[route[i - 1]], &b = nodes[route[i]];
                std::vector<Point2> crossings;
                if (!visible(gates, a.gate, a.point, b.gate, b.point, &crossings)) {
                    tc_log_error("[SurfaceNavigation] reconstruction lost visibility between gates %zu and %zu",
                                 a.gate, b.gate);
                    return false;
                }
                for (size_t j = 0; j < crossings.size(); ++j) {
                    const size_t gate = a.gate + 1 + j;
                    if (gate + 1 == gates.size()) {
                        output.points.push_back({end, corridor.faces[last]});
                    } else {
                        const auto& portal = graph.portals[corridor.portals[first + gate - 1]];
                        const Point2 d = gates[gate].b - gates[gate].a;
                        const double t = std::clamp((crossings[j] - gates[gate].a).dot(d) / d.dot(d), 0.0, 1.0);
                        output.points.push_back(
                            {portal.a + (portal.b - portal.a) * t, corridor.faces[first + gate - 1]});
                    }
                }
            }
            return true;
        }
    } // namespace

    void SurfaceGraph::index() {
        outgoing.assign(faces.size(), {});
        for (size_t i = 0; i < portals.size(); ++i) {
            const auto& portal = portals[i];
            if (portal.from >= faces.size() || portal.to >= faces.size() || !portal.a.is_finite() ||
                !portal.b.is_finite()) {
                tc_log_error("[SurfaceNavigation] invalid portal %zu", i);
                continue;
            }
            outgoing[portal.from].push_back(i);
        }
    }

    Vec3 closest_surface_point(const SurfaceFace& face, const Vec3& point) {
        if (face.vertices.empty()) {
            tc_log_error("[SurfaceNavigation] cannot project onto an empty face");
            const double nan = std::numeric_limits<double>::quiet_NaN();
            return {nan, nan, nan};
        }
        if (face.vertices.size() == 1)
            return face.vertices[0];
        if (face.vertices.size() == 2)
            return closest_segment(face.vertices[0], face.vertices[1], point);
        Frame frame;
        if (!face_frame(face, frame)) {
            tc_log_error("[SurfaceNavigation] cannot project onto a degenerate or nonplanar face");
            const double nan = std::numeric_limits<double>::quiet_NaN();
            return {nan, nan, nan};
        }
        const Vec3 normal = frame.u.cross(frame.v);
        const Vec3 projected = point - normal * (point - frame.origin).dot(normal);
        bool positive = false, negative = false;
        Vec3 nearest = face.vertices[0];
        double distance = std::numeric_limits<double>::infinity();
        for (size_t i = 0; i < face.vertices.size(); ++i) {
            const Vec3 a = face.vertices[i], b = face.vertices[(i + 1) % face.vertices.size()];
            const double side = (b - a).cross(projected - a).dot(normal);
            const double side_tolerance = epsilon * (b - a).norm();
            positive |= side > side_tolerance;
            negative |= side < -side_tolerance;
            const Vec3 candidate = closest_segment(a, b, point);
            const double candidate_distance = (candidate - point).norm_squared();
            if (candidate_distance < distance) {
                nearest = candidate;
                distance = candidate_distance;
            }
        }
        return positive && negative ? nearest : projected;
    }

    SurfaceCorridor find_surface_corridor(
        const SurfaceGraph& graph, size_t start_face, const Vec3& start, size_t end_face, const Vec3& end) {
        SurfaceCorridor result;
        if (start_face >= graph.faces.size() || end_face >= graph.faces.size() ||
            graph.outgoing.size() != graph.faces.size() || !start.is_finite() || !end.is_finite()) {
            tc_log_error("[SurfaceNavigation] invalid corridor query or unindexed graph");
            return result;
        }
        std::vector<Vec3> centers;
        centers.reserve(graph.faces.size());
        for (const auto& face : graph.faces)
            centers.push_back(center(face));
        std::vector<double> distance(graph.faces.size(), std::numeric_limits<double>::infinity());
        std::vector<size_t> previous(graph.faces.size(), absent);
        using Entry = std::pair<double, size_t>;
        std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
        auto heuristic = [&](size_t i) {
            return (centers[i] - centers[end_face]).norm();
        };
        distance[start_face] = 0;
        queue.push({heuristic(start_face), start_face});
        size_t best = start_face;
        double best_distance = (closest_surface_point(graph.faces[best], end) - end).norm_squared();
        while (!queue.empty()) {
            const auto [estimate, face] = queue.top();
            queue.pop();
            if (estimate > distance[face] + heuristic(face) + epsilon)
                continue;
            const double goal_distance = (closest_surface_point(graph.faces[face], end) - end).norm_squared();
            if (goal_distance < best_distance) {
                best = face;
                best_distance = goal_distance;
            }
            if (face == end_face) {
                best = face;
                break;
            }
            for (size_t portal_index : graph.outgoing[face]) {
                if (portal_index >= graph.portals.size())
                    continue;
                const auto& portal = graph.portals[portal_index];
                if (portal.from != face || portal.to >= graph.faces.size())
                    continue;
                const Vec3 midpoint = (portal.a + portal.b) * 0.5;
                const double candidate =
                    distance[face] + (centers[face] - midpoint).norm() + (centers[portal.to] - midpoint).norm();
                if (candidate + epsilon >= distance[portal.to])
                    continue;
                distance[portal.to] = candidate;
                previous[portal.to] = portal_index;
                queue.push({candidate + heuristic(portal.to), portal.to});
            }
        }
        result.partial = best != end_face;
        result.start = closest_surface_point(graph.faces[start_face], start);
        result.end = closest_surface_point(graph.faces[best], end);
        if (!result.start.is_finite() || !result.end.is_finite())
            return result;
        for (size_t face = best;;) {
            result.faces.push_back(face);
            if (face == start_face)
                break;
            const size_t portal_index = previous[face];
            if (portal_index == absent) {
                tc_log_error("[SurfaceNavigation] broken corridor predecessor");
                return {};
            }
            result.portals.push_back(portal_index);
            face = graph.portals[portal_index].from;
        }
        std::reverse(result.faces.begin(), result.faces.end());
        std::reverse(result.portals.begin(), result.portals.end());
        result.success = true;
        return result;
    }

    SurfacePath straighten_surface_corridor(const SurfaceGraph& graph, const SurfaceCorridor& corridor) {
        if (!corridor.success || corridor.faces.empty() || corridor.portals.size() + 1 != corridor.faces.size() ||
            !corridor.start.is_finite() || !corridor.end.is_finite())
            return failure("invalid surface corridor");
        for (size_t i = 0; i < corridor.faces.size(); ++i) {
            if (corridor.faces[i] >= graph.faces.size())
                return failure("corridor face index out of bounds");
            if (i == corridor.portals.size())
                continue;
            if (corridor.portals[i] >= graph.portals.size())
                return failure("corridor portal index out of bounds");
            const auto& portal = graph.portals[corridor.portals[i]];
            if (portal.from != corridor.faces[i] || portal.to != corridor.faces[i + 1] || !portal.a.is_finite() ||
                !portal.b.is_finite())
                return failure("corridor portal does not connect its faces");
            for (size_t supporting_face : {portal.from, portal.to}) {
                const auto& face = graph.faces[supporting_face];
                const Vec3 a = closest_surface_point(face, portal.a);
                const Vec3 b = closest_surface_point(face, portal.b);
                if (!a.is_finite() || !b.is_finite() || (a - portal.a).norm() > epsilon * 10 ||
                    (b - portal.b).norm() > epsilon * 10)
                    return failure("portal is not contained in both supporting faces");
            }
        }
        const Vec3 start_projection = closest_surface_point(graph.faces[corridor.faces.front()], corridor.start);
        const Vec3 end_projection = closest_surface_point(graph.faces[corridor.faces.back()], corridor.end);
        if (!start_projection.is_finite() || !end_projection.is_finite() ||
            (start_projection - corridor.start).norm() > epsilon * 10 ||
            (end_projection - corridor.end).norm() > epsilon * 10)
            return failure("corridor endpoint is not on its supporting face");
        SurfacePath output;
        output.points.push_back({corridor.start, corridor.faces[0]});
        size_t first = 0;
        Vec3 start = corridor.start;
        while (first < corridor.faces.size()) {
            size_t last = first;
            if (!typed(graph.faces[corridor.faces[first]])) {
                while (last < corridor.portals.size()) {
                    const auto& portal = graph.portals[corridor.portals[last]];
                    if (typed(graph.faces[corridor.faces[last + 1]]) || (portal.b - portal.a).norm() <= epsilon)
                        break;
                    ++last;
                }
            }
            Vec3 end = corridor.end;
            if (last < corridor.portals.size()) {
                const auto& portal = graph.portals[corridor.portals[last]];
                if ((portal.b - portal.a).norm() > epsilon)
                    return failure("typed transition requires a point portal");
                end = portal.a;
            }
            if (typed(graph.faces[corridor.faces[first]])) {
                output.points.push_back({end, corridor.faces[first]});
            } else if (!surface_run(graph, corridor, first, last, start, end, output)) {
                return failure("cannot develop or straighten surface corridor");
            }
            first = last + 1;
            start = end;
        }
        output.success = true;
        return output;
    }
} // namespace termin
