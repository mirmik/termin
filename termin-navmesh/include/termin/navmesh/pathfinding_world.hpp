#pragma once

#include <array>
#include <cstddef>
#include <limits>
#include <string>
#include <tuple>
#include <vector>

#include <termin/entity/entity.hpp>
#include <termin/navmesh/detour_pathfinding_world_component.hpp>
#include <termin/navmesh/tc_pathfinding_world.h>

namespace termin {

struct TERMIN_NAVMESH_COMPONENTS_API PathfindingWorldQueryOptions {
    bool navmesh_precast = true;
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

struct TERMIN_NAVMESH_COMPONENTS_API PathfindingWorldPathResult {
    bool success = false;
    PathfindingWorldCandidate candidate;
    DetourPathResult path;
};

class TERMIN_NAVMESH_COMPONENTS_API PathfindingWorld {
public:
    static PathfindingWorld* from_scene(tc_scene_handle scene);
    static PathfindingWorld* ensure_scene(tc_scene_handle scene);

    PathfindingWorld() = default;

    void set_scene(tc_scene_handle scene);
    tc_scene_handle scene() const { return scene_; }

    void add(DetourPathfindingWorldComponent* component);
    void remove(DetourPathfindingWorldComponent* component);
    bool contains(DetourPathfindingWorldComponent* component) const;
    void rebuild_from_scene();

    size_t size() const;

    std::vector<PathfindingWorldCandidate> candidates_for_world_points(
        const std::array<float, 3>& start,
        const std::array<float, 3>& end);

    bool find_best_candidate_world(
        const std::array<float, 3>& start,
        const std::array<float, 3>& end,
        PathfindingWorldCandidate& out_candidate);

    PathfindingWorldPathResult find_detailed_path_world(
        const std::array<float, 3>& start,
        const std::array<float, 3>& end,
        const PathfindingWorldQueryOptions& options = {});

private:
    struct Entry {
        tc_entity_handle owner = TC_ENTITY_HANDLE_INVALID;
        DetourPathfindingWorldComponent* component = nullptr;
    };

    tc_scene_handle scene_ = TC_SCENE_HANDLE_INVALID;
    std::vector<Entry> entries_;

    void prune_invalid_entries();
    static double distance_sq(const std::array<float, 3>& a, const std::array<float, 3>& b);
    static bool same_owner_scene(const Entity& entity, tc_scene_handle scene);
};

} // namespace termin
