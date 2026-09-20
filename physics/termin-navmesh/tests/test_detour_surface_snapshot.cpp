#include <DetourAlloc.h>
#include <DetourNavMesh.h>
#include <DetourNavMeshBuilder.h>
#include <termin/navmesh/detour_pathfinding_world_component.hpp>
#include <termin/navmesh/tc_navmesh_registry.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <set>
#include <vector>

namespace {
    using namespace termin;

    void require(bool condition, const char* message) {
        if (!condition) {
            std::fprintf(stderr, "%s\n", message);
            std::abort();
        }
    }

    void require_point(Vec3f point, Vec3f expected, const char* message) {
        if ((point - expected).norm() > 0.001f) {
            std::fprintf(stderr,
                         "%s: actual=(%f,%f,%f) expected=(%f,%f,%f)\n",
                         message,
                         point.x,
                         point.y,
                         point.z,
                         expected.x,
                         expected.y,
                         expected.z);
            std::abort();
        }
    }

    std::vector<unsigned char> make_tile(float elevation = 0) {
        const unsigned short vertices[] = {0, 0, 0, 10, 0, 0, 10, 0, 10, 0, 0, 10};
        const unsigned short polygons[] = {0, 1, 2, 3, 0xffff, 0xffff, 0xffff, 0xffff};
        const unsigned short flags[] = {5};
        const unsigned char areas[] = {2};
        // The detail surface has an interior raised vertex absent from the coarse polygon.
        const unsigned int detail_meshes[] = {0, 5, 0, 4};
        const float detail_vertices[] = {
            0,
            elevation,
            0,
            10,
            elevation,
            0,
            10,
            elevation,
            10,
            0,
            elevation,
            10,
            5,
            elevation + 0.25f,
            5,
        };
        const unsigned char detail_triangles[] = {0, 1, 4, 1, 1, 2, 4, 1, 2, 3, 4, 1, 3, 0, 4, 1};
        const float linear_vertices[] = {
            12,
            elevation,
            5,
            15,
            elevation,
            5,
            16,
            elevation,
            5,
            20,
            elevation,
            5,
        };
        const unsigned short linear_flags[] = {1, 1};
        const unsigned char linear_areas[] = {7, 8};
        const unsigned int linear_ids[] = {1001, 1002};
        // Deliberately one-way and attached inside both segments, at distinct positions.
        const dtLinearLink linear_links[] = {{1, 2, 32768, 49152, 0, {0, 0, 0}}};
        const float offmesh_vertices[] = {10, elevation, 5, 12, elevation, 5};
        const float offmesh_radii[] = {0.75f};
        const unsigned short offmesh_flags[] = {1};
        const unsigned char offmesh_areas[] = {3};
        const unsigned char offmesh_directions[] = {DT_OFFMESH_CON_BIDIR};
        const unsigned int offmesh_ids[] = {2001};
        dtNavMeshCreateParams params{};
        params.verts = vertices;
        params.vertCount = 4;
        params.polys = polygons;
        params.polyFlags = flags;
        params.polyAreas = areas;
        params.polyCount = 1;
        params.nvp = 4;
        params.detailMeshes = detail_meshes;
        params.detailVerts = detail_vertices;
        params.detailVertsCount = 5;
        params.detailTris = detail_triangles;
        params.detailTriCount = 4;
        params.linearSegmentVerts = linear_vertices;
        params.linearSegmentFlags = linear_flags;
        params.linearSegmentAreas = linear_areas;
        params.linearSegmentUserID = linear_ids;
        params.linearSegmentCount = 2;
        params.linearLinks = linear_links;
        params.linearLinkCount = 1;
        params.offMeshConVerts = offmesh_vertices;
        params.offMeshConRad = offmesh_radii;
        params.offMeshConFlags = offmesh_flags;
        params.offMeshConAreas = offmesh_areas;
        params.offMeshConDir = offmesh_directions;
        params.offMeshConUserID = offmesh_ids;
        params.offMeshConCount = 1;
        params.bmin[1] = elevation;
        params.bmax[0] = 21;
        params.bmax[1] = elevation + 1;
        params.bmax[2] = 10;
        params.cs = params.ch = 1;
        params.walkableHeight = 2;
        params.walkableRadius = 0.5f;
        params.walkableClimb = 1;
        params.buildBvTree = true;
        unsigned char* data = nullptr;
        int size = 0;
        require(dtCreateNavMeshData(&params, &data, &size), "snapshot fixture creation failed");
        std::vector<unsigned char> result(data, data + size);
        dtFree(data);
        return result;
    }

    const DetourSurfacePolygon& polygon(const DetourSurfaceSnapshot& mesh, unsigned int user_id) {
        for (const auto& poly : mesh.polygons) {
            if (poly.user_id == user_id)
                return poly;
        }
        require(false, "expected snapshot polygon missing");
        std::abort();
    }

    const DetourSurfaceLink& link(const DetourSurfacePolygon& from, unsigned long long to) {
        for (const auto& portal : from.links) {
            if (portal.poly_ref == to)
                return portal;
        }
        require(false, "expected directed snapshot link missing");
        std::abort();
    }

