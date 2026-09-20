#include <DetourAlloc.h>
#include <DetourNavMesh.h>
#include <DetourNavMeshBuilder.h>
#include <termin/entity/unknown_component.hpp>
#include <termin/navmesh/components_bootstrap.hpp>
#include <termin/navmesh/pathfinding_world.hpp>
#include <termin/navmesh/tc_navmesh_registry.h>
#include <termin/tc_scene.hpp>
#include <termin_scene/internal/tc_scene_extension_registry.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

namespace {
    using namespace termin;
    constexpr unsigned int jump_id = 2001;
    constexpr unsigned int exit_id = 2002;
    constexpr unsigned int rail_id = 1001;

    void require(bool condition, const char* message) {
        if (!condition) {
            std::fprintf(stderr, "public transitions: %s\n", message);
            std::abort();
        }
    }

    void near(Vec3f actual, Vec3f expected, const char* message) {
        if ((actual - expected).norm() > 0.001f) {
            std::fprintf(stderr, "%s: actual=(%f,%f,%f), expected=(%f,%f,%f)\n", message,
                         actual.x, actual.y, actual.z, expected.x, expected.y, expected.z);
            std::abort();
        }
    }

    void update_tile(tc_navmesh_handle resource, bool bidirectional, bool with_linear) {
        const unsigned short right = with_linear ? 20 : 12;
        const unsigned short far_right = right + 10;
        const unsigned short vertices[] = {
            0,0,0, 10,0,0, 10,0,10, 0,0,10,
            right,0,0, far_right,0,0, far_right,0,10, right,0,10,
        };
        const unsigned short polygons[] = {
            0,1,2,3, 0xffff,0xffff,0xffff,0xffff,
            4,5,6,7, 0xffff,0xffff,0xffff,0xffff,
        };
        const unsigned short flags[] = {1,1};
        const unsigned char areas[] = {1,2};
        const float linear_vertices[] = {12,0,5, 18,0,5};
        const unsigned short linear_flags[] = {1};
        const unsigned char linear_areas[] = {7};
        const unsigned int linear_ids[] = {rail_id};
        const float offmesh_vertices[] = {10,0,5, 12,0,5, 18,0,5, 20,0,5};
        const float offmesh_radii[] = {0.75f,0.75f};
        const unsigned short offmesh_flags[] = {1,1};
        const unsigned char offmesh_areas[] = {3,4};
        const unsigned char direction = bidirectional ? DT_OFFMESH_CON_BIDIR : 0;
        const unsigned char offmesh_directions[] = {direction,direction};
        const unsigned int offmesh_ids[] = {jump_id,exit_id};
        dtNavMeshCreateParams params{};
        params.verts = vertices;
        params.vertCount = 8;
        params.polys = polygons;
        params.polyFlags = flags;
        params.polyAreas = areas;
        params.polyCount = 2;
        params.nvp = 4;
        if (with_linear) {
            params.linearSegmentVerts = linear_vertices;
            params.linearSegmentFlags = linear_flags;
            params.linearSegmentAreas = linear_areas;
            params.linearSegmentUserID = linear_ids;
            params.linearSegmentCount = 1;
        }
        params.offMeshConVerts = offmesh_vertices;
        params.offMeshConRad = offmesh_radii;
        params.offMeshConFlags = offmesh_flags;
        params.offMeshConAreas = offmesh_areas;
        params.offMeshConDir = offmesh_directions;
        params.offMeshConUserID = offmesh_ids;
        params.offMeshConCount = with_linear ? 2 : 1;
        params.bmax[0] = far_right;
        params.bmax[1] = 1;
        params.bmax[2] = 10;
        params.cs = params.ch = 1;
        params.walkableHeight = 2;
        params.walkableRadius = 0.5f;
        params.walkableClimb = 1;
        params.buildBvTree = true;
        unsigned char* data = nullptr;
        int size = 0;
        require(dtCreateNavMeshData(&params, &data, &size), "tile creation failed");
        const tc_navmesh_tile registered{0,0,0,data,size_t(size)};
        require(tc_navmesh_set_tiles(tc_navmesh_get(resource), &registered, 1), "tile registration failed");
        dtFree(data);
    }

