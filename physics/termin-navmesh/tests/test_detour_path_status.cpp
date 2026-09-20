#include <DetourAlloc.h>
#include <DetourNavMeshBuilder.h>
#include <termin/navmesh/detour_query_session.hpp>

#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace {
    void require(bool condition, const char* message) {
        if (!condition) {
            std::fprintf(stderr, "%s\n", message);
            std::abort();
        }
    }

    void load_navmesh(termin::DetourQuerySession& query) {
        // Three connected squares form an L; the fourth square is an island.
        const unsigned short vertices[] = {
            0,0,0, 10,0,0, 10,0,10, 0,0,10,
            20,0,0, 20,0,10, 20,0,20, 10,0,20,
            30,0,0, 40,0,0, 40,0,10, 30,0,10,
        };
        constexpr unsigned short boundary = 0xffff;
        const unsigned short polygons[] = {
            0,1,2,3, boundary,1,boundary,boundary,
            1,4,5,2, boundary,boundary,2,0,
            2,5,6,7, 1,boundary,boundary,boundary,
            8,9,10,11, boundary,boundary,boundary,boundary,
        };
        const unsigned short flags[] = {1,1,1,1};
        const unsigned char areas[] = {1,1,1,1};
        dtNavMeshCreateParams params{};
        params.verts = vertices;
        params.vertCount = 12;
        params.polys = polygons;
        params.polyCount = 4;
        params.polyFlags = flags;
        params.polyAreas = areas;
        params.nvp = 4;
        params.bmax[0] = 40;
        params.bmax[1] = 1;
        params.bmax[2] = 20;
        params.cs = 1;
        params.ch = 1;
        params.walkableHeight = 2;
        params.walkableRadius = 0.2f;
        params.walkableClimb = 0.5f;
        params.buildBvTree = true;
        unsigned char* data = nullptr;
        int size = 0;
        require(dtCreateNavMeshData(&params, &data, &size), "tile creation failed");
        require(query.load_single_tile_data(data, size, "path-status-test"), "tile load failed");
        dtFree(data);
    }

    void require_path(const termin::DetourPathResult& path, bool partial, const char* message) {
        require(path.success && !path.points.empty(), "expected usable path");
        require(path.partial == partial, message);
    }
}

int main() {
    termin::DetourQuerySession query;
    load_navmesh(query);
    const termin::Vec3f start{1,1,0};
    const termin::Vec3f end{19,19,0};
    require_path(query.find_detailed_path(start, end), false, "connected path must be complete");

    const auto snapped = query.find_detailed_path(start, {20.5f,19,0.3f});
    require_path(snapped, false, "snapped endpoint must not mark a connected path partial");
    require(std::fabs(snapped.points.back().point.x - 20.0f) < 0.001f, "endpoint was not snapped");

    require_path(query.find_detailed_path(start, {35,5,0}), true, "disconnected island must be partial");

    query.max_polys = 1;
    require_path(query.find_detailed_path(start, end), true, "truncated corridor must be partial");
    query.max_polys = 256;
    query.max_straight_path = 2;
    require_path(query.find_detailed_path(start, end), true, "truncated corner path must be partial");
    require_path(query.find_detailed_path(start, {5,5,0}), false,
                 "complete path exactly filling straight buffer must remain complete");

    query.max_straight_path = 256;
    termin::Pose3 frame;
    frame.lin = {100,200,3};
    require_path(query.find_detailed_path_world(frame, {101,201,3}, {119,219,3}), false,
                 "world transform lost complete status");
    const auto partial_world = query.find_detailed_path_world(frame, {101,201,3}, {135,205,3});
    require_path(partial_world, true, "world transform lost partial status");
    require(partial_world.points.front().point.x > 100, "world points were not transformed");
    require(!query.find_detailed_path(start, {1000,1000,0}).success,
            "missing destination polygon must fail");
    return 0;
}
