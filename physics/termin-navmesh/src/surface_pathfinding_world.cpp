#include <algorithm>
#include <cmath>
#include <tcbase/tc_log.hpp>
#include <termin/navmesh/navmesh_query_space.hpp>
#include <termin/navmesh/pathfinding_world.hpp>
#include <termin/navmesh/surface_graph_builder.hpp>
#include <termin/navmesh/world_navmesh_seam_component.hpp>

namespace termin {
    struct SurfaceWorldCache {
        SurfaceGraph graph;
        std::vector<DetourPathfindingWorldComponent*> components;
        std::vector<uint64_t> generations;
        std::vector<Pose3> frames;
        std::vector<SurfaceGraphSeam> seams;
    };
    namespace {
        Vec3 as_vec(const Vec3f& v) {
            return {v.x, v.y, v.z};
        }
        Vec3f as_float(const Vec3& v) {
            return {float(v.x), float(v.y), float(v.z)};
        }
        bool same(const Vec3& a, const Vec3& b) {
            return (a - b).norm() < 1e-7;
        }
        bool same(const Pose3& a, const Pose3& b) {
            return same(a.lin, b.lin) && same(a.transform_vector({1, 0, 0}), b.transform_vector({1, 0, 0})) &&
                   same(a.transform_vector({0, 1, 0}), b.transform_vector({0, 1, 0}));
        }
        bool same(const SurfaceGraphSeam& a, const SurfaceGraphSeam& b) {
            return a.from == b.from && a.to == b.to && a.bidirectional == b.bidirectional &&
                   a.max_extension == b.max_extension && same(a.start_a, b.start_a) && same(a.start_b, b.start_b) &&
                   same(a.end_a, b.end_a) && same(a.end_b, b.end_b);
        }
    } // namespace
    PathfindingWorldPathResult PathfindingWorld::find_surface_path_world(const Vec3f& start,
                                                                         const Vec3f& end,
                                                                         const PathfindingWorldQueryOptions& options) {
        PathfindingWorldPathResult result;
        (void)options; // Both endpoints snap to the unified traversable surface.
        std::vector<DetourPathfindingWorldComponent*> components;
        std::vector<Entity> entities;
        std::vector<Pose3> world_frames;
        std::vector<SurfaceGraphSource> sources;
        std::vector<uint64_t> generations;
        for (const auto& entry : entries_) {
            Entity entity(entry.owner);
            if (!entity.enabled() || !entry.component->enabled())
                continue;
            const auto* mesh = entry.component->surface_snapshot();
            if (!mesh)
                continue;
            components.push_back(entry.component);
            entities.push_back(entity);
            world_frames.push_back(navmesh_bake_frame_from_transform(entity.transform()));
            generations.push_back(mesh->generation);
            sources.push_back({mesh, {}});
        }
        if (sources.empty()) {
            tc_log_warn("[PathfindingWorld] no available navigation surfaces");
            return result;
        }
        const Pose3 origin = world_frames.front(), inverse = origin.inverse();
        for (size_t i = 0; i < sources.size(); ++i)
            sources[i].frame = inverse * world_frames[i];
        std::vector<SurfaceGraphSeam> seams;
        for (const auto& entry : seams_) {
            auto* s = entry.component;
            if (!Entity(entry.owner).enabled() || !s->enabled())
                continue;
            auto find = [&](Entity e) {
                size_t index = sources.size();
                for (size_t i = 0; i < entities.size(); ++i)
                    if (tc_entity_handle_eq(e.handle(), entities[i].handle())) {
                        if (index != sources.size())
                            return sources.size();
                        index = i;
                    }
                return index;
            };
            if (!s->start_surface.valid() || !s->end_surface.valid())
                continue;
            size_t a = find(s->start_surface), b = find(s->end_surface);
            if (a == sources.size() || b == sources.size()) {
                tc_log_warn("[PathfindingWorld] seam has missing or ambiguous surface");
                continue;
            }
            // Authored coordinates belong to entities, including baked scale.
            auto point = [&](Entity e, tc_vec3 p) {
                return inverse.transform_point(e.transform().transform_point(p));
            };
            seams.push_back({a,
                             b,
                             point(s->start_surface, s->start_a),
                             point(s->start_surface, s->start_b),
                             point(s->end_surface, s->end_a),
                             point(s->end_surface, s->end_b),
                             s->max_extension,
                             s->bidirectional});
        }
        bool rebuild =
            !surface_cache_ || surface_cache_->components != components || surface_cache_->generations != generations;
        if (!rebuild) {
            rebuild = surface_cache_->seams.size() != seams.size();
            for (size_t i = 0; !rebuild && i < sources.size(); ++i)
                rebuild = !same(surface_cache_->frames[i], sources[i].frame);
            for (size_t i = 0; !rebuild && i < seams.size(); ++i)
                rebuild = !same(surface_cache_->seams[i], seams[i]);
        }
        if (rebuild) {
            surface_cache_ = std::make_shared<SurfaceWorldCache>();
            surface_cache_->components = components;
            surface_cache_->generations = generations;
            surface_cache_->seams = seams;
            for (const auto& src : sources)
                surface_cache_->frames.push_back(src.frame);
            surface_cache_->graph = build_surface_graph(sources, seams);
            if (!links_.empty())
                tc_log_warn("[PathfindingWorld] point WorldNavMeshLink declarations are obsolete; author "
                            "WorldNavMeshSeam boundaries");
        }
        const auto& graph = surface_cache_->graph;
        Vec3 a = inverse.transform_point(as_vec(start)), b = inverse.transform_point(as_vec(end));
        auto nearest = [&](Vec3 point, Vec3& snapped) {
            size_t best = graph.faces.size();
            double distance = 1e100;
            for (size_t i = 0; i < graph.faces.size(); ++i) {
                const auto& face = graph.faces[i];
                if (face.poly_type == 1)
                    continue;
                Vec3 closest = closest_surface_point(face, point);
                Vec3 delta = sources[face.surface].frame.inverse_transform_vector(closest - point);
                const Vec3f& ext = components[face.surface]->query_extents;
                if (std::abs(delta.x) > ext.x || std::abs(delta.y) > ext.y || std::abs(delta.z) > ext.z)
                    continue;
                double d = (closest - point).norm();
                if (d < distance) {
                    best = i;
                    distance = d;
                    snapped = closest;
                }
            }
            return best;
        };
        Vec3 sa, sb;
        size_t af = nearest(a, sa), bf = nearest(b, sb);
        if (af == graph.faces.size() || bf == graph.faces.size()) {
            tc_log_warn("[PathfindingWorld] endpoint outside navigation query extents");
            return result;
        }
        auto corridor = find_surface_corridor(graph, af, sa, bf, sb);
        if (!corridor.success) {
            tc_log_warn("[PathfindingWorld] no traversable corridor");
            return result;
        }
        auto path = straighten_surface_corridor(graph, corridor);
        if (!path.success) {
            tc_log_error("[PathfindingWorld] corridor straightening failed: %s", path.error.c_str());
            return result;
        }
        auto output_point = [&](Vec3 p, size_t face) {
            const auto& f = graph.faces[face];
            DetourPathPoint out;
            out.point = as_float(origin.transform_point(p));
            out.poly_ref = f.poly_ref;
            out.poly_type = f.poly_type;
            out.area = f.area;
            out.off_mesh_connection = f.poly_type == 1;
            out.linear_segment = f.poly_type == 2;
            if (out.off_mesh_connection) {
                out.off_mesh_user_id = f.user_id;
                out.flags |= 4;
            }
            if (out.linear_segment) {
                out.linear_user_id = f.user_id;
                out.flags |= 8;
            }
            return out;
        };
        auto surface_normal = [&](size_t face) {
            const auto& f = graph.faces[face];
            const Vec3 up = world_frames[f.surface].transform_vector({0, 0, 1});
            Vec3 normal = up;
            if (f.vertices.size() >= 3)
                normal = origin.transform_vector(
                    (f.vertices[1] - f.vertices[0]).cross(f.vertices[2] - f.vertices[0]).normalized());
            return normal.dot(up) < 0 ? -normal : normal;
        };
        for (size_t i = 1; i < path.points.size(); ++i) {
            size_t face = path.points[i].face, s = graph.faces[face].surface;
            if ((path.points[i].point - path.points[i - 1].point).norm() < 1e-8)
                continue;
            if (result.path.points.empty())
                result.path.points.push_back(output_point(path.points[i - 1].point, face));
            else
                result.path.points.back() = output_point(path.points[i - 1].point, face);
            const size_t begin = result.path.points.size() - 1;
            result.path.points.push_back(output_point(path.points[i].point, face));
            const auto& f = graph.faces[face];
            result.spans.push_back({entities[s],
                                    components[s],
                                    world_frames[s],
                                    begin,
                                    begin + 1,
                                    f.poly_ref,
                                    f.generation,
                                    surface_normal(face)});
        }
        if (result.path.points.empty() && !path.points.empty()) {
            const auto& p = path.points.front();
            size_t s = graph.faces[p.face].surface;
            result.path.points.push_back(output_point(p.point, p.face));
            const auto& f = graph.faces[p.face];
            result.spans.push_back(
                {entities[s], components[s], world_frames[s], 0, 0, f.poly_ref, f.generation, surface_normal(p.face)});
        }
        if (result.path.points.empty())
            return result;
        result.path.points.front().flags |= 1;
        result.path.points.back().flags |= 2;
        result.path.points.back().off_mesh_connection = false;
        result.path.points.back().flags &= ~4u;
        size_t s = graph.faces[af].surface;
        result.candidate.entity = entities[s];
        result.candidate.component = components[s];
        result.candidate.bake_frame = world_frames[s];
        result.candidate.start_closest = {true, true, graph.faces[af].poly_ref, as_float(origin.transform_point(sa))};
        result.candidate.end_closest = {true, true, graph.faces[bf].poly_ref, as_float(origin.transform_point(sb))};
        result.candidate.start_distance_sq = (a - sa).dot(a - sa);
        result.candidate.end_distance_sq = (b - sb).dot(b - sb);
        result.success = result.path.success = true;
        result.path.partial = corridor.partial;
        return result;
    }
} // namespace termin