    void validate_route(const PathfindingWorldPathResult& result, Vec3f start, Vec3f end,
                        DetourPathfindingWorldComponent* component) {
        require(result.success && result.path.success && !result.path.partial, "expected complete route");
        const auto& points = result.path.points;
        require(points.size() >= 2, "route must contain start and destination");
        near(points.front().point, start, "route start changed");
        near(points.back().point, end, "route destination changed");
        require((points.front().flags & DT_STRAIGHTPATH_START) != 0, "start flag missing");
        require((points.back().flags & DT_STRAIGHTPATH_END) != 0, "end flag missing");
        require(!points.back().off_mesh_connection, "destination cannot initiate an offmesh action");
        require(result.spans.size() == points.size() - 1, "every output edge must retain a span");
        for (size_t i = 0; i + 1 < points.size(); ++i) {
            require((points[i + 1].point - points[i].point).norm() > 1e-5f,
                    "typed transitions must not emit duplicate zero-length edges");
            const auto& span = result.spans[i];
            require(span.point_begin == i && span.point_end == i + 1, "span indices must cover their edge");
            require(span.component == component && span.entity.valid(), "span must retain owning component/entity");
            require(span.poly_ref == points[i].poly_ref && span.poly_ref != 0,
                    "span poly ref must describe outgoing edge");
            require(span.generation == component->generation(), "span must retain loaded geometry generation");
            require(std::abs(span.normal.norm() - 1) < 0.001, "span must have a unit normal");
        }
    }

    void validate_ground_ends(const PathfindingWorldPathResult& result) {
        const auto& points = result.path.points;
        require(points.front().poly_type == DT_POLYTYPE_GROUND && !points.front().off_mesh_connection &&
                    !points.front().linear_segment, "initial ground edge acquired transition metadata");
        const auto& last_edge = points[points.size() - 2];
        require(last_edge.poly_type == DT_POLYTYPE_GROUND && !last_edge.off_mesh_connection &&
                    !last_edge.linear_segment, "final ground edge acquired transition metadata");
    }

    size_t count_offmesh_edges(const PathfindingWorldPathResult& result, unsigned int user_id,
                              Vec3f start, Vec3f end) {
        size_t count = 0;
        for (size_t i = 0; i + 1 < result.path.points.size(); ++i) {
            const auto& point = result.path.points[i];
            if (!point.off_mesh_connection || point.off_mesh_user_id != user_id) continue;
            ++count;
            require(point.poly_type == DT_POLYTYPE_OFFMESH_CONNECTION && !point.linear_segment,
                    "offmesh outgoing edge has wrong type");
            require((point.flags & DT_STRAIGHTPATH_OFFMESH_CONNECTION) != 0,
                    "offmesh action flag missing");
            near(point.point, start, "offmesh action begins at wrong attachment");
            near(result.path.points[i + 1].point, end, "offmesh action ends at wrong attachment");
        }
        return count;
    }
}

