#include <termin/navmesh/surface_navigation.hpp>

#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <new>

// Test-only instrumentation of ordinary C++ allocations. The solver's vectors
// use default alignment. Counting is enabled only around the measured call,
// excluding fixture construction, diagnostics and result destruction.
namespace allocation_profile {
    std::atomic<bool> enabled{false};
    std::atomic<size_t> calls{0}, bytes{0};
} // namespace allocation_profile
void* operator new(size_t size) {
    void* memory = std::malloc(size ? size : 1);
    if (!memory)
        throw std::bad_alloc();
    if (allocation_profile::enabled.load(std::memory_order_relaxed)) {
        allocation_profile::calls.fetch_add(1, std::memory_order_relaxed);
        allocation_profile::bytes.fetch_add(size, std::memory_order_relaxed);
    }
    return memory;
}
void* operator new[](size_t size) {
    return ::operator new(size);
}
void operator delete(void* memory) noexcept {
    std::free(memory);
}
void operator delete[](void* memory) noexcept {
    std::free(memory);
}
void operator delete(void* memory, size_t) noexcept {
    std::free(memory);
}
void operator delete[](void* memory, size_t) noexcept {
    std::free(memory);
}

using namespace termin;
namespace {
    void require(bool value, const char* message) {
        if (!value) {
            std::fprintf(stderr, "surface navigation: %s\n", message);
            std::abort();
        }
    }
    void near(double a, double b, const char* message) {
        require(std::abs(a - b) < 1e-5, message);
    }
    double length(const SurfacePath& path) {
        double result = 0;
        for (size_t i = 1; i < path.points.size(); ++i)
            result += (path.points[i].point - path.points[i - 1].point).norm();
        return result;
    }
    SurfaceFace face(std::initializer_list<Vec3> vertices) {
        SurfaceFace result;
        result.vertices = vertices;
        return result;
    }
    void connect(SurfaceGraph& graph, size_t a, size_t b, Vec3 p, Vec3 q) {
        graph.portals.push_back({a, b, p, q});
        graph.portals.push_back({b, a, p, q});
    }
    SurfaceGraph strip(size_t count) {
        SurfaceGraph graph;
        for (size_t i = 0; i < count; ++i) {
            double x = static_cast<double>(i);
            graph.faces.push_back(face({{x, 0, 0}, {x + 1, 0, 0}, {x + 1, 1, 0}, {x, 1, 0}}));
            if (i)
                connect(graph, i - 1, i, {x, 0, 0}, {x, 1, 0});
        }
        graph.index();
        return graph;
    }
    SurfaceCorridor ordered(const SurfaceGraph& graph, Vec3 start, Vec3 end) {
        SurfaceCorridor c;
        c.success = true;
        c.start = start;
        c.end = end;
        for (size_t i = 0; i < graph.faces.size(); ++i)
            c.faces.push_back(i);
        for (size_t i = 0; i + 1 < graph.faces.size(); ++i)
            c.portals.push_back(i * 2);
        return c;
    }
    Vec3 rotate(Vec3 p, Vec3 origin, Vec3 axis, double angle) {
        Vec3 v = p - origin;
        return origin + v * std::cos(angle) + axis.cross(v) * std::sin(angle) +
               axis * axis.dot(v) * (1 - std::cos(angle));
    }
    void fold(SurfaceGraph& graph, size_t after, double angle, Vec3& end) {
        auto hinge = graph.portals[after * 2];
        Vec3 axis = (hinge.b - hinge.a).normalized();
        for (size_t i = after + 1; i < graph.faces.size(); ++i)
            for (auto& p : graph.faces[i].vertices)
                p = rotate(p, hinge.a, axis, angle);
        for (auto& portal : graph.portals) {
            if (portal.from > after && portal.to > after) {
                portal.a = rotate(portal.a, hinge.a, axis, angle);
                portal.b = rotate(portal.b, hinge.a, axis, angle);
            }
        }
        end = rotate(end, hinge.a, axis, angle);
    }
    void supporting_segments(const SurfaceGraph& graph, const SurfacePath& path) {
        for (size_t i = 1; i < path.points.size(); ++i) {
            const auto& f = graph.faces[path.points[i].face];
            Vec3 midpoint = (path.points[i - 1].point + path.points[i].point) * 0.5;
            require((closest_surface_point(f, midpoint) - midpoint).norm() < 1e-5,
                    "segment must remain on supporting face");
        }
    }
    void planar_and_long_strip() {
        auto graph = strip(200);
        auto c = find_surface_corridor(graph, 0, {.1, .2, 2}, 199, {199.8, .7, 3});
        require(c.success && !c.partial && c.faces.size() == 200, "A* connects long strip and projects endpoints");
        auto path = straighten_surface_corridor(graph, c);
        require(path.success && path.points.size() == 201, "every portal crossing reconstructed");
        near(length(path), std::hypot(199.7, .5), "planar straight path has Euclidean length");
        supporting_segments(graph, path);
        graph.faces.push_back(face({{250, 0, 0}, {251, 0, 0}, {251, 1, 0}, {250, 1, 0}}));
        graph.index();
        c = find_surface_corridor(graph, 0, {.1, .2, 0}, 200, {250.5, .5, 0});
        require(c.success && c.partial && c.faces.back() == 199,
                "unreachable goal returns nearest reachable partial corridor");
        near(c.end.x, 200, "partial endpoint clamped to last reachable face");
    }
    void folded_strip() {
        auto graph = strip(3);
        Vec3 start{.2, .1, 0}, end{2.8, .9, 0};
        fold(graph, 0, 1.5707963267948966, end);
        fold(graph, 1, -1.1, end);
        auto path = straighten_surface_corridor(graph, ordered(graph, start, end));
        require(path.success && path.points.size() == 4, "folded path includes both hinges");
        near(length(path), std::hypot(2.6, .8), "folds preserve intrinsic length");
        require(length(path) > (end - start).norm() + .1, "folded path does not cut a 3D chord");
        supporting_segments(graph, path);

        graph = strip(2);
        for (auto& f : graph.faces)
            for (auto& p : f.vertices)
                p *= 1e-4;
        for (auto& portal : graph.portals) {
            portal.a *= 1e-4;
            portal.b *= 1e-4;
        }
        path = straighten_surface_corridor(graph, ordered(graph, {.2e-4, .1e-4, 0}, {1.8e-4, .9e-4, 0}));
        require(path.success && path.points.size() == 3, "small nondegenerate faces remain navigable");
        require(std::abs(length(path) - std::hypot(1.6e-4, .8e-4)) < 1e-9,
                "short gates use geometric rather than unit-scale parallel tolerance");
    }
    void multiaxis_folds() {
        SurfaceGraph graph;
        graph.faces = {face({{0, 0, 0}, {1, 0, 0}, {0, 1, 0}}),
                       face({{1, 0, 0}, {1, 1, 0}, {0, 1, 0}}),
                       face({{1, 0, 0}, {2, 1, 0}, {1, 1, 0}}),
                       face({{1, 1, 0}, {2, 1, 0}, {2, 2, 0}})};
        connect(graph, 0, 1, {1, 0, 0}, {0, 1, 0});
        connect(graph, 1, 2, {1, 0, 0}, {1, 1, 0});
        connect(graph, 2, 3, {1, 1, 0}, {2, 1, 0});
        Vec3 start{.2, .3, 0}, end{1.7, 1.4, 0};
        const double expected = (end - start).norm();
        fold(graph, 0, .8, end);
        fold(graph, 1, -.6, end);
        fold(graph, 2, 1.1, end);
        auto path = straighten_surface_corridor(graph, ordered(graph, start, end));
        require(path.success, "multiple nonparallel hinges develop successfully");
        near(length(path), expected, "multiaxis unfolding preserves geodesic");
        supporting_segments(graph, path);
    }
    void bent_corridor() {
        SurfaceGraph graph;
        graph.faces = {face({{0, 0, 0}, {2, 0, 0}, {2, 1, 0}, {0, 1, 0}}),
                       face({{1, 1, 0}, {2, 1, 0}, {2, 3, 0}, {1, 3, 0}})};
        connect(graph, 0, 1, {1, 1, 0}, {2, 1, 0});
        auto path = straighten_surface_corridor(graph, ordered(graph, {.1, .5, 0}, {1.5, 2.9, 0}));
        require(path.success, "path around an inside corner exists");
        near(path.points[1].point.x, 1, "shortest path touches reflex portal endpoint");
        near(length(path), std::hypot(.9, .5) + std::hypot(.5, 1.9), "corner path length is analytical");
        supporting_segments(graph, path);
    }
    void overlapping_development_and_saddle() {
        // A fan with more than a full turn deliberately repeats developed positions.
        // Occurrences must stay ordered; a shortcut in the 2D union is invalid.
        SurfaceGraph graph;
        const double step = 1.0471975511965976;
        auto rim = [&](size_t i) {
            return Vec3{std::cos(step * i), std::sin(step * i), 0};
        };
        for (size_t i = 0; i < 9; ++i) {
            graph.faces.push_back(face({{0, 0, 0}, rim(i), rim(i + 1)}));
            if (i)
                connect(graph, i - 1, i, {0, 0, 0}, rim(i));
        }
        const Vec3 start = (rim(0) + rim(1)) * .4, end = (rim(8) + rim(9)) * .4;
        auto path = straighten_surface_corridor(graph, ordered(graph, start, end));
        require(path.success && path.points.size() == 10, "overlap preserves every corridor occurrence");
        near(
            length(path), start.norm() + end.norm(), "saddle fan goes through shared vertex, not overlapping shortcut");
        supporting_segments(graph, path);

        // The alternating-height ring gives four 120-degree face angles around
        // the center (negative intrinsic curvature). This three-face corridor
        // sweeps 240 degrees between its endpoints, so its geodesic hits the apex.
        const Vec3 rim3[] = {{1, 0, 1}, {0, 1, -1}, {-1, 0, 1}, {0, -1, -1}};
        graph = {};
        for (size_t i = 0; i < 3; ++i) {
            graph.faces.push_back(face({{0, 0, 0}, rim3[i], rim3[i + 1]}));
            if (i)
                connect(graph, i - 1, i, {}, rim3[i]);
        }
        const Vec3 saddle_start = (rim3[0] + rim3[1]) * .25;
        const Vec3 saddle_end = (rim3[2] + rim3[3]) * .25;
        path = straighten_surface_corridor(graph, ordered(graph, saddle_start, saddle_end));
        require(path.success, "negative-curvature saddle corridor is supported");
        near(length(path), saddle_start.norm() + saddle_end.norm(), "saddle geodesic has analytical apex length");
        near(path.points[1].point.norm(), 0, "saddle path reaches shared apex");
        supporting_segments(graph, path);
    }
    void nearly_collinear_portal_endpoint() {
        // These exact coordinates reproduce cancellation when intersecting a
        // segment with its known destination endpoint: the previous redundant
        // intersection computed gate parameter 1.000001337 and rejected it.
        const Vec3 start{-11.152989529175624, 19.81815998228476, 0};
        const Vec3 a{-9.799885293559889, 21.190770947639532, 0};
        const Vec3 b{-6.846821592863352, 24.186406841468926, 0};
        const Vec3 along = b - a;
        const Vec3 across = Vec3{-along.y, along.x, 0}.normalized() * 5;
        const Vec3 end = a + across * .5;
        SurfaceGraph graph;
        graph.faces = {face({{0, 0, 0}, {10, 0, 0}, b, a - along}), face({a, b, b + across, a + across})};
        connect(graph, 0, 1, b, a);
        auto path = straighten_surface_corridor(graph, ordered(graph, start, end));
        require(path.success && path.points.size() == 3, "near-collinear endpoint corridor remains connected");
        near((path.points[1].point - a).norm(), 0, "known gate endpoint survives cancellation");
        near(length(path), (start - a).norm() + (end - a).norm(), "endpoint cancellation must not create a detour");
        supporting_segments(graph, path);
    }
    void typed_transition_and_validation() {
        auto graph = strip(1);
        SurfaceFace line = face({{1, .5, 0}, {4, .5, 2}});
        line.poly_type = 1;
        graph.faces.push_back(line);
        graph.faces.push_back(face({{4, 0, 2}, {5, 0, 2}, {5, 1, 2}, {4, 1, 2}}));
        connect(graph, 0, 1, {1, .5, 0}, {1, .5, 0});
        connect(graph, 1, 2, {4, .5, 2}, {4, .5, 2});
        auto c = ordered(graph, {.2, .2, 0}, {4.8, .8, 2});
        auto path = straighten_surface_corridor(graph, c);
        require(path.success && path.points.size() == 4, "typed transitions split surface runs");
        require(path.points[2].face == 1, "offmesh segment retains its supporting type");
        supporting_segments(graph, path);
        c.portals[0] = 1000;
        require(!straighten_surface_corridor(graph, c).success, "invalid portal index fails explicitly");
        graph = strip(1);
        graph.faces[0].vertices[2].z = 1;
        require(!straighten_surface_corridor(graph, ordered(graph, {.1, .1, 0}, {.8, .8, 0})).success,
                "nonplanar polygons rejected rather than flattened");
        graph.faces[0] = face({{0, 0, 0}, {1, 0, 0}, {2, 0, 0}});
        require(!straighten_surface_corridor(graph, ordered(graph, {}, {1, 0, 0})).success,
                "degenerate surface fails explicitly");
    }
    void profile(const char* label, const SurfaceGraph& graph, const SurfaceCorridor& corridor) {
        // Warm up code and runtime facilities before the measured invocation.
        require(straighten_surface_corridor(graph, corridor).success, "profile warmup succeeds");
        allocation_profile::calls.store(0, std::memory_order_relaxed);
        allocation_profile::bytes.store(0, std::memory_order_relaxed);
        const auto begin = std::chrono::steady_clock::now();
        allocation_profile::enabled.store(true, std::memory_order_relaxed);
        auto path = straighten_surface_corridor(graph, corridor);
        allocation_profile::enabled.store(false, std::memory_order_relaxed);
        const auto end = std::chrono::steady_clock::now();
        require(path.success && path.points.size() == corridor.faces.size() + 1,
                "profile preserves every gate crossing");
        supporting_segments(graph, path);
        const double milliseconds = std::chrono::duration<double, std::milli>(end - begin).count();
        std::printf("surface_navigation profile %s: faces=%zu elapsed_ms=%.3f allocations=%zu allocated_bytes=%zu\n",
                    label,
                    corridor.faces.size(),
                    milliseconds,
                    allocation_profile::calls.load(std::memory_order_relaxed),
                    allocation_profile::bytes.load(std::memory_order_relaxed));
    }
    void bounded_performance_profile() {
        for (size_t count : {size_t{200}, size_t{1000}}) {
            auto graph = strip(count);
            profile("straight", graph, ordered(graph, {.1, .2, 0}, {double(count) - .1, .8, 0}));
        }
        SurfaceGraph graph;
        // Eight alternating rows force seven hairpins. Cells touching elsewhere
        // remain separate sheets of the explicitly ordered corridor.
        int previous_x = 0, previous_y = 0;
        for (int row = 0; row < 8; ++row)
            for (int column = 0; column < 8; ++column) {
                const int x = row % 2 ? 7 - column : column, y = row;
                const size_t id = graph.faces.size();
                graph.faces.push_back(face({{double(x), double(y), 0},
                                            {double(x + 1), double(y), 0},
                                            {double(x + 1), double(y + 1), 0},
                                            {double(x), double(y + 1), 0}}));
                if (id) {
                    if (x != previous_x) {
                        const double edge_x = double(x > previous_x ? x : previous_x);
                        connect(graph, id - 1, id, {edge_x, double(y), 0}, {edge_x, double(y + 1), 0});
                    } else {
                        connect(graph, id - 1, id, {double(x), double(y), 0}, {double(x + 1), double(y), 0});
                    }
                }
                previous_x = x;
                previous_y = y;
            }
        profile("seven_hairpins", graph, ordered(graph, {.1, .5, 0}, {.1, double(previous_y) + .5, 0}));
        graph = {};
        auto rim = [](size_t i) {
            const double angle = double(i) * 1.0471975511965976;
            return Vec3{std::cos(angle), std::sin(angle), 0};
        };
        for (size_t i = 0; i < 96; ++i) {
            graph.faces.push_back(face({{}, rim(i), rim(i + 1)}));
            if (i)
                connect(graph, i - 1, i, {}, rim(i));
        }
        profile("overlapping_fan", graph, ordered(graph, (rim(0) + rim(1)) * .4, (rim(95) + rim(96)) * .4));
    }
} // namespace
int main() {
    planar_and_long_strip();
    folded_strip();
    multiaxis_folds();
    bent_corridor();
    overlapping_development_and_saddle();
    nearly_collinear_portal_endpoint();
    typed_transition_and_validation();
    bounded_performance_profile();
    return 0;
}
