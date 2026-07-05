#include <DetourAlloc.h>
#include <DetourNavMesh.h>
#include <DetourNavMeshBuilder.h>
#include <DetourNavMeshQuery.h>
#include <DetourStatus.h>

#include <cstring>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace {

void require(bool condition, const char* message)
{
    if (!condition) {
        std::fprintf(stderr, "%s\n", message);
        std::abort();
    }
}

void require_near(float actual, float expected, const char* message)
{
    if (std::fabs(actual - expected) > 0.001f) {
        std::fprintf(stderr, "%s: actual=%.6f expected=%.6f\n", message, actual, expected);
        std::abort();
    }
}

float point_distance_sq(const float* a, const float* b)
{
    const float dx = a[0] - b[0];
    const float dy = a[1] - b[1];
    const float dz = a[2] - b[2];
    return dx * dx + dy * dy + dz * dz;
}

void require_no_duplicate_linear_straight_points(const float* points,
                                                 const unsigned char* flags,
                                                 const dtPolyRef* refs,
                                                 int count,
                                                 const char* message)
{
    static const float linearEpsilonSq = 0.01f * 0.01f;
    for (int i = 1; i < count; ++i)
    {
        const bool previousLinear = (flags[i - 1] & DT_STRAIGHTPATH_LINEAR) != 0;
        const bool currentLinear = (flags[i] & DT_STRAIGHTPATH_LINEAR) != 0;
        if (previousLinear && currentLinear && refs[i - 1] == refs[i] &&
            point_distance_sq(&points[(i - 1) * 3], &points[i * 3]) < linearEpsilonSq)
        {
            std::fprintf(stderr, "%s: duplicate indices %d and %d ref=%llu\n",
                         message,
                         i - 1,
                         i,
                         static_cast<unsigned long long>(refs[i]));
            std::abort();
        }
    }
}

dtNavMesh* build_linear_navmesh()
{
    static const unsigned short verts[] = {
        0, 0, 0,
        10, 0, 0,
        10, 0, 10,
        0, 0, 10,
    };
    static const unsigned short polys[] = {
        0, 1, 2, 3,
        0, 0, 0, 0,
    };
    static const unsigned short polyFlags[] = {1};
    static const unsigned char polyAreas[] = {1};

    static const float linearVerts[] = {
        12.0f, 0.0f, 5.0f, 15.0f, 0.0f, 5.0f,
        15.0f, 0.0f, 5.0f, 18.0f, 0.0f, 5.0f,
    };
    static const unsigned short linearFlags[] = {1, 1};
    static const unsigned char linearAreas[] = {7, 7};
    static const unsigned int linearUserIds[] = {1001, 1002};
    static const dtLinearLink linearLinks[] = {
        {1, 2, 65535, 0, DT_LINEAR_LINK_BIDIR, {0, 0, 0}},
    };

    static const float offMeshVerts[] = {
        10.0f, 0.0f, 5.0f,
        12.0f, 0.0f, 5.0f,
    };
    static const float offMeshRadii[] = {0.75f};
    static const unsigned short offMeshFlags[] = {1};
    static const unsigned char offMeshAreas[] = {3};
    static const unsigned char offMeshDirs[] = {DT_OFFMESH_CON_BIDIR};
    static const unsigned int offMeshUserIds[] = {2001};

    dtNavMeshCreateParams params;
    std::memset(&params, 0, sizeof(params));
    params.verts = verts;
    params.vertCount = 4;
    params.polys = polys;
    params.polyFlags = polyFlags;
    params.polyAreas = polyAreas;
    params.polyCount = 1;
    params.nvp = 4;
    params.linearSegmentVerts = linearVerts;
    params.linearSegmentFlags = linearFlags;
    params.linearSegmentAreas = linearAreas;
    params.linearSegmentUserID = linearUserIds;
    params.linearSegmentCount = 2;
    params.linearLinks = linearLinks;
    params.linearLinkCount = 1;
    params.offMeshConVerts = offMeshVerts;
    params.offMeshConRad = offMeshRadii;
    params.offMeshConFlags = offMeshFlags;
    params.offMeshConAreas = offMeshAreas;
    params.offMeshConDir = offMeshDirs;
    params.offMeshConUserID = offMeshUserIds;
    params.offMeshConCount = 1;
    params.bmin[0] = 0.0f;
    params.bmin[1] = -1.0f;
    params.bmin[2] = 0.0f;
    params.bmax[0] = 20.0f;
    params.bmax[1] = 1.0f;
    params.bmax[2] = 10.0f;
    params.walkableHeight = 2.0f;
    params.walkableRadius = 0.5f;
    params.walkableClimb = 1.0f;
    params.cs = 1.0f;
    params.ch = 1.0f;
    params.buildBvTree = true;

    unsigned char* data = nullptr;
    int dataSize = 0;
    require(dtCreateNavMeshData(&params, &data, &dataSize), "dtCreateNavMeshData failed");
    require(data != nullptr, "dtCreateNavMeshData returned null data");
    require(dataSize > 0, "dtCreateNavMeshData returned empty data");

    dtNavMesh* nav = dtAllocNavMesh();
    require(nav != nullptr, "dtAllocNavMesh failed");
    const dtStatus status = nav->init(data, dataSize, DT_TILE_FREE_DATA);
    require(dtStatusSucceed(status), "dtNavMesh::init failed");
    return nav;
}

} // namespace

