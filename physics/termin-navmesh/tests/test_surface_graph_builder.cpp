#include <termin/navmesh/surface_graph_builder.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <vector>

using namespace termin;
namespace {
    void require(bool condition, const char* message) {
        if (!condition) {
            std::fprintf(stderr, "%s\n", message);
            std::abort();
        }
    }
    DetourSurfacePolygon rectangle(unsigned long long ref, float x0, float x1, float y0, float y1) {
        DetourSurfacePolygon polygon;
        polygon.poly_ref = ref;
        polygon.flags = 1;
        polygon.area = 7;
        polygon.vertices = {{x0, y0, 0}, {x1, y0, 0}, {x1, y1, 0}, {x0, y1, 0}};
        polygon.detail_triangles = {{polygon.vertices[0], polygon.vertices[1], polygon.vertices[2]},
                                    {polygon.vertices[0], polygon.vertices[2], polygon.vertices[3]}};
        return polygon;
    }
    DetourSurfacePolygon subdivided_rectangle() {
        auto polygon = rectangle(20, 0, 4, .6f, 2.6f);
        const std::vector<Vec3f> rim = {{0, .6f, 0}, {1, .6f, 0}, {4, .6f, 0}, {4, 2.6f, 0}, {0, 2.6f, 0}};
        const Vec3f center{2, 1.6f, 0};
        polygon.detail_triangles.clear();
        for (size_t i = 0; i < rim.size(); ++i)
            polygon.detail_triangles.push_back({center, rim[i], rim[(i + 1) % rim.size()]});
        return polygon;
    }
    SurfaceGraphSeam seam(float gap = .6f) {
        SurfaceGraphSeam result;
        result.from = 0;
        result.to = 1;
        result.start_a = {0, 0, 0};
        result.start_b = {4, 0, 0};
        result.end_a = {0, gap, 0};
        result.end_b = {4, gap, 0};
        return result;
    }
    std::vector<SurfacePortal> crossings(const SurfaceGraph& graph) {
        std::vector<SurfacePortal> result;
        for (const auto& portal : graph.portals)
            if (graph.faces[portal.from].surface == 0 && graph.faces[portal.to].surface == 1)
                result.push_back(portal);
        return result;
    }
    double coverage(const std::vector<SurfacePortal>& portals) {
        double total = 0;
        for (const auto& portal : portals)
            total += (portal.b - portal.a).norm();
        return total;
    }
    size_t nearest(const SurfaceGraph& graph, size_t surface, Vec3 point) {
        size_t best = std::numeric_limits<size_t>::max();
        double distance = std::numeric_limits<double>::infinity();
        for (size_t i = 0; i < graph.faces.size(); ++i) {
            if (graph.faces[i].surface != surface || graph.faces[i].poly_type)
                continue;
            double current = (closest_surface_point(graph.faces[i], point) - point).norm();
            if (current < distance) {
                distance = current;
                best = i;
            }
        }
        require(best != std::numeric_limits<size_t>::max(), "missing native surface face");
        return best;
    }
    bool reaches(const SurfaceGraph& graph, size_t start, size_t end) {
        std::vector<bool> visited(graph.faces.size(), false);
        std::vector<size_t> queue{start};
        visited[start] = true;
        for (size_t i = 0; i < queue.size(); ++i) {
            if (queue[i] == end)
                return true;
            for (size_t index : graph.outgoing[queue[i]]) {
                size_t next = graph.portals[index].to;
                if (!visited[next]) {
                    visited[next] = true;
                    queue.push_back(next);
                }
            }
        }
        return false;
    }
    DetourSurfaceLink link(unsigned long long target, Vec3f a, Vec3f b) {
        DetourSurfaceLink result;
        result.poly_ref = target;
        result.left = result.target_left = a;
        result.right = result.target_right = b;
        return result;
    }
} // namespace

