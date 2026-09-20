#include <DetourAlloc.h>
#include <DetourNavMeshBuilder.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <termin/entity/unknown_component.hpp>
#include <termin/navmesh/components_bootstrap.hpp>
#include <termin/navmesh/pathfinding_world.hpp>
#include <termin/navmesh/tc_navmesh_registry.h>
#include <termin/navmesh/world_navmesh_link_component.hpp>
#include <termin/tc_scene.hpp>
#include <termin_scene/internal/tc_scene_extension_registry.h>
using namespace termin;
namespace {
    void require(bool c, const char* m) {
        if (!c) {
            std::fprintf(stderr, "%s\n", m);
            std::abort();
        }
    }
    void tile(const char* uuid) {
        const unsigned short vertices[] = {0,  0, 0, 10, 0, 0, 10, 0, 10, 0,  0, 10,
                                           20, 0, 0, 30, 0, 0, 30, 0, 10, 20, 0, 10};
        const unsigned short polygons[] = {
            0, 1, 2, 3, 0xffff, 0xffff, 0xffff, 0xffff, 4, 5, 6, 7, 0xffff, 0xffff, 0xffff, 0xffff};
        const unsigned short flags[] = {1, 1};
        const unsigned char areas[] = {1, 1};
        dtNavMeshCreateParams p{};
        p.verts = vertices;
        p.vertCount = 8;
        p.polys = polygons;
        p.polyCount = 2;
        p.nvp = 4;
        p.polyFlags = flags;
        p.polyAreas = areas;
        p.bmax[0] = 30;
        p.bmax[1] = 1;
        p.bmax[2] = 10;
        p.cs = 1;
        p.ch = 1;
        p.walkableHeight = 2;
        p.walkableRadius = .2;
        p.walkableClimb = .5;
        p.buildBvTree = true;
        unsigned char* data = nullptr;
        int size = 0;
        require(dtCreateNavMeshData(&p, &data, &size), "create tile");
        auto handle = tc_navmesh_create(uuid);
        auto* mesh = tc_navmesh_get(handle);
        tc_navmesh_tile t{0, 0, 0, data, size_t(size)};
        require(tc_navmesh_set_tiles(mesh, &t, 1), "register tile");
        dtFree(data);
    }
    Entity add_entity(TcSceneRef scene, const char* name) {
        Entity e = Entity::create(tc_scene_entity_pool(scene.handle()), name);
        scene.add_entity(e);
        return e;
    }
    Vec3f world(Entity e, Vec3 p) {
        auto v = e.transform().transform_point(p);
        return {float(v.x), float(v.y), float(v.z)};
    }
    void endpoint(const PathfindingWorldPathResult& r, Vec3f p) {
        require(r.success && !r.path.partial, "expected complete cross surface path");
        require((r.path.points.back().point - p).norm() < 1e-4, "wrong route destination");
        for (const auto& v : r.path.points)
            require(!v.off_mesh_connection, "walk seam became gameplay jump");
    }
} // namespace
int main() {
    // Isolated component test: initialize the core facilities without linking
    // the application bootstrap (which itself depends on this module).
    tc_entity_pool_registry_init();
    tc_scene_pool_init();
    tc_scene_ext_registry_init();
    register_builtin_scene_component_types();
    tc_navmesh_init();
    register_builtin_navmesh_component_types();
    tile("world-link-tile");
    auto scene = TcSceneRef::create("world-links");
    auto root = add_entity(scene, "moving-parent");
    auto a = add_entity(scene, "floor-a"), b = add_entity(scene, "floor-b"), c = add_entity(scene, "floor-c");
    for (auto e : {a, b, c}) {
        e.transform().set_parent(root.transform());
        auto* nav = new DetourPathfindingWorldComponent;
        nav->navmesh_uuid = "world-link-tile";
        e.add_component(nav);
    }
    GeneralPose3 pb;
    pb.lin = {10, 0, 0};
    pb.ang = Quat::from_axis_angle({0, 1, 0}, .8);
    b.transform().set_local_pose(pb);
    GeneralPose3 pc;
    pc.lin = {17, 0, -7};
    pc.ang = Quat::from_axis_angle({0, 1, 0}, 1.6);
    c.transform().set_local_pose(pc);
    auto make_link = [&](Entity from, Entity to) {
        auto e = add_entity(scene, "seam");
        auto* l = new WorldNavMeshLinkComponent;
        l->start_surface = from;
        l->end_surface = to;
        l->start_local = {9.8, 5, 0};
        l->end_local = {.2, 5, 0};
        e.add_component(l);
        return l;
    };
    auto* ab = make_link(a, b);
    auto* bc = make_link(b, c);
    auto* w = PathfindingWorld::ensure_scene(scene.handle());
    w->rebuild_from_scene();
    endpoint(w->find_detailed_path_world(world(a, {1, 5, 0}), world(c, {9, 5, 0})), world(c, {9, 5, 0}));
    endpoint(w->find_detailed_path_world(world(c, {9, 5, 0}), world(a, {1, 5, 0})), world(a, {1, 5, 0}));
    GeneralPose3 pr;
    pr.lin = {43, 7, -11};
    pr.ang = Quat::from_axis_angle(Vec3{1, 2, 3}.normalized(), 1.2);
    root.transform().set_local_pose(pr);
    endpoint(w->find_detailed_path_world(world(a, {1, 5, 0}), world(c, {9, 5, 0})), world(c, {9, 5, 0}));
    // Partial Detour legs cannot bridge the disconnected island on surface B.
    ab->end_local = {25, 5, 0};
    auto blocked = w->find_detailed_path_world(world(a, {1, 5, 0}), world(c, {9, 5, 0}));
    require(!blocked.success || blocked.path.partial, "partial intra-surface leg accepted");
    ab->end_local = {.2, 5, 0};
    bc->bidirectional = false;
    auto backwards = w->find_detailed_path_world(world(c, {9, 5, 0}), world(a, {1, 5, 0}));
    require(!backwards.success || backwards.path.partial, "one-way seam traversed backwards");
    bc->end_local = {100, 5, 0};
    auto missing = w->find_detailed_path_world(world(a, {1, 5, 0}), world(c, {9, 5, 0}));
    require(!missing.success || missing.path.partial, "unattached endpoint accepted");
    bc->end_local = {.2, 5, 0};
    bc->bidirectional = true;
    auto* ca = make_link(c, a);
    const auto round_trip = w->find_detailed_path_world(world(c, {9.5, 5, 0}), world(a, {.5, 5, 0}));
    endpoint(round_trip, world(a, {.5, 5, 0}));
    require(round_trip.spans.size() == 3, "closed ring did not choose shortest seam");
    ca->set_enabled(false);
    const auto long_way = w->find_detailed_path_world(world(c, {9.5, 5, 0}), world(a, {.5, 5, 0}));
    endpoint(long_way, world(a, {.5, 5, 0}));
    require(long_way.spans.size() == 5, "disabled seam remained traversable");
    auto* duplicate = new DetourPathfindingWorldComponent;
    duplicate->navmesh_uuid = "world-link-tile";
    b.add_component(duplicate);
    const auto ambiguous = w->find_detailed_path_world(world(a, {1, 5, 0}), world(c, {9, 5, 0}));
    require(!ambiguous.success || ambiguous.path.partial, "ambiguous seam surface was accepted");
    // A fallback on the destination floor must not silently project the origin
    // from another nearby floor and report a complete route.
    ab->set_enabled(false);
    bc->set_enabled(false);
    duplicate->set_enabled(false);
    c.set_enabled(false);
    GeneralPose3 parallel;
    parallel.lin = {0, 0, .2};
    b.transform().set_local_pose(parallel);
    const auto projected_origin = w->find_detailed_path_world(world(a, {1, 5, .05}), world(b, {5, 5, 0}));
    require(projected_origin.success && projected_origin.path.partial,
            "fallback projected origin onto another surface");
    scene.destroy();
    tc_navmesh_shutdown();
    tc_scene_pool_shutdown();
    tc_scene_ext_registry_shutdown();
    tc_entity_pool_registry_shutdown();
    return 0;
}