int main()
{
    dtNavMesh* nav = build_linear_navmesh();

    const dtMeshTile* tile = static_cast<const dtNavMesh*>(nav)->getTile(0);
    require(tile != nullptr, "missing tile");
    require(tile->header != nullptr, "missing tile header");
    require(tile->header->polyCount == 4, "unexpected poly count");
    require(tile->header->linearSegmentCount == 2, "unexpected linear segment count");
    require(tile->header->linearSegmentBase == 1, "unexpected linear segment base");
    require(tile->header->offMeshBase == 3, "unexpected offmesh base");
    require(tile->polys[1].getType() == DT_POLYTYPE_LINEAR, "first linear poly has wrong type");
    require(tile->polys[2].getType() == DT_POLYTYPE_LINEAR, "second linear poly has wrong type");
    require(tile->polys[3].getType() == DT_POLYTYPE_OFFMESH_CONNECTION, "offmesh poly has wrong type");

    dtNavMeshQuery* query = dtAllocNavMeshQuery();
    require(query != nullptr, "dtAllocNavMeshQuery failed");
    require(dtStatusSucceed(query->init(nav, 64)), "dtNavMeshQuery::init failed");

    dtQueryFilter filter;
    filter.setIncludeFlags(0xffff);
    filter.setExcludeFlags(0);

    const float extents[] = {1.0f, 2.0f, 1.0f};
    const float start[] = {5.0f, 0.0f, 5.0f};
    const float end[] = {18.0f, 0.0f, 5.0f};
    float nearestStart[3];
    float nearestEnd[3];
    dtPolyRef startRef = 0;
    dtPolyRef endRef = 0;
    require(dtStatusSucceed(query->findNearestPoly(start, extents, &filter, &startRef, nearestStart)),
            "findNearestPoly start failed");
    require(dtStatusSucceed(query->findNearestPoly(end, extents, &filter, &endRef, nearestEnd)),
            "findNearestPoly end failed");
    require(startRef != 0, "start ref is null");
    require(endRef != 0, "end ref is null");

    const dtMeshTile* endTile = nullptr;
    const dtPoly* endPoly = nullptr;
    require(dtStatusSucceed(nav->getTileAndPolyByRef(endRef, &endTile, &endPoly)),
            "getTileAndPolyByRef end failed");
    require(endPoly->getType() == DT_POLYTYPE_LINEAR, "end ref is not linear");
    const dtLinearSegment* endSegment = nav->getLinearSegmentByRef(endRef);
    require(endSegment != nullptr, "missing end linear segment");
    require(endSegment->userId == 1002, "unexpected end linear segment user id");

    dtPolyRef path[16];
    int pathCount = 0;
    require(dtStatusSucceed(query->findPath(startRef, endRef, nearestStart, nearestEnd, &filter,
                                            path, &pathCount, 16)),
            "findPath failed");
    require(pathCount == 4, "unexpected corridor size");
    require(path[0] == startRef, "path does not start at startRef");
    require(path[3] == endRef, "path does not end at endRef");

    bool hasOffmesh = false;
    int linearCount = 0;
    for (int i = 0; i < pathCount; ++i)
    {
        const dtMeshTile* pathTile = nullptr;
        const dtPoly* pathPoly = nullptr;
        require(dtStatusSucceed(nav->getTileAndPolyByRef(path[i], &pathTile, &pathPoly)),
                "getTileAndPolyByRef path poly failed");
        if (pathPoly->getType() == DT_POLYTYPE_OFFMESH_CONNECTION)
            hasOffmesh = true;
        if (pathPoly->getType() == DT_POLYTYPE_LINEAR)
            linearCount++;
    }
    require(hasOffmesh, "corridor does not include offmesh");
    require(linearCount == 2, "corridor does not include two linear polys");

    float straight[16 * 3];
    unsigned char straightFlags[16];
    dtPolyRef straightRefs[16];
    int straightCount = 0;
    require(dtStatusSucceed(query->findStraightPath(nearestStart, nearestEnd, path, pathCount,
                                                    straight, straightFlags, straightRefs,
                                                    &straightCount, 16, 0)),
            "findStraightPath failed");
    require(straightCount >= 4, "straight path is too short");
    require_no_duplicate_linear_straight_points(straight, straightFlags, straightRefs, straightCount,
                                                "straight path contains duplicate linear points");

    bool hasLinearStraightPoint = false;
    for (int i = 0; i < straightCount; ++i)
    {
        if (straightFlags[i] & DT_STRAIGHTPATH_LINEAR)
            hasLinearStraightPoint = true;
    }
    require(hasLinearStraightPoint, "straight path does not include a linear point");

    dtPolyRef reversePath[16];
    int reversePathCount = 0;
    require(dtStatusSucceed(query->findPath(endRef, startRef, nearestEnd, nearestStart, &filter,
                                            reversePath, &reversePathCount, 16)),
            "reverse findPath failed");
    require(reversePathCount == 4, "unexpected reverse corridor size");
    require(reversePath[0] == endRef, "reverse path does not start at endRef");
    require(reversePath[3] == startRef, "reverse path does not end at startRef");

    float reverseStraight[16 * 3];
    unsigned char reverseStraightFlags[16];
    dtPolyRef reverseStraightRefs[16];
    int reverseStraightCount = 0;
    require(dtStatusSucceed(query->findStraightPath(nearestEnd, nearestStart, reversePath, reversePathCount,
                                                    reverseStraight, reverseStraightFlags, reverseStraightRefs,
                                                    &reverseStraightCount, 16, 0)),
            "reverse findStraightPath failed");
    require(reverseStraightCount >= 4, "reverse straight path is too short");
    require_no_duplicate_linear_straight_points(reverseStraight, reverseStraightFlags, reverseStraightRefs,
                                                reverseStraightCount,
                                                "reverse straight path contains duplicate linear points");

    bool hasReverseOffmeshStraightPoint = false;
    for (int i = 0; i < reverseStraightCount; ++i)
    {
        if (reverseStraightFlags[i] & DT_STRAIGHTPATH_OFFMESH_CONNECTION)
        {
            hasReverseOffmeshStraightPoint = true;
            require_near(reverseStraight[i*3 + 0], 12.0f, "reverse offmesh point x");
            require_near(reverseStraight[i*3 + 1], 0.0f, "reverse offmesh point y");
            require_near(reverseStraight[i*3 + 2], 5.0f, "reverse offmesh point z");

            const dtMeshTile* offmeshTile = nullptr;
            const dtPoly* offmeshPoly = nullptr;
            require(dtStatusSucceed(nav->getTileAndPolyByRef(reverseStraightRefs[i], &offmeshTile, &offmeshPoly)),
                    "reverse offmesh straight ref lookup failed");
            require(offmeshPoly->getType() == DT_POLYTYPE_OFFMESH_CONNECTION,
                    "reverse offmesh straight ref is not offmesh");
        }
    }
    require(hasReverseOffmeshStraightPoint, "reverse straight path does not include offmesh point");

    dtFreeNavMeshQuery(query);
    dtFreeNavMesh(nav);
    return 0;
}