    void test_snapshot() {
        DetourQuerySession query;
        const auto initial = query.generation();
        require(query.surface_snapshot().polygons.empty(), "new session snapshot must be empty");
        const auto data = make_tile();
        require(query.load_single_tile_data(data, "snapshot-test"), "snapshot tile load failed");
        require(query.generation() > initial, "load must advance geometry generation");
        const auto& mesh = query.surface_snapshot();
        require(std::fabs(mesh.walkable_climb - 1) < 0.001f, "snapshot must retain native walkable climb");
        require(mesh.polygons.size() == 4, "snapshot omitted polygons");
        std::set<unsigned long long> refs;
        for (const auto& poly : mesh.polygons) {
            require(poly.poly_ref != 0 && refs.insert(poly.poly_ref).second, "polygon refs must be nonzero and unique");
        }
        const auto& ground = polygon(mesh, 0);
        require(ground.poly_type == DT_POLYTYPE_GROUND && ground.area == 2 && ground.flags == 5,
                "ground metadata was lost");
        require(ground.vertices.size() == 4 && ground.detail_triangles.size() == 4,
                "detail surface must retain all triangles");
        require_point(ground.vertices[2], {10, 10, 0}, "coarse vertices must use Termin coordinates");
        for (const auto& triangle : ground.detail_triangles) {
            require_point(triangle[2], {5, 5, 0.25f}, "interior detail height was lost");
        }
        const auto closest = query.closest_point({5, 5, 0.3f});
        require(closest.success && closest.poly_ref == ground.poly_ref, "snapshot refs must match query refs");
        const auto& first = polygon(mesh, 1001);
        const auto& second = polygon(mesh, 1002);
        const auto& offmesh = polygon(mesh, 2001);
        require(first.poly_type == DT_POLYTYPE_LINEAR && first.area == 7 && first.flags == 1,
                "linear metadata was lost");
        require(second.poly_type == DT_POLYTYPE_LINEAR && second.area == 8, "second linear metadata was lost");
        require(offmesh.poly_type == DT_POLYTYPE_OFFMESH_CONNECTION && offmesh.area == 3, "offmesh metadata was lost");
        require(first.detail_triangles.empty() && offmesh.detail_triangles.empty(),
                "typed polygons must not invent triangle surfaces");
        const auto& directed = link(first, second.poly_ref);
        require_point(
            directed.left, {12 + 3 * (127 / 255.0f), 5, 0}, "linear source attachment must retain interior t");
        require_point(
            directed.target_left, {16 + 4 * (191 / 255.0f), 5, 0}, "linear target attachment must retain interior t");
        require_point(directed.right, directed.left, "linear source portal must be a point");
        require_point(directed.target_right, directed.target_left, "linear target portal must be a point");
        require(second.links.empty(), "one-way linear link must not invent reverse adjacency");
        require_point(link(ground, offmesh.poly_ref).left, {10, 5, 0}, "ground offmesh attachment is wrong");
        require_point(link(offmesh, ground.poly_ref).left, {10, 5, 0}, "offmesh return attachment is wrong");
        require_point(link(offmesh, first.poly_ref).left, {12, 5, 0}, "offmesh exit attachment is wrong");
        require_point(link(first, offmesh.poly_ref).left, {12, 5, 0}, "linear offmesh attachment is wrong");
        const auto loaded = query.generation();
        query.clear();
        require(query.generation() > loaded && query.surface_snapshot().polygons.empty(),
                "clear must invalidate snapshot and generation");
        const auto cleared = query.generation();
        require(query.load_single_tile_data(data), "reload failed");
        require(query.generation() > cleared, "reload must advance generation even for identical bytes");
    }

    void set_resource(tc_navmesh_handle handle, std::vector<unsigned char>& data) {
        tc_navmesh_tile tile{};
        tile.data = data.data();
        tile.data_size = data.size();
        require(tc_navmesh_set_tiles(tc_navmesh_get(handle), &tile, 1), "resource tile update failed");
    }

    void test_resource_reload() {
        tc_navmesh_init();
        {
            DetourPathfindingWorldComponent component;
            component.navmesh_uuid = "surface-snapshot-reload-test";
            require(component.surface_snapshot() == nullptr, "missing resource must fail to load");
            auto handle = tc_navmesh_create(component.navmesh_uuid.c_str());
            auto data = make_tile();
            set_resource(handle, data);
            const auto* mesh = component.surface_snapshot();
            require(mesh != nullptr && component.is_ready(), "resource creation must recover failed-load cache");
            const auto generation = mesh->generation;
            require_point(polygon(*mesh, 0).vertices[0], {0, 0, 0}, "initial resource geometry wrong");
            data = make_tile(2);
            set_resource(handle, data);
            require(!component.is_ready(), "same UUID with changed payload must invalidate readiness");
            mesh = component.surface_snapshot();
            require(mesh != nullptr && mesh->generation > generation, "resource update must refresh snapshot");
            require_point(polygon(*mesh, 0).vertices[0], {0, 0, 2}, "same UUID reload kept stale geometry");
            const auto updated = mesh->generation;
            const auto updated_version = tc_navmesh_get(handle)->version;
            require(component.surface_snapshot()->generation == updated, "unchanged resource must retain generation");

            // Recycle the registry slot with the same UUID and same loaded version.
            require(tc_navmesh_destroy(handle), "resource destroy failed");
            const auto replacement = tc_navmesh_create(component.navmesh_uuid.c_str());
            require(!tc_navmesh_handle_eq(handle, replacement), "recreated resource must get new handle generation");
            data = make_tile(4);
            set_resource(replacement, data);
            set_resource(replacement, data);
            require(tc_navmesh_get(replacement)->version == updated_version, "replacement fixture version changed");
            require(!component.is_ready(), "replacement handle must invalidate readiness");
            mesh = component.surface_snapshot();
            require(mesh != nullptr && mesh->generation > updated, "handle replacement must refresh snapshot");
            require_point(polygon(*mesh, 0).vertices[0], {0, 0, 4}, "replacement resource kept stale geometry");
            require(tc_navmesh_destroy(replacement), "replacement destroy failed");
            require(component.surface_snapshot() == nullptr, "destroyed resource must not expose old snapshot");
        }
        tc_navmesh_shutdown();
    }
} // namespace

int main() {
    test_snapshot();
    test_resource_reload();
    return 0;
}
