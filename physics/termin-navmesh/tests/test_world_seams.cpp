#include <DetourAlloc.h>
#include <DetourNavMeshBuilder.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <termin/entity/unknown_component.hpp>
#include <termin/navmesh/components_bootstrap.hpp>
#include <termin/navmesh/pathfinding_world.hpp>
#include <termin/navmesh/tc_navmesh_registry.h>
#include <termin/navmesh/world_navmesh_seam_component.hpp>
#include <termin/tc_scene.hpp>
#include <termin_scene/internal/tc_scene_extension_registry.h>

using namespace termin;
namespace {
    void require(bool condition, const char* message) {
        if (!condition) {
            std::fprintf(stderr, "world seams: %s\n", message);
            std::abort();
        }
    }
    void near(double actual, double expected, const char* message) {
        if (std::abs(actual - expected) > 2e-4) {
            std::fprintf(stderr, "%s: actual %.9f expected %.9f\n", message, actual, expected);
            std::abort();
        }
    }
    void tile(const char* uuid, unsigned short inset, bool create, unsigned char area = 1) {
        const unsigned short upper = 100 - inset;
        const unsigned short vertices[] = {inset, 0, inset, upper, 0, inset, upper, 0, upper, inset, 0, upper};
        const unsigned short polygons[] = {0, 1, 2, 3, 0xffff, 0xffff, 0xffff, 0xffff};
        const unsigned short flags[] = {1};
        const unsigned char areas[] = {area};
        dtNavMeshCreateParams params{};
        params.verts = vertices;
        params.vertCount = 4;
        params.polys = polygons;
        params.polyCount = 1;
        params.nvp = 4;
        params.polyFlags = flags;
        params.polyAreas = areas;
        params.bmax[0] = 10;
        params.bmax[1] = 1;
        params.bmax[2] = 10;
        params.cs = .1;
        params.ch = .1;
        params.walkableHeight = 2;
        params.walkableRadius = .2;
        params.walkableClimb = .5;
        params.buildBvTree = true;
        unsigned char* data = nullptr;
        int size = 0;
        require(dtCreateNavMeshData(&params, &data, &size), "create inset tile");
        auto handle = create ? tc_navmesh_create(uuid) : tc_navmesh_find(uuid);
        auto* mesh = tc_navmesh_get(handle);
        require(mesh != nullptr, "find asset for same UUID reload");
        tc_navmesh_tile registered{0, 0, 0, data, size_t(size)};
        require(tc_navmesh_set_tiles(mesh, &registered, 1), "register inset tile");
        dtFree(data);
    }
    Entity entity(TcSceneRef scene, const char* name) {
        Entity result = Entity::create(tc_scene_entity_pool(scene.handle()), name);
        scene.add_entity(result);
        return result;
    }
    Vec3f world(Entity entity, Vec3 point) {
        auto p = entity.transform().transform_point(point);
        return {float(p.x), float(p.y), float(p.z)};
    }
    double path_length(const PathfindingWorldPathResult& result) {
        double length = 0;
        for (size_t i = 1; i < result.path.points.size(); ++i)
            length += (result.path.points[i].point - result.path.points[i - 1].point).norm();
        return length;
    }
    void complete(const PathfindingWorldPathResult& result, Vec3f end, double expected_length) {
        require(result.success && !result.path.partial, "expected complete surface seam path");
        require(!result.path.points.empty(), "complete route contains points");
        near((result.path.points.back().point - end).norm(), 0, "route reaches destination");
        near(path_length(result), expected_length, "route preserves analytical intrinsic length");
        for (const auto& point : result.path.points)
            require(!point.off_mesh_connection && !point.linear_segment, "seam remains an ordinary surface path");
        require(!result.spans.empty(), "surface path retains owner spans");
        for (const auto& span : result.spans)
            require(span.entity.valid() && span.component != nullptr, "span retains owning entity and component");
    }
    void incomplete(const PathfindingWorldPathResult& result, const char* message) {
        require(!result.success || result.path.partial, message);
    }
} // namespace
int main() {
    tc_entity_pool_registry_init();
    tc_scene_pool_init();
    tc_scene_ext_registry_init();
    register_builtin_scene_component_types();
    tc_navmesh_init();
    register_builtin_navmesh_component_types();
    tile("world-seam-inset", 2, true);
    auto scene = TcSceneRef::create("world-seams");
    auto parent = entity(scene, "moving-station");
    auto a = entity(scene, "panel-a"), b = entity(scene, "panel-b");
    for (auto e : {a, b}) {
        e.transform().set_parent(parent.transform());
        auto* nav = new DetourPathfindingWorldComponent;
        nav->navmesh_uuid = "world-seam-inset";
        e.add_component(nav);
    }
    GeneralPose3 pose_b;
    pose_b.lin = {10, 0, 0};
    b.transform().set_local_pose(pose_b);
    auto seam_entity = entity(scene, "panel-seam");
    auto* seam = new WorldNavMeshSeamComponent;
    seam->start_surface = a;
    seam->end_surface = b;
    seam->start_a = {10, 0, 0};
    seam->start_b = {10, 10, 0};
    seam->end_a = {0, 0, 0};
    seam->end_b = {0, 10, 0};
    seam->max_extension = .75;
    seam_entity.add_component(seam);
    auto* navigation = PathfindingWorld::ensure_scene(scene.handle());
    navigation->rebuild_from_scene();
    auto forward = [&]() {
        return navigation->find_detailed_path_world(world(a, {1, 2, 0}), world(b, {9, 6, 0}));
    };
    const double expected_length = std::hypot(18., 4.);
    auto route = forward();
    complete(route, world(b, {9, 6, 0}), expected_length);
    bool crossed = false;
    for (const auto& point : route.path.points) {
        if (std::abs(point.point.x - 10) < 1e-4) {
            near(point.point.y, 4, "crossing is optimized along seam, not fixed at its midpoint");
            crossed = true;
        }
    }
    require(crossed, "route emits crossing of virtual bisector edge");
    seam->bidirectional = false;
    incomplete(navigation->find_detailed_path_world(world(b, {9, 6, 0}), world(a, {1, 2, 0})),
               "one-way seam cannot be traversed in reverse");
    complete(forward(), world(b, {9, 6, 0}), expected_length);
    seam->bidirectional = true;
    seam->set_enabled(false);
    incomplete(forward(), "disabled seam leaves panels disconnected");
    seam->set_enabled(true);
    complete(forward(), world(b, {9, 6, 0}), expected_length);

    // Replacing bytes under the same identity must invalidate both the Detour
    // session and assembled graph; these new boundaries exceed seam reach.
    tile("world-seam-inset", 20, false);
    incomplete(forward(), "same UUID resource reload invalidates old seam connectivity");
    tile("world-seam-inset", 2, false);
    complete(forward(), world(b, {9, 6, 0}), expected_length);

    pose_b.ang = Quat::from_axis_angle({0, 1, 0}, 1.1);
    b.transform().set_local_pose(pose_b);
    complete(forward(), world(b, {9, 6, 0}), expected_length);
    GeneralPose3 parent_pose;
    parent_pose.lin = {43, 7, -11};
    parent_pose.ang = Quat::from_axis_angle(Vec3{1, 2, 3}.normalized(), 1.2);
    parent.transform().set_local_pose(parent_pose);
    complete(forward(), world(b, {9, 6, 0}), expected_length);

    // A query on an excluded wall must not silently snap to nearby ground.
    tile("wall-area", 2, true, 12);
    auto wall_scene = TcSceneRef::create("wall-area-policy");
    auto floor = entity(wall_scene, "floor"), wall = entity(wall_scene, "wall");
    auto* floor_nav = new DetourPathfindingWorldComponent;
    floor_nav->navmesh_uuid = "world-seam-inset";
    floor.add_component(floor_nav);
    auto* wall_nav = new DetourPathfindingWorldComponent;
    wall_nav->navmesh_uuid = "wall-area";
    wall.add_component(wall_nav);
    GeneralPose3 wall_pose;
    wall_pose.ang = Quat::from_axis_angle({1, 0, 0}, 1.5707963267948966);
    wall.transform().set_local_pose(wall_pose);
    auto* wall_navigation = PathfindingWorld::ensure_scene(wall_scene.handle());
    wall_navigation->rebuild_from_scene();
    const auto wall_start = world(wall, {5, 1, 0});
    const auto wall_end = world(wall, {5, 2, 0});
    complete(wall_navigation->find_detailed_path_world(wall_start, wall_end), wall_end, 1);
    PathfindingWorldQueryOptions forbidden;
    forbidden.traversal.area_mask &= ~(uint64_t{1} << 12);
    require(!wall_navigation->find_detailed_path_world(world(floor, {5, 5, 0}), wall_start, forbidden).success,
            "excluded nearest wall destination must not snap to nearby allowed floor");
    require(!wall_navigation->find_detailed_path_world(wall_start, world(floor, {5, 5, 0}), forbidden).success,
            "excluded nearest wall start must not snap to nearby allowed floor");
    complete(wall_navigation->find_detailed_path_world(wall_start, wall_end), wall_end, 1);
    complete(wall_navigation->find_detailed_path_world(world(floor, {5, 5, 0}), world(floor, {6, 5, 0}), forbidden),
             world(floor, {6, 5, 0}),
             1);
    wall_scene.destroy();

    scene.destroy();
    tc_navmesh_shutdown();
    tc_scene_pool_shutdown();
    tc_scene_ext_registry_shutdown();
    tc_entity_pool_registry_shutdown();
    return 0;
}