int main() {
    tc_entity_pool_registry_init();
    tc_scene_pool_init();
    tc_scene_ext_registry_init();
    register_builtin_scene_component_types();
    tc_navmesh_init();
    register_builtin_navmesh_component_types();
    auto resource = tc_navmesh_create("public-surface-transitions");
    auto scene = TcSceneRef::create("public-surface-transitions");
    auto owner = Entity::create(tc_scene_entity_pool(scene.handle()), "navigation");
    scene.add_entity(owner);
    auto* component = new DetourPathfindingWorldComponent;
    component->navmesh_uuid = "public-surface-transitions";
    owner.add_component(component);
    auto* world = PathfindingWorld::ensure_scene(scene.handle());
    world->rebuild_from_scene();

    update_tile(resource, true, false);
    for (bool reverse : {false,true}) {
        const Vec3f start = reverse ? Vec3f{21,5,0} : Vec3f{1,5,0};
        const Vec3f end = reverse ? Vec3f{1,5,0} : Vec3f{21,5,0};
        const auto route = world->find_detailed_path_world(start, end);
        validate_route(route, start, end, component);
        validate_ground_ends(route);
        require(count_offmesh_edges(route, jump_id, reverse ? Vec3f{12,5,0} : Vec3f{10,5,0},
                                    reverse ? Vec3f{10,5,0} : Vec3f{12,5,0}) == 1,
                "one offmesh connection must produce exactly one nonzero action edge");
        for (size_t i = 0; i + 1 < route.path.points.size(); ++i) {
            const auto& point = route.path.points[i];
            require(!point.linear_segment, "ground/offmesh fixture must not introduce linear edges");
            if (point.off_mesh_connection) require(point.off_mesh_user_id == jump_id, "unexpected offmesh action");
        }
    }

    update_tile(resource, false, false);
    const auto forward = world->find_detailed_path_world({1,5,0}, {21,5,0});
    validate_route(forward, {1,5,0}, {21,5,0}, component);
    require(count_offmesh_edges(forward, jump_id, {10,5,0}, {12,5,0}) == 1,
            "one-way forward action must remain traversable");
    const auto blocked = world->find_detailed_path_world({21,5,0}, {1,5,0});
    require(!blocked.success || blocked.path.partial, "one-way offmesh cannot produce complete reverse route");
    for (const auto& point : blocked.path.points)
        require(!point.off_mesh_connection, "blocked reverse query must not invent offmesh action");

    update_tile(resource, true, true);
    for (bool reverse : {false,true}) {
        const Vec3f start = reverse ? Vec3f{29,5,0} : Vec3f{1,5,0};
        const Vec3f end = reverse ? Vec3f{1,5,0} : Vec3f{29,5,0};
        const auto route = world->find_detailed_path_world(start, end);
        validate_route(route, start, end, component);
        validate_ground_ends(route);
        require(count_offmesh_edges(route, jump_id, reverse ? Vec3f{12,5,0} : Vec3f{10,5,0},
                                    reverse ? Vec3f{10,5,0} : Vec3f{12,5,0}) == 1,
                "linear entry action metadata must be retained");
        require(count_offmesh_edges(route, exit_id, reverse ? Vec3f{20,5,0} : Vec3f{18,5,0},
                                    reverse ? Vec3f{18,5,0} : Vec3f{20,5,0}) == 1,
                "linear exit action metadata must be retained");
        float linear_length = 0;
        for (size_t i = 0; i + 1 < route.path.points.size(); ++i) {
            const auto& point = route.path.points[i];
            if (!point.linear_segment) continue;
            require(point.poly_type == DT_POLYTYPE_LINEAR && point.linear_user_id == rail_id && point.area == 7,
                    "linear traversal metadata must retain type/user id/area");
            require(!point.off_mesh_connection && (point.flags & DT_STRAIGHTPATH_LINEAR) != 0,
                    "linear edge must retain linear flag without offmesh action");
            linear_length += (route.path.points[i + 1].point - point.point).norm();
        }
        require(std::abs(linear_length - 6) < 0.001f, "full linear segment must remain LINEAR traversal");
    }

    // A route starting and ending inside the same linear segment retains its semantic type.
    const auto on_rail = world->find_detailed_path_world({13,5,0}, {17,5,0});
    validate_route(on_rail, {13,5,0}, {17,5,0}, component);
    for (size_t i = 0; i + 1 < on_rail.path.points.size(); ++i)
        require(on_rail.path.points[i].linear_segment && on_rail.path.points[i].linear_user_id == rail_id &&
                    !on_rail.path.points[i].off_mesh_connection, "same-linear route lost traversal metadata");

    scene.destroy();
    tc_navmesh_shutdown();
    tc_scene_pool_shutdown();
    tc_scene_ext_registry_shutdown();
    tc_entity_pool_registry_shutdown();
    return 0;
}
