#pragma once

// Debug data captured during Recast navmesh building.
// Each stage of the pipeline can be visualized separately.

#include <vector>
#include <cstdint>
#include <optional>

namespace termin {

// Span in a heightfield column (voxel range)
struct RecastSpan {
    uint16_t smin;  // bottom of span
    uint16_t smax;  // top of span
    uint8_t area;   // area type (0 = unwalkable, 63 = walkable)
};

// Debug data from Recast build stages
struct RecastDebugData {
    // Stage 1: Heightfield (after rasterization + filtering)
    struct Heightfield {
        int width = 0;
        int height = 0;
        float cs = 0.0f;  // cell size XZ
        float ch = 0.0f;  // cell height Y
        float bmin[3] = {0, 0, 0};
        float bmax[3] = {0, 0, 0};

        // Spans per cell: spans[z * width + x] = list of spans in that column
        std::vector<std::vector<RecastSpan>> spans;

        void clear() {
            width = height = 0;
            spans.clear();
        }
    };

    // Stage 2: Compact heightfield (after erosion, distance field, regions)
    struct CompactHeightfield {
        int width = 0;
        int height = 0;
        int span_count = 0;
        float cs = 0.0f;
        float ch = 0.0f;
        float bmin[3] = {0, 0, 0};
        float bmax[3] = {0, 0, 0};

        // Per-span data (indexed by span index, not by cell)
        std::vector<uint16_t> y;          // span height
        std::vector<uint16_t> distances;  // distance to border
        std::vector<uint16_t> regions;    // region ID
        std::vector<uint8_t> areas;       // area type

        // Cell index: cells[z * width + x] = (first_span_index, span_count)
        std::vector<std::pair<uint32_t, uint8_t>> cells;

        void clear() {
            width = height = span_count = 0;
            y.clear();
            distances.clear();
            regions.clear();
            areas.clear();
            cells.clear();
        }
    };

    // Stage 3: Contours
    struct Contour {
        // Simplified contour vertices: (x, y, z, region_id) per vertex
        // Coordinates are in voxel space
        std::vector<int32_t> verts;
        int nverts = 0;

        // Raw (unsimplified) contour vertices
        std::vector<int32_t> raw_verts;
        int nraw_verts = 0;

        uint16_t region = 0;
        uint8_t area = 0;
    };

    struct ContourSet {
        std::vector<Contour> contours;
        float cs = 0.0f;
        float ch = 0.0f;
        float bmin[3] = {0, 0, 0};
        float bmax[3] = {0, 0, 0};

        void clear() {
            contours.clear();
        }
    };

    // Stage 4: Polygon mesh (final result)
    struct PolyMesh {
        // Vertices: (x, y, z) in voxel coordinates, packed as uint16
        std::vector<uint16_t> verts;
        int nverts = 0;

        // Polygons: indices into verts, nvp values per polygon
        // Unused slots filled with 0xFFFF
        std::vector<uint16_t> polys;
        int npolys = 0;
        int nvp = 0;  // max verts per polygon

        // Per-polygon data
        std::vector<uint16_t> regions;
        std::vector<uint16_t> flags;
        std::vector<uint8_t> areas;

        float cs = 0.0f;
        float ch = 0.0f;
        float bmin[3] = {0, 0, 0};
        float bmax[3] = {0, 0, 0};

        void clear() {
            verts.clear();
            polys.clear();
            regions.clear();
            flags.clear();
            areas.clear();
            nverts = npolys = nvp = 0;
        }
    };

    // Stage 5: Detail mesh (optional, for height accuracy)
    struct PolyMeshDetail {
        // Sub-meshes: (vert_base, vert_count, tri_base, tri_count) per polygon
        std::vector<uint32_t> meshes;
        int nmeshes = 0;

        // Detail vertices (x, y, z) as float
        std::vector<float> verts;
        int nverts = 0;

        // Detail triangles: (v0, v1, v2, flags) as uint8
        std::vector<uint8_t> tris;
        int ntris = 0;

        void clear() {
            meshes.clear();
            verts.clear();
            tris.clear();
            nmeshes = nverts = ntris = 0;
        }
    };

    // Captured data (optional - only filled if capture_X is enabled)
    std::optional<Heightfield> heightfield;
    std::optional<CompactHeightfield> compact;
    std::optional<ContourSet> contours;
    std::optional<PolyMesh> poly_mesh;
    std::optional<PolyMeshDetail> detail_mesh;

    void clear() {
        heightfield.reset();
        compact.reset();
        contours.reset();
        poly_mesh.reset();
        detail_mesh.reset();
    }
};

} // namespace termin
