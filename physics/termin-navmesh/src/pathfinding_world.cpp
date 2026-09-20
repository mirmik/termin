#include <termin/navmesh/pathfinding_world.hpp>

#include <algorithm>
#include <cmath>
#include <termin/navmesh/world_navmesh_link_component.hpp>

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
    }

    void PathfindingWorld::remove(DetourPathfindingWorldComponent* component) {
        if (!component) {
            return;
        }

        entries_.erase(std::remove_if(entries_.begin(),
                                      entries_.end(),
                                      [component](const Entry& entry) { return entry.component == component; }),
                       entries_.end());
    }

    bool PathfindingWorld::contains(DetourPathfindingWorldComponent* component) const {
        return std::find_if(entries_.begin(), entries_.end(), [component](const Entry& entry) {
                   return entry.component == component;
               }) != entries_.end();
    }

    void PathfindingWorld::rebuild_from_scene() {
        entries_.clear();
        links_.clear();
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
        if (!links_.empty()) {
            auto linked = find_linked_path_world(start, end);
            if (linked.success)
                return linked;
        }
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

            const Vec3f& query_end = options.navmesh_precast ? candidate.end_closest.point : end;
            DetourPathResult path =
                candidate.component->find_detailed_path_world(candidate.bake_frame, start, query_end);
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
            result.spans.push_back(
                {candidate.entity, candidate.component, candidate.bake_frame, 0, result.path.points.size() - 1});
            if (!links_.empty()) {
                // A failed seam route must not masquerade as reaching a target
                // that was projected onto an unrelated local surface.
                const auto starts = candidates_for_world_point(start);
                for (const auto& origin : starts) {
                    if (origin.distance_sq + 1e-6 < candidate.start_distance_sq)
                        result.path.partial = true;
                }
                const auto ends = candidates_for_world_point(end);
                for (const auto& target : ends) {
                    if (target.distance_sq + 1e-6 < candidate.end_distance_sq)
                        result.path.partial = true;
                }
            }
            return result;
        }

        tc_log_warn("[PathfindingWorld] path query failed: all %zu candidates returned empty path", candidates.size());
        return result;
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

    PathfindingWorldPathResult PathfindingWorld::find_linked_path_world(const Vec3f& start, const Vec3f& end) {
        PathfindingWorldPathResult result;
        auto starts = candidates_for_world_point(start);
        auto ends = candidates_for_world_point(end);
        if (starts.empty() || ends.empty())
            return result;
        // In a curved world a remote floor can be directly below a point in its
        // own bake frame. Physical distance, not over_poly, chooses the surface.
        auto nearest = [](const auto& a, const auto& b) {
            return a.distance_sq < b.distance_sq;
        };
        auto start_candidate = *std::min_element(starts.begin(), starts.end(), nearest);
        auto end_candidate = *std::min_element(ends.begin(), ends.end(), nearest);
        struct Node {
            PathfindingWorldPointCandidate surface;
        };
        std::vector<Node> nodes{{start_candidate}, {end_candidate}};
        struct Seam {
            size_t from, to;
        };
        std::vector<Seam> seams;
        auto endpoint = [&](Entity surface, const tc_vec3& local, double radius, PathfindingWorldPointCandidate& out) {
            if (!surface.valid() || !surface.enabled() || !same_owner_scene(surface, scene_))
                return false;
            const Vec3 world = surface.transform().transform_point(Vec3{local.x, local.y, local.z});
            const Vec3f point{float(world.x), float(world.y), float(world.z)};
            double best = radius * radius;
            bool found = false;
            bool ambiguous = false;
            for (const auto& entry : entries_) {
                if (!tc_entity_handle_eq(entry.owner, surface.handle()) || !entry.component->enabled())
                    continue;
                const Pose3 frame = navmesh_bake_frame_from_transform(surface.transform());
                const auto closest = entry.component->closest_point_world(frame, point);
                if (!closest.success)
                    continue;
                const double distance = distance_sq(point, closest.point);
                if (found && std::abs(distance - best) <= 1e-10) {
                    ambiguous = true;
                } else if (distance <= best) {
                    ambiguous = false;
                    out = {surface, entry.component, frame, closest, distance};
                    best = distance;
                    found = true;
                }
            }
            if (ambiguous)
                tc_log_warn("[PathfindingWorld] ambiguous seam surface '%s': multiple equally near Detour components",
                            surface.name());
            return found && !ambiguous;
        };
        for (const auto& entry : links_) {
            Entity owner(entry.owner);
            auto* link = entry.component;
            if (!owner.enabled() || !link->enabled())
                continue;
            PathfindingWorldPointCandidate a, b;
            if (!std::isfinite(link->snap_radius) || link->snap_radius < 0 ||
                !endpoint(link->start_surface, link->start_local, link->snap_radius, a) ||
                !endpoint(link->end_surface, link->end_local, link->snap_radius, b)) {
                tc_log_warn("[PathfindingWorld] ignored seam '%s': missing surface or endpoint outside snap radius",
                            owner.name());
                continue;
            }
            const size_t i = nodes.size();
            nodes.push_back({a});
            nodes.push_back({b});
            seams.push_back({i, i + 1});
            if (link->bidirectional)
                seams.push_back({i + 1, i});
        }
        if (seams.empty())
            return result;
        struct Edge {
            bool evaluated = false;
            double cost = std::numeric_limits<double>::infinity();
            DetourPathResult path;
        };
        const size_t count = nodes.size();
        // Every directed intra-surface leg is evaluated at most once per query.
        std::vector<Edge> edges(count * count);
        for (auto seam : seams) {
            auto& edge = edges[seam.from * count + seam.to];
            edge.evaluated = true;
            edge.path.success = true;
            DetourPathPoint a, b;
            a.point = nodes[seam.from].surface.closest.point;
            b.point = nodes[seam.to].surface.closest.point;
            a.poly_ref = nodes[seam.from].surface.closest.poly_ref;
            // The seam span belongs to its starting surface; the destination
            // polygon reference is provided by the following surface span.
            b.poly_ref = 0;
            edge.path.points = {a, b};
            edge.cost = std::sqrt(distance_sq(a.point, b.point));
        }
        std::vector<double> distances(count, std::numeric_limits<double>::infinity());
        std::vector<size_t> previous(count, count);
        std::vector<bool> visited(count, false);
        distances[0] = 0;
        for (size_t iteration = 0; iteration < count; ++iteration) {
            size_t current = count;
            for (size_t i = 0; i < count; ++i)
                if (!visited[i] && (current == count || distances[i] < distances[current]))
                    current = i;
            if (current == count || !std::isfinite(distances[current]))
                break;
            if (current == 1)
                break;
            visited[current] = true;
            for (size_t next = 0; next < count; ++next) {
                if (visited[next] || next == current)
                    continue;
                auto& edge = edges[current * count + next];
                const auto& a = nodes[current].surface;
                const auto& b = nodes[next].surface;
                if (!edge.evaluated && a.component == b.component) {
                    edge.evaluated = true;
                    edge.path = a.component->find_detailed_path_world(a.bake_frame, a.closest.point, b.closest.point);
                    if (edge.path.success && !edge.path.partial && !edge.path.points.empty()) {
                        edge.cost = 0;
                        for (size_t p = 1; p < edge.path.points.size(); ++p)
                            edge.cost +=
                                std::sqrt(distance_sq(edge.path.points[p - 1].point, edge.path.points[p].point));
                    }
                }
                const double cost = distances[current] + edge.cost;
                if (cost < distances[next]) {
                    distances[next] = cost;
                    previous[next] = current;
                }
            }
        }
        if (!std::isfinite(distances[1]))
            return result;
        std::vector<size_t> route;
        for (size_t i = 1; i != 0; i = previous[i])
            route.push_back(i);
        route.push_back(0);
        std::reverse(route.begin(), route.end());
        for (size_t i = 1; i < route.size(); ++i) {
            const size_t from = route[i - 1], to = route[i];
            const auto& points = edges[from * count + to].path.points;
            const auto& surface = nodes[from].surface;
            const size_t begin = result.path.points.size();
            result.path.points.insert(result.path.points.end(), points.begin(), points.end());
            result.spans.push_back(
                {surface.entity, surface.component, surface.bake_frame, begin, result.path.points.size() - 1});
        }
        // START/END flags belong to the whole route, never an intermediate leg.
        for (auto& point : result.path.points)
            point.flags &= ~3u;
        result.path.points.front().flags |= 1u;
        result.path.points.back().flags |= 2u;
        result.success = result.path.success = true;
        result.candidate = {start_candidate.entity,
                            start_candidate.component,
                            start_candidate.bake_frame,
                            start_candidate.closest,
                            end_candidate.closest,
                            start_candidate.distance_sq,
                            end_candidate.distance_sq};
        return result;
    }

    void PathfindingWorld::prune_invalid_entries() {
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