int main() {
    DetourSurfaceSnapshot a{41, 0, {rectangle(10, 0, 4, -2, 0)}};
    DetourSurfaceSnapshot b{67, 0, {subdivided_rectangle()}};
    auto declaration = seam();
    auto graph = build_surface_graph({{&a, {}}, {&b, {}}}, {declaration});
    const auto portals = crossings(graph);
    require(portals.size() == 2, "detail boundary subdivisions must produce two seam intervals");
    require(std::abs(coverage(portals) - 4) < 1e-5, "seam must retain full authored width");
    for (const auto& portal : portals) {
        require(std::abs(portal.a.y - .3) < 1e-5 && std::abs(portal.b.y - .3) < 1e-5,
                "coplanar extended boundaries must meet at their midline");
        require(graph.faces[portal.from].generation == 41 && graph.faces[portal.to].generation == 67,
                "extension faces must preserve geometry generations");
    }
    const Vec3 start{.5, -1, 0}, end{3.5, 1.6, 0};
    const auto corridor = find_surface_corridor(graph, nearest(graph, 0, start), start, nearest(graph, 1, end), end);
    require(corridor.success && !corridor.partial, "split detail facets must remain traversable across seam");
    const auto path = straighten_surface_corridor(graph, corridor);
    require(path.success, "coplanar extended corridor must straighten");
    declaration.bidirectional = false;
    graph = build_surface_graph({{&a, {}}, {&b, {}}}, {declaration});
    require(reaches(graph, nearest(graph, 0, start), nearest(graph, 1, end)) &&
                !reaches(graph, nearest(graph, 1, end), nearest(graph, 0, start)),
            "one-way seam declaration must preserve direction");
    declaration.bidirectional = true;

    // Removing the middle destination interval must leave a real hole in the seam.
    b.polygons = {rectangle(20, 0, 1, .6f, 2.6f), rectangle(21, 3, 4, .6f, 2.6f)};
    graph = build_surface_graph({{&a, {}}, {&b, {}}}, {declaration});
    require(std::abs(coverage(crossings(graph)) - 2) < 1e-5, "blocked interval must reduce traversable seam width");
    for (const auto& portal : crossings(graph))
        require(std::max(portal.a.x, portal.b.x) <= 1 + 1e-5 || std::min(portal.a.x, portal.b.x) >= 3 - 1e-5,
                "seam must not bridge a missing boundary interval");

    b.polygons = {rectangle(20, 0, 4, 2, 4)};
    graph = build_surface_graph({{&a, {}}, {&b, {}}}, {seam(2)});
    require(crossings(graph).empty(), "gap above maximum extension must remain disconnected");

    // Two local bake frames form a right angle, with erosion on both sides.
    a.polygons = {rectangle(10, 0, 4, -2.3f, -.3f)};
    b.polygons = {rectangle(20, 0, 4, .3f, 2.3f)};
    Pose3 fold;
    fold.ang = Quat::from_axis_angle({1, 0, 0}, std::acos(-1.0) / 2);
    declaration.start_a = {0, -.3, 0};
    declaration.start_b = {4, -.3, 0};
    declaration.end_a = {0, 0, .3};
    declaration.end_b = {4, 0, .3};
    graph = build_surface_graph({{&a, {}}, {&b, fold}}, {declaration});
    require(std::abs(coverage(crossings(graph)) - 4) < 1e-5, "folded seam must preserve width");
    for (const auto& portal : crossings(graph))
        require(std::abs(portal.a.y) + std::abs(portal.a.z) + std::abs(portal.b.y) + std::abs(portal.b.z) < 1e-5,
                "folded seam must lie on the plane intersection");
    const Vec3 folded_start{2, -1, 0}, folded_end{2, 0, 1};
    require(reaches(graph, nearest(graph, 0, folded_start), nearest(graph, 1, folded_end)),
            "folded seam must connect both detail surfaces");
    Pose3 rigid;
    rigid.ang = Quat::from_axis_angle(Vec3{1, 2, 3}.normalized(), .93);
    rigid.lin = {31, -19, 7};
    declaration.start_a = rigid.transform_point(declaration.start_a);
    declaration.start_b = rigid.transform_point(declaration.start_b);
    declaration.end_a = rigid.transform_point(declaration.end_a);
    declaration.end_b = rigid.transform_point(declaration.end_b);
    const auto moved = build_surface_graph({{&a, rigid}, {&b, rigid * fold}}, {declaration});
    require(moved.faces.size() == graph.faces.size() && moved.portals.size() == graph.portals.size(),
            "rigid frame changes must preserve graph topology");
    for (size_t i = 0; i < graph.faces.size(); ++i)
        for (size_t j = 0; j < graph.faces[i].vertices.size(); ++j)
            require((moved.faces[i].vertices[j] - rigid.transform_point(graph.faces[i].vertices[j])).norm() < 1e-5,
                    "graph and extension geometry must transform rigidly");

    // Geometric coincidence cannot manufacture Detour adjacency.
    DetourSurfaceSnapshot touching{9, 0, {rectangle(1, 0, 4, -2, 0), rectangle(2, 0, 4, 0, 2)}};
    graph = build_surface_graph({{&touching, {}}}, {});
    for (const auto& portal : graph.portals)
        require(graph.faces[portal.from].poly_ref == graph.faces[portal.to].poly_ref,
                "unlinked touching polygons must stay disconnected");
    touching.polygons[0].links = {link(2, {1, 0, 0}, {3, 0, 0})};
    touching.polygons[1].links = {link(1, {1, 0, 0}, {3, 0, 0})};
    graph = build_surface_graph({{&touching, {}}}, {});
    size_t clipped_count = 0;
    for (const auto& portal : graph.portals) {
        if (graph.faces[portal.from].poly_ref == graph.faces[portal.to].poly_ref)
            continue;
        ++clipped_count;
        require(std::min(portal.a.x, portal.b.x) >= 1 - 1e-5 && std::max(portal.a.x, portal.b.x) <= 3 + 1e-5,
                "native portals must respect Detour's clipped link interval");
    }
    require(clipped_count == 2, "clipped native adjacency must remain bidirectional");

    // Adjacent Detour detail boundaries can differ in height within walkable climb.
    auto stepped = touching;
    stepped.walkable_climb = .25f;
    for (auto& triangle : stepped.polygons[1].detail_triangles)
        for (auto& vertex : triangle)
            vertex.z = .2f;
    graph = build_surface_graph({{&stepped, {}}}, {});
    require(graph.faces.size() == 5, "climbable detail discontinuity must produce one planar riser");
    const Vec3 step_start{2, -1, 0}, step_end{2, 1, .2};
    const auto step_corridor =
        find_surface_corridor(graph, nearest(graph, 0, step_start), step_start, nearest(graph, 0, step_end), step_end);
    require(step_corridor.success && !step_corridor.partial, "climbable native step must stay connected");
    const auto step_path = straighten_surface_corridor(graph, step_corridor);
    require(step_path.success, "native step corridor must straighten over the explicit riser");
    double step_length = 0;
    for (size_t i = 1; i < step_path.points.size(); ++i)
        step_length += (step_path.points[i].point - step_path.points[i - 1].point).norm();
    require(std::abs(step_length - 2.2) < 1e-5,
            "native step path must follow the riser rather than a diagonal shortcut");
    const auto& riser = graph.faces.back();
    for (const auto& vertex : riser.vertices)
        require(vertex.x >= 1 - 1e-5 && vertex.x <= 3 + 1e-5 && std::abs(vertex.y) < 1e-5,
                "native riser must retain the clipped link interval");
    stepped.polygons[1].links.clear();
    graph = build_surface_graph({{&stepped, {}}}, {});
    require(reaches(graph, nearest(graph, 0, step_start), nearest(graph, 0, step_end)) &&
                !reaches(graph, nearest(graph, 0, step_end), nearest(graph, 0, step_start)),
            "native riser must retain directed adjacency");
    stepped.walkable_climb = .1f;
    graph = build_surface_graph({{&stepped, {}}}, {});
    require(!reaches(graph, nearest(graph, 0, step_start), nearest(graph, 0, step_end)),
            "detail discontinuity exceeding walkable climb must remain disconnected");

    // A one-way typed transition must retain its semantic metadata and direction.
    DetourSurfaceSnapshot typed{13, 0, {rectangle(1, 0, 1, 0, 1), rectangle(2, 3, 4, 0, 1)}};
    DetourSurfacePolygon transition;
    transition.poly_ref = 3;
    transition.flags = 1;
    transition.poly_type = 1;
    transition.area = 6;
    transition.user_id = 731;
    transition.vertices = {{.6f, .5f, 0}, {3.5f, .5f, 0}};
    typed.polygons[0].links = {link(3, {.5f, .5f, 0}, {.5f, .5f, 0})};
    typed.polygons[0].links[0].target_left = typed.polygons[0].links[0].target_right = {.6f, .5f, 0};
    transition.links = {link(2, {3.5f, .5f, 0}, {3.5f, .5f, 0})};
    typed.polygons.push_back(transition);
    graph = build_surface_graph({{&typed, {}}}, {});
    const size_t from = nearest(graph, 0, {.5, .5, 0}), to = nearest(graph, 0, {3.5, .5, 0});
    require(reaches(graph, from, to) && !reaches(graph, to, from), "typed link direction must be preserved");
    size_t typed_faces = 0;
    for (const auto& face : graph.faces)
        if (face.poly_type) {
            ++typed_faces;
            require(face.poly_type == 1 && face.area == 6 && face.user_id == 731,
                    "typed transition metadata must survive graph extraction");
        }
    require(typed_faces == 2, "distinct typed attachments must retain a typed connecting segment");
    return 0;
}
