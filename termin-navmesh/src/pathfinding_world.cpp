#include <termin/navmesh/pathfinding_world.hpp>

#include <algorithm>

#include <termin/navmesh/navmesh_query_space.hpp>
#include <termin/tc_scene.hpp>
#include <core/tc_entity_pool_registry.h>
#include <tcbase/tc_log.hpp>

namespace termin {

bool PathfindingWorldCandidate::valid() const {
    return entity.valid() && component != nullptr;
}

std::string PathfindingWorldCandidate::entity_name() const {
    return entity.valid() ? std::string(entity.name()) : std::string();
}

std::string PathfindingWorldCandidate::navmesh_uuid() const {
    return component ? component->navmesh_uuid : std::string();
}

std::tuple<int, double, double> PathfindingWorldCandidate::score() const {
    const int off_poly_count =
        (start_closest.over_poly ? 0 : 1) + (end_closest.over_poly ? 0 : 1);
    const double total_distance_sq = start_distance_sq + end_distance_sq;
    const double max_distance_sq = std::max(start_distance_sq, end_distance_sq);
    return {off_poly_count, total_distance_sq, max_distance_sq};
}

PathfindingWorld* PathfindingWorld::from_scene(tc_scene_handle scene) {
    return reinterpret_cast<PathfindingWorld*>(tc_pathfinding_world_get_scene(scene));
}

PathfindingWorld* PathfindingWorld::ensure_scene(tc_scene_handle scene) {
    return reinterpret_cast<PathfindingWorld*>(tc_pathfinding_world_ensure_scene(scene));
}

void PathfindingWorld::set_scene(tc_scene_handle scene) {
    scene_ = scene;
}

void PathfindingWorld::add(DetourPathfindingWorldComponent* component) {
    if (!component) {
        return;
    }

    Entity entity = component->entity();
    if (!entity.valid()) {
        tc_log_warn("[PathfindingWorld] cannot add component without valid owner entity");
        return;
    }
    if (tc_scene_handle_valid(scene_) && !same_owner_scene(entity, scene_)) {
        tc_log_warn("[PathfindingWorld] ignored component from another scene: entity='%s'",
                    entity.name());
        return;
    }
    if (contains(component)) {
        return;
    }

    entries_.push_back({entity.handle(), component});
}

void PathfindingWorld::remove(DetourPathfindingWorldComponent* component) {
    if (!component) {
        return;
    }

    entries_.erase(
        std::remove_if(
            entries_.begin(),
            entries_.end(),
            [component](const Entry& entry) {
                return entry.component == component;
            }),
        entries_.end());
}

bool PathfindingWorld::contains(DetourPathfindingWorldComponent* component) const {
    return std::find_if(entries_.begin(), entries_.end(), [component](const Entry& entry) {
        return entry.component == component;
    }) != entries_.end();
}

void PathfindingWorld::rebuild_from_scene() {
    entries_.clear();
    if (!tc_scene_handle_valid(scene_)) {
        tc_log_warn("[PathfindingWorld] cannot rebuild: scene handle is invalid");
        return;
    }

    tc_entity_pool* pool = tc_scene_entity_pool(scene_);
    if (!pool) {
        tc_log_warn("[PathfindingWorld] cannot rebuild: scene entity pool is unavailable");
        return;
    }

    tc_entity_pool_handle pool_handle = tc_entity_pool_registry_find(pool);
    const size_t capacity = tc_entity_pool_capacity(pool);
    for (size_t i = 0; i < capacity; ++i) {
        tc_entity_id id = tc_entity_pool_id_at(pool, static_cast<uint32_t>(i));
        if (!tc_entity_id_valid(id)) {
            continue;
        }

        Entity entity(tc_entity_handle_make(pool_handle, id));
        const size_t component_count = entity.component_count();
        for (size_t component_index = 0; component_index < component_count; ++component_index) {
            tc_component* raw = entity.component_at(component_index);
            if (!raw || raw->kind != TC_CXX_COMPONENT) {
                continue;
            }

            CxxComponent* cxx = CxxComponent::from_tc(raw);
            auto* pathfinding = dynamic_cast<DetourPathfindingWorldComponent*>(cxx);
            if (pathfinding) {
                add(pathfinding);
            }
        }
    }
}

size_t PathfindingWorld::size() const {
    return entries_.size();
}

std::vector<PathfindingWorldCandidate> PathfindingWorld::candidates_for_world_points(
    const std::array<float, 3>& start,
    const std::array<float, 3>& end)
{
    prune_invalid_entries();

    std::vector<PathfindingWorldCandidate> candidates;
    candidates.reserve(entries_.size());

    for (const Entry& entry : entries_) {
        if (!entry.component) {
            continue;
        }

        Entity entity(entry.owner);
        if (!entity.valid()) {
            continue;
        }
        if (!entity.enabled() || !entry.component->enabled()) {
            continue;
        }
        if (!entry.component->is_ready() && !entry.component->rebuild()) {
            tc_log_warn("[PathfindingWorld] skipped pathfinding world: entity='%s' "
                        "navmesh_uuid='%s' is not ready",
                        entity.name(),
                        entry.component->navmesh_uuid.c_str());
            continue;
        }

        const Pose3 bake_frame = navmesh_bake_frame_from_pose(entity.transform().global_pose());
        DetourClosestPointResult start_closest = entry.component->closest_point_world(bake_frame, start);
        DetourClosestPointResult end_closest = entry.component->closest_point_world(bake_frame, end);
        if (!start_closest.success || !end_closest.success) {
            tc_log_warn("[PathfindingWorld] skipped pathfinding world: entity='%s' "
                        "navmesh_uuid='%s' start_success=%d end_success=%d",
                        entity.name(),
                        entry.component->navmesh_uuid.c_str(),
                        start_closest.success ? 1 : 0,
                        end_closest.success ? 1 : 0);
            continue;
        }

        PathfindingWorldCandidate candidate;
        candidate.entity = entity;
        candidate.component = entry.component;
        candidate.bake_frame = bake_frame;
        candidate.start_closest = start_closest;
        candidate.end_closest = end_closest;
        candidate.start_distance_sq = distance_sq(start, start_closest.point);
        candidate.end_distance_sq = distance_sq(end, end_closest.point);
        candidates.push_back(candidate);
    }

    std::sort(candidates.begin(), candidates.end(), [](const auto& a, const auto& b) {
        return a.score() < b.score();
    });
    return candidates;
}

bool PathfindingWorld::find_best_candidate_world(
    const std::array<float, 3>& start,
    const std::array<float, 3>& end,
    PathfindingWorldCandidate& out_candidate)
{
    std::vector<PathfindingWorldCandidate> candidates = candidates_for_world_points(start, end);
    if (candidates.empty()) {
        return false;
    }

    out_candidate = candidates.front();
    return true;
}

PathfindingWorldPathResult PathfindingWorld::find_detailed_path_world(
    const std::array<float, 3>& start,
    const std::array<float, 3>& end,
    const PathfindingWorldQueryOptions& options)
{
    PathfindingWorldPathResult result;
    std::vector<PathfindingWorldCandidate> candidates = candidates_for_world_points(start, end);
    if (candidates.empty()) {
        tc_log_warn("[PathfindingWorld] path query failed: no DetourPathfindingWorldComponent "
                    "accepted closest-point query");
        return result;
    }

    for (const PathfindingWorldCandidate& candidate : candidates) {
        if (!candidate.component) {
            continue;
        }

        const std::array<float, 3>& query_end =
            options.navmesh_precast ? candidate.end_closest.point : end;
        DetourPathResult path = candidate.component->find_detailed_path_world(
            candidate.bake_frame,
            start,
            query_end);
        if (!path.success || path.points.empty()) {
            tc_log_warn("[PathfindingWorld] path candidate failed: entity='%s' "
                        "navmesh_uuid='%s'",
                        candidate.entity_name().c_str(),
                        candidate.navmesh_uuid().c_str());
            continue;
        }

        result.success = true;
        result.candidate = candidate;
        result.path = std::move(path);
        return result;
    }

    tc_log_warn("[PathfindingWorld] path query failed: all %zu candidates returned empty path",
                candidates.size());
    return result;
}

void PathfindingWorld::prune_invalid_entries() {
    entries_.erase(
        std::remove_if(
            entries_.begin(),
            entries_.end(),
            [this](const Entry& entry) {
                if (!entry.component) {
                    return true;
                }
                Entity entity(entry.owner);
                return !entity.valid() || (tc_scene_handle_valid(scene_) && !same_owner_scene(entity, scene_));
            }),
        entries_.end());
}

double PathfindingWorld::distance_sq(const std::array<float, 3>& a, const std::array<float, 3>& b) {
    const double dx = static_cast<double>(a[0]) - static_cast<double>(b[0]);
    const double dy = static_cast<double>(a[1]) - static_cast<double>(b[1]);
    const double dz = static_cast<double>(a[2]) - static_cast<double>(b[2]);
    return dx * dx + dy * dy + dz * dz;
}

bool PathfindingWorld::same_owner_scene(const Entity& entity, tc_scene_handle scene) {
    if (!entity.valid() || !tc_scene_handle_valid(scene)) {
        return false;
    }
    return tc_scene_handle_eq(entity.scene().handle(), scene);
}

} // namespace termin
