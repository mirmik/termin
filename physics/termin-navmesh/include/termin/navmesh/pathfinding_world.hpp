#pragma once

#include <cstddef>
#include <limits>
#include <memory>
#include <string>
#include <tuple>
#include <vector>

#include <termin/entity/entity.hpp>
#include <termin/navmesh/detour_pathfinding_world_component.hpp>
#include <termin/navmesh/surface_navigation.hpp>
#include <termin/navmesh/tc_pathfinding_world.h>

namespace termin {
    class WorldNavMeshLinkComponent;
    class WorldNavMeshSeamComponent;
    struct SurfaceWorldCache;

    struct TERMIN_NAVMESH_COMPONENTS_API PathfindingWorldQueryOptions {
        bool navmesh_precast = true;
        SurfaceTraversalPolicy traversal;
    };

    struct TERMIN_NAVMESH_COMPONENTS_API PathfindingWorldCandidate {
        Entity entity;
        DetourPathfindingWorldComponent* component = nullptr;
        Pose3 bake_frame;
        DetourClosestPointResult start_closest;
        DetourClosestPointResult end_closest;
        double start_distance_sq = std::numeric_limits<double>::infinity();
        double end_distance_sq = std::numeric_limits<double>::infinity();

        bool valid() const;
        std::string entity_name() const;
        std::string navmesh_uuid() const;
        std::tuple<int, double, double> score() const;
    };

    struct TERMIN_NAVMESH_COMPONENTS_API PathfindingWorldPointCandidate {
        Entity entity;
        DetourPathfindingWorldComponent* component = nullptr;
        Pose3 bake_frame;
        DetourClosestPointResult closest;
        double distance_sq = std::numeric_limits<double>::infinity();

        bool valid() const;
        std::string entity_name() const;
        std::string navmesh_uuid() const;
        std::tuple<int, double> score() const;
    };

    struct TERMIN_NAVMESH_COMPONENTS_API PathfindingWorldPathSpan {
        Entity entity;
        DetourPathfindingWorldComponent* component = nullptr;
        Pose3 bake_frame;
        // Inclusive indices in the concatenated world-space polyline.
        size_t point_begin = 0;
        size_t point_end = 0;
        uint64_t poly_ref = 0;
        uint64_t generation = 0;
        Vec3 normal{0, 0, 1};
    };

    struct TERMIN_NAVMESH_COMPONENTS_API PathfindingWorldPathResult {
        bool success = false;
        PathfindingWorldCandidate candidate;
        DetourPathResult path;
        std::vector<PathfindingWorldPathSpan> spans;
    };

    class TERMIN_NAVMESH_COMPONENTS_API PathfindingWorld {
    private:
        struct Entry {
            tc_entity_handle owner = TC_ENTITY_HANDLE_INVALID;
            DetourPathfindingWorldComponent* component = nullptr;
        };
        tc_scene_handle scene_ = TC_SCENE_HANDLE_INVALID;
        std::vector<Entry> entries_;
        struct LinkEntry {
            tc_entity_handle owner = TC_ENTITY_HANDLE_INVALID;
            WorldNavMeshLinkComponent* component = nullptr;
        };
        std::vector<LinkEntry> links_;
        struct SeamEntry {
            tc_entity_handle owner = TC_ENTITY_HANDLE_INVALID;
            WorldNavMeshSeamComponent* component = nullptr;
        };
        std::vector<SeamEntry> seams_;
        std::shared_ptr<SurfaceWorldCache> surface_cache_;

    public:
        static PathfindingWorld* from_scene(tc_scene_handle scene);
        static PathfindingWorld* ensure_scene(tc_scene_handle scene);

        PathfindingWorld() = default;

        void set_scene(tc_scene_handle scene);
        tc_scene_handle scene() const {
            return scene_;
        }

        void add(DetourPathfindingWorldComponent* component);
        void remove(DetourPathfindingWorldComponent* component);
        bool contains(DetourPathfindingWorldComponent* component) const;
        void rebuild_from_scene();
        void add_link(WorldNavMeshLinkComponent* component);
        void remove_link(WorldNavMeshLinkComponent* component);
        void add_seam(WorldNavMeshSeamComponent* component);
        void remove_seam(WorldNavMeshSeamComponent* component);

        size_t size() const;

        std::vector<PathfindingWorldPointCandidate> candidates_for_world_point(const Vec3f& point);

        bool find_best_candidate_world_point(const Vec3f& point, PathfindingWorldPointCandidate& out_candidate);

        std::vector<PathfindingWorldCandidate> candidates_for_world_points(const Vec3f& start, const Vec3f& end);

        bool find_best_candidate_world(const Vec3f& start, const Vec3f& end, PathfindingWorldCandidate& out_candidate);

        PathfindingWorldPathResult find_detailed_path_world(const Vec3f& start,
                                                            const Vec3f& end,
                                                            const PathfindingWorldQueryOptions& options = {});

    private:
        PathfindingWorldPathResult
        find_surface_path_world(const Vec3f& start, const Vec3f& end, const PathfindingWorldQueryOptions& options);
        void prune_invalid_entries();
        static double distance_sq(const Vec3f& a, const Vec3f& b);
        static bool same_owner_scene(const Entity& entity, tc_scene_handle scene);
    };

} // namespace termin
