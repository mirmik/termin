#pragma once

#include <array>
#include <cstdint>
#include <limits>
#include <string>
#include <termin/geom/vec3.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>
#include <vector>

namespace termin {
    // Coordinates share a rigid reference frame. Every face is convex and planar.
    struct SurfaceFace {
        size_t surface = 0;
        uint64_t generation = 0;
        uint64_t poly_ref = 0;
        unsigned char poly_type = 0;
        unsigned char area = 0;
        unsigned int user_id = 0;
        std::vector<Vec3> vertices;
    };
    struct SurfacePortal {
        size_t from = 0, to = 0;
        Vec3 a, b; // Shared geometric edge, or a point for a typed transition.
    };
    struct TERMIN_NAVMESH_COMPONENTS_API SurfaceGraph {
        std::vector<SurfaceFace> faces;
        std::vector<SurfacePortal> portals;
        std::vector<std::vector<size_t>> outgoing;
        void index();
    };
    // Per-query traversal permissions and relative time per unit distance.
    // Geometry and connectivity remain shared between all actors.
    struct TERMIN_NAVMESH_COMPONENTS_API SurfaceTraversalPolicy {
        uint64_t area_mask = std::numeric_limits<uint64_t>::max();
        std::array<double, 64> area_costs = [] {
            std::array<double, 64> costs{};
            costs.fill(1.0);
            return costs;
        }();

        bool allows(unsigned char area) const {
            return area < area_costs.size() && (area_mask & (uint64_t{1} << area)) != 0;
        }
        // All costs, including disabled areas, must be finite and positive.
        bool valid() const;
    };
    struct SurfaceCorridor {
        bool success = false;
        bool partial = false;
        Vec3 start, end;
        std::vector<size_t> faces;
        std::vector<size_t> portals;
    };
    struct SurfacePathVertex {
        Vec3 point;
        size_t face = 0; // The face supporting the segment ending at this vertex.
    };
    struct SurfacePath {
        bool success = false;
        std::string error;
        std::vector<SurfacePathVertex> points;
    };
    TERMIN_NAVMESH_COMPONENTS_API SurfaceCorridor find_surface_corridor(const SurfaceGraph& graph,
                                                                        size_t start_face,
                                                                        const Vec3& start,
                                                                        size_t end_face,
                                                                        const Vec3& end,
                                                                        const SurfaceTraversalPolicy& traversal = {});
    TERMIN_NAVMESH_COMPONENTS_API SurfacePath straighten_surface_corridor(const SurfaceGraph& graph,
                                                                          const SurfaceCorridor& corridor);
    TERMIN_NAVMESH_COMPONENTS_API Vec3 closest_surface_point(const SurfaceFace& face, const Vec3& point);

    // Explicitly paired boundary segments. Normals point to each walkable side.
    // Extension is restricted by max_extension and the finite edge intervals.
    struct SurfaceSeamInput {
        Vec3 a0, a1, normal_a, interior_a;
        Vec3 b0, b1, normal_b, interior_b;
        double max_extension = 0.75;
        double tolerance = 1e-5;
    };
    struct SurfaceSeamGeometry {
        bool success = false;
        std::string error;
        Vec3 edge0, edge1;
        Vec3 source_a0, source_a1, source_b0, source_b1;
    };
    TERMIN_NAVMESH_COMPONENTS_API SurfaceSeamGeometry extend_surface_seam(const SurfaceSeamInput& input);
} // namespace termin
