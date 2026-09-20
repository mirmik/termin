#include <termin/navmesh/pathfinding_world.hpp>

#include <algorithm>
#include <cmath>
#include <termin/navmesh/world_navmesh_link_component.hpp>
#include <termin/navmesh/world_navmesh_seam_component.hpp>

#include <core/tc_entity_pool_registry.h>
#include <tcbase/tc_log.hpp>
#include <termin/navmesh/navmesh_query_space.hpp>
#include <termin/tc_scene.hpp>

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
        const int off_poly_count = (start_closest.over_poly ? 0 : 1) + (end_closest.over_poly ? 0 : 1);
        const double total_distance_sq = start_distance_sq + end_distance_sq;
        const double max_distance_sq = std::max(start_distance_sq, end_distance_sq);
        return {off_poly_count, total_distance_sq, max_distance_sq};
    }

    bool PathfindingWorldPointCandidate::valid() const {
        return entity.valid() && component != nullptr;
    }

    std::string PathfindingWorldPointCandidate::entity_name() const {
        return entity.valid() ? std::string(entity.name()) : std::string();
    }

    std::string PathfindingWorldPointCandidate::navmesh_uuid() const {
        return component ? component->navmesh_uuid : std::string();
    }

    std::tuple<int, double> PathfindingWorldPointCandidate::score() const {
        const int off_poly_count = closest.over_poly ? 0 : 1;
        return {off_poly_count, distance_sq};
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
            tc_log_warn("[PathfindingWorld] ignored component from another scene: entity='%s'", entity.name());
            return;
        }
        if (contains(component)) {
            return;
        }

        entries_.push_back({entity.handle(), component});
        surface_cache_.reset();
    }

    void PathfindingWorld::remove(DetourPathfindingWorldComponent* component) {
        if (!component) {
            return;
        }

        entries_.erase(std::remove_if(entries_.begin(),
                                      entries_.end(),
                                      [component](const Entry& entry) { return entry.component == component; }),
                       entries_.end());
        surface_cache_.reset();
    }

    bool PathfindingWorld::contains(DetourPathfindingWorldComponent* component) const {
        return std::find_if(entries_.begin(), entries_.end(), [component](const Entry& entry) {
                   return entry.component == component;
               }) != entries_.end();
    }

    void PathfindingWorld::rebuild_from_scene() {
        entries_.clear();
        links_.clear();
        seams_.clear();
        surface_cache_.reset();
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
                if (auto* link = dynamic_cast<WorldNavMeshLinkComponent*>(cxx))
                    add_link(link);
                if (auto* seam = dynamic_cast<WorldNavMeshSeamComponent*>(cxx))
                    add_seam(seam);
            }
        }
    }

    size_t PathfindingWorld::size() const {
        return entries_.size();
    }

    std::vector<PathfindingWorldPointCandidate> PathfindingWorld::candidates_for_world_point(const Vec3f& point) {
        prune_invalid_entries();

        std::vector<PathfindingWorldPointCandidate> candidates;
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
                tc_log_warn("[PathfindingWorld] skipped point query world: entity='%s' "
                            "navmesh_uuid='%s' is not ready",
                            entity.name(),
                            entry.component->navmesh_uuid.c_str());
                continue;
            }

            const Pose3 bake_frame = navmesh_bake_frame_from_transform(entity.transform());
            DetourClosestPointResult closest = entry.component->closest_point_world(bake_frame, point);
            if (!closest.success) {
                tc_log_warn("[PathfindingWorld] skipped point query world: entity='%s' "
                            "navmesh_uuid='%s' closest_success=0",
                            entity.name(),
                            entry.component->navmesh_uuid.c_str());
                continue;
            }

            PathfindingWorldPointCandidate candidate;
            candidate.entity = entity;
            candidate.component = entry.component;
            candidate.bake_frame = bake_frame;
            candidate.closest = closest;
            candidate.distance_sq = distance_sq(point, closest.point);
            candidates.push_back(candidate);
        }

        std::sort(
            candidates.begin(), candidates.end(), [](const auto& a, const auto& b) { return a.score() < b.score(); });
        return candidates;
    }

    bool PathfindingWorld::find_best_candidate_world_point(const Vec3f& point,
                                                           PathfindingWorldPointCandidate& out_candidate) {
        std::vector<PathfindingWorldPointCandidate> candidates = candidates_for_world_point(point);
        if (candidates.empty()) {
            return false;
        }

        out_candidate = candidates.front();
        return true;
    }

    std::vector<PathfindingWorldCandidate> PathfindingWorld::candidates_for_world_points(const Vec3f& start,
                                                                                         const Vec3f& end) {
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

            const Pose3 bake_frame = navmesh_bake_frame_from_transform(entity.transform());
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

        std::sort(
            candidates.begin(), candidates.end(), [](const auto& a, const auto& b) { return a.score() < b.score(); });
        return candidates;
    }

    bool PathfindingWorld::find_best_candidate_world(const Vec3f& start,
                                                     const Vec3f& end,
                                                     PathfindingWorldCandidate& out_candidate) {
        std::vector<PathfindingWorldCandidate> candidates = candidates_for_world_points(start, end);
        if (candidates.empty()) {
            return false;
        }

        out_candidate = candidates.front();
        return true;
    }

    PathfindingWorldPathResult PathfindingWorld::find_detailed_path_world(const Vec3f& start,
                                                                          const Vec3f& end,
                                                                          const PathfindingWorldQueryOptions& options) {
        prune_invalid_entries();
        return find_surface_path_world(start, end, options);
    }

    void PathfindingWorld::add_link(WorldNavMeshLinkComponent* component) {
        if (!component || !same_owner_scene(component->entity(), scene_))
            return;
        if (std::any_of(links_.begin(), links_.end(), [component](const auto& e) { return e.component == component; }))
            return;
        links_.push_back({component->entity().handle(), component});
    }

    void PathfindingWorld::remove_link(WorldNavMeshLinkComponent* component) {
        std::erase_if(links_, [component](const auto& e) { return e.component == component; });
    }

    void PathfindingWorld::add_seam(WorldNavMeshSeamComponent* component) {
        if (!component || !same_owner_scene(component->entity(), scene_))
            return;
        if (std::any_of(seams_.begin(), seams_.end(), [component](const auto& e) { return e.component == component; }))
            return;
        seams_.push_back({component->entity().handle(), component});
        surface_cache_.reset();
    }
    void PathfindingWorld::remove_seam(WorldNavMeshSeamComponent* component) {
        std::erase_if(seams_, [component](const auto& e) { return e.component == component; });
        surface_cache_.reset();
    }

    void PathfindingWorld::prune_invalid_entries() {
        std::erase_if(seams_, [this](const SeamEntry& entry) {
            Entity owner(entry.owner);
            return !owner.valid() || !same_owner_scene(owner, scene_);
        });
        std::erase_if(links_, [this](const LinkEntry& entry) {
            Entity owner(entry.owner);
            return !owner.valid() || !same_owner_scene(owner, scene_);
        });
        entries_.erase(std::remove_if(entries_.begin(),
                                      entries_.end(),
                                      [this](const Entry& entry) {
                                          if (!entry.component) {
                                              return true;
                                          }
                                          Entity entity(entry.owner);
                                          return !entity.valid() ||
                                                 (tc_scene_handle_valid(scene_) && !same_owner_scene(entity, scene_));
                                      }),
                       entries_.end());
    }

    double PathfindingWorld::distance_sq(const Vec3f& a, const Vec3f& b) {
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
