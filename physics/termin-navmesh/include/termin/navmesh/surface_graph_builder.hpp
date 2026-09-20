#pragma once
#include <termin/geom/pose3.hpp>
#include <termin/navmesh/detour_surface_snapshot.hpp>
#include <termin/navmesh/surface_navigation.hpp>
namespace termin {
    struct SurfaceGraphSource {
        const DetourSurfaceSnapshot* mesh = nullptr;
        Pose3 frame;
    };
    struct SurfaceGraphSeam {
        size_t from = 0, to = 0;
        Vec3 start_a, start_b, end_a, end_b; // Same common frame as graph.
        double max_extension = 0.75;
        bool bidirectional = true;
    };
    TERMIN_NAVMESH_COMPONENTS_API SurfaceGraph build_surface_graph(const std::vector<SurfaceGraphSource>& sources,
                                                                   const std::vector<SurfaceGraphSeam>& seams);
} // namespace termin
