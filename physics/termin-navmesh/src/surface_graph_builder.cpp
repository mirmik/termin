#include <algorithm>
#include <cmath>
#include <map>
#include <tcbase/tc_log.hpp>
#include <termin/navmesh/surface_graph_builder.hpp>

namespace termin {
    namespace {
        constexpr double eps = 1e-4;
        Vec3 vector(const Vec3f& v) {
            return {v.x, v.y, v.z};
        }
        Vec3 center(const SurfaceFace& f) {
            Vec3 c{};
            for (auto p : f.vertices)
                c += p;
            return c / double(f.vertices.size());
        }
        Vec3 normal(const SurfaceFace& f) {
            return (f.vertices[1] - f.vertices[0]).cross(f.vertices[2] - f.vertices[0]).normalized();
        }
        bool overlap(Vec3 a, Vec3 b, Vec3 c, Vec3 d, Vec3& lo, Vec3& hi) {
            Vec3 u = b - a;
            double length = u.norm();
            if (length < eps)
                return false;
            u = u / length;
            if ((c - a).cross(u).norm() > eps || (d - a).cross(u).norm() > eps)
                return false;
            double t0 = (c - a).dot(u), t1 = (d - a).dot(u);
            double l = std::max(0., std::min(t0, t1)), r = std::min(length, std::max(t0, t1));
            if (r - l < eps)
                return false;
            lo = a + u * l;
            hi = a + u * r;
            return true;
        }
        void join(SurfaceGraph& g, size_t a, size_t b, Vec3 p, Vec3 q, bool reverse = true) {
            g.portals.push_back({a, b, p, q});
            if (reverse)
                g.portals.push_back({b, a, p, q});
        }
        struct Boundary {
            size_t face;
            Vec3 a, b;
        };
        std::vector<Boundary> boundaries(const SurfaceGraph& g) {
            std::vector<Boundary> result;
            for (size_t i = 0; i < g.faces.size(); ++i) {
                const auto& f = g.faces[i];
                if (f.poly_type || f.vertices.size() < 3)
                    continue;
                for (size_t e = 0; e < f.vertices.size(); ++e) {
                    Vec3 a = f.vertices[e], b = f.vertices[(e + 1) % f.vertices.size()], u = b - a;
                    double length = u.norm();
                    if (length < eps)
                        continue;
                    u = u / length;
                    std::vector<std::pair<double, double>> cuts;
                    for (auto pi : g.outgoing[i]) {
                        const auto& p = g.portals[pi];
                        Vec3 l, r;
                        if (overlap(a, b, p.a, p.b, l, r))
                            cuts.push_back({(l - a).dot(u), (r - a).dot(u)});
                    }
                    std::sort(cuts.begin(), cuts.end());
                    double t = 0;
                    for (auto [l, r] : cuts) {
                        if (l - t > eps)
                            result.push_back({i, a + u * t, a + u * l});
                        t = std::max(t, r);
                    }
                    if (length - t > eps)
                        result.push_back({i, a + u * t, b});
                }
            }
            return result;
        }
        // Clip an actual exposed boundary against the authored longitudinal interval.
        bool select_boundary(const Boundary& b, Vec3 a, Vec3 z, double reach, Boundary& out) {
            Vec3 u = z - a;
            double length = u.norm();
            if (length < eps)
                return false;
            u = u / length;
            Vec3 v = b.b - b.a;
            double vl = v.norm();
            if (vl < eps || std::abs(v.dot(u) / vl) < 0.95)
                return false;
            double t0 = (b.a - a).dot(u), t1 = (b.b - a).dot(u);
            double l = std::max(0., std::min(t0, t1)), r = std::min(length, std::max(t0, t1));
            if (r - l < eps)
                return false;
            Vec3 p = b.a + v * ((l - t0) / (t1 - t0)), q = b.a + v * ((r - t0) / (t1 - t0));
            if ((p - (a + u * l)).norm() > reach + eps || (q - (a + u * r)).norm() > reach + eps)
                return false;
            out = {b.face, p, q};
            return true;
        }
        size_t add_strip(SurfaceGraph& g, size_t face, Vec3 a, Vec3 b, Vec3 p, Vec3 q) {
            if ((a - p).norm() < eps && (b - q).norm() < eps)
                return face;
            SurfaceFace f = g.faces[face];
            f.vertices = {a, b, q, p};
            std::vector<Vec3> clean;
            for (auto v : f.vertices)
                if (clean.empty() || (v - clean.back()).norm() > eps)
                    clean.push_back(v);
            if (clean.size() > 1 && (clean.front() - clean.back()).norm() < eps)
                clean.pop_back();
            if (clean.size() < 3)
                return face;
            f.vertices = std::move(clean);
            size_t id = g.faces.size();
            g.faces.push_back(std::move(f));
            join(g, face, id, a, b);
            return id;
        }
    } // namespace
    SurfaceGraph build_surface_graph(const std::vector<SurfaceGraphSource>& sources,
                                     const std::vector<SurfaceGraphSeam>& seams) {
        SurfaceGraph graph;
        using Key = std::pair<size_t, uint64_t>;
        std::map<Key, std::vector<size_t>> faces;
        std::map<Key, const DetourSurfacePolygon*> polygons;
        for (size_t s = 0; s < sources.size(); ++s) {
            const auto& src = sources[s];
            if (!src.mesh)
                continue;
            for (const auto& p : src.mesh->polygons) {
                if (!p.flags)
                    continue;
                Key key{s, p.poly_ref};
                polygons[key] = &p;
                SurfaceFace f;
                f.surface = s;
                f.generation = src.mesh->generation;
                f.poly_ref = p.poly_ref;
                f.poly_type = p.poly_type;
                f.area = p.area;
                f.user_id = p.user_id;
                auto add = [&](const auto& vertices) {
                    f.vertices.clear();
                    for (auto v : vertices)
                        f.vertices.push_back(src.frame.transform_point(vector(v)));
                    if (f.vertices.size() >= 3 &&
                        (f.vertices[1] - f.vertices[0]).cross(f.vertices[2] - f.vertices[0]).norm() < 1e-10)
                        return;
                    faces[key].push_back(graph.faces.size());
                    graph.faces.push_back(f);
                };
                if (!p.poly_type)
                    for (const auto& tri : p.detail_triangles)
                        add(tri);
                else
                    add(p.vertices);
            }
        }
        auto adjacent = [&](size_t a, size_t b) {
            const auto& x = graph.faces[a];
            const auto& y = graph.faces[b];
            if (x.surface != y.surface)
                return false;
            if (x.poly_ref == y.poly_ref)
                return true;
            auto it = polygons.find({x.surface, x.poly_ref});
            if (it == polygons.end())
                return false;
            for (const auto& link : it->second->links)
                if (link.poly_ref == y.poly_ref)
                    return true;
            return false;
        };
        // Ground links delimit accessible edge intervals in the source bake XY
        // plane. Detail sampling may put the two sides at different heights.
        auto clip_link = [&](size_t i, size_t j, Vec3& l, Vec3& r) {
            const auto& a = graph.faces[i];
            const auto& b = graph.faces[j];
            if (a.poly_ref == b.poly_ref)
                return true;
            auto it = polygons.find({a.surface, a.poly_ref});
            if (it == polygons.end())
                return false;
            const Pose3 inv = sources[a.surface].frame.inverse();
            Vec3 ll = inv.transform_point(l), rr = inv.transform_point(r);
            Vec3 delta = rr - ll;
            Vec3 lp = ll, rp = rr;
            lp.z = rp.z = 0;
            for (const auto& link : it->second->links)
                if (link.poly_ref == b.poly_ref) {
                    Vec3 x = vector(link.left), y = vector(link.right);
                    x.z = y.z = 0;
                    Vec3 lo, hi;
                    if (!overlap(lp, rp, x, y, lo, hi))
                        continue;
                    double denom = (rp - lp).dot(rp - lp);
                    double t0 = (lo - lp).dot(rp - lp) / denom, t1 = (hi - lp).dot(rp - lp) / denom;
                    l = sources[a.surface].frame.transform_point(ll + delta * t0);
                    r = sources[a.surface].frame.transform_point(ll + delta * t1);
                    return true;
                }
            return false;
        };
        auto connect_faces = [&](size_t i, size_t j, bool extended = false) {
            const auto& a = graph.faces[i];
            const auto& b = graph.faces[j];
            if (a.poly_type || b.poly_type || a.vertices.size() < 3 || b.vertices.size() < 3)
                return;
            bool ab = adjacent(i, j), ba = adjacent(j, i);
            if (!ab && !ba)
                return;
            for (size_t x = 0; x < a.vertices.size(); ++x)
                for (size_t y = 0; y < b.vertices.size(); ++y) {
                    Vec3 l, r;
                    if (!overlap(a.vertices[x],
                                 a.vertices[(x + 1) % a.vertices.size()],
                                 b.vertices[y],
                                 b.vertices[(y + 1) % b.vertices.size()],
                                 l,
                                 r))
                        continue;
                    Vec3 p = l, q = r;
                    if (ab && (extended || clip_link(i, j, p, q)))
                        join(graph, i, j, p, q, false);
                    p = l;
                    q = r;
                    if (ba && (extended || clip_link(j, i, p, q)))
                        join(graph, j, i, p, q, false);
                }
        };
        const size_t ground_count = graph.faces.size();
        for (size_t i = 0; i < ground_count; ++i)
            for (size_t j = i + 1; j < ground_count; ++j)
                if (graph.faces[i].surface == graph.faces[j].surface)
                    connect_faces(i, j);
        // Detour permits climbable height discontinuities. Represent their actual
        // two boundaries and the planar riser explicitly, rather than disconnecting
        // the graph or flattening height differences into an invisible portal.
        for (size_t i = 0; i < ground_count; ++i)
            for (size_t j = i + 1; j < ground_count; ++j) {
                const SurfaceFace a = graph.faces[i], b = graph.faces[j];
                if (a.surface != b.surface || a.poly_type || b.poly_type || a.poly_ref == b.poly_ref)
                    continue;
                bool ab = adjacent(i, j), ba = adjacent(j, i);
                if (!ab && !ba)
                    continue;
                const auto& src = sources[a.surface];
                const Pose3 inv = src.frame.inverse();
                for (size_t x = 0; x < a.vertices.size(); ++x)
                    for (size_t y = 0; y < b.vertices.size(); ++y) {
                        Vec3 aa = inv.transform_point(a.vertices[x]),
                             az = inv.transform_point(a.vertices[(x + 1) % a.vertices.size()]);
                        Vec3 bb = inv.transform_point(b.vertices[y]),
                             bz = inv.transform_point(b.vertices[(y + 1) % b.vertices.size()]);
                        Vec3 ap = aa, aq = az, bp = bb, bq = bz;
                        ap.z = aq.z = bp.z = bq.z = 0;
                        Vec3 l, r;
                        if (!overlap(ap, aq, bp, bq, l, r))
                            continue;
                        auto at = [&](Vec3 p, Vec3 q, Vec3 pp, Vec3 qq, Vec3 v) {
                            return p + (q - p) * ((v - pp).dot(qq - pp) / (qq - pp).dot(qq - pp));
                        };
                        Vec3 a0 = src.frame.transform_point(at(aa, az, ap, aq, l)),
                             a1 = src.frame.transform_point(at(aa, az, ap, aq, r));
                        if (!(ab ? clip_link(i, j, a0, a1) : clip_link(j, i, a0, a1)))
                            continue;
                        l = inv.transform_point(a0);
                        r = inv.transform_point(a1);
                        l.z = r.z = 0;
                        Vec3 b0 = src.frame.transform_point(at(bb, bz, bp, bq, l)),
                             b1 = src.frame.transform_point(at(bb, bz, bp, bq, r));
                        double d0 = (a0 - b0).norm(), d1 = (a1 - b1).norm();
                        if (std::max(d0, d1) < eps)
                            continue;
                        if (std::max(d0, d1) > src.mesh->walkable_climb + eps) {
                            tc_log_warn("[SurfaceGraph] native detail boundary exceeds walkable climb");
                            continue;
                        }
                        // A crossing pair would require splitting the interval at its zero.
                        if ((a0 - b0).dot(a1 - b1) < -eps * eps) {
                            tc_log_warn("[SurfaceGraph] crossing detail boundaries require rebake");
                            continue;
                        }
                        SurfaceFace riser = a;
                        riser.vertices = {a0, a1, b1, b0};
                        std::vector<Vec3> clean;
                        for (auto v : riser.vertices)
                            if (clean.empty() || (v - clean.back()).norm() > eps)
                                clean.push_back(v);
                        if (clean.size() > 1 && (clean.front() - clean.back()).norm() < eps)
                            clean.pop_back();
                        if (clean.size() < 3)
                            continue;
                        riser.vertices = std::move(clean);
                        size_t id = graph.faces.size();
                        graph.faces.push_back(std::move(riser));
                        if (ab) {
                            join(graph, i, id, a0, a1, false);
                            join(graph, id, j, b0, b1, false);
                        }
                        if (ba) {
                            join(graph, j, id, b0, b1, false);
                            join(graph, id, i, a0, a1, false);
                        }
                    }
            }
        // Typed transitions keep their attachment positions and directionality.
        for (const auto& [key, p] : polygons)
            for (const auto& link : p->links) {
                auto target = polygons.find({key.first, link.poly_ref});
                if (target == polygons.end() || (!p->poly_type && !target->second->poly_type))
                    continue;
                Vec3 point = sources[key.first].frame.transform_point(vector(link.left));
                Vec3 endpoint = sources[key.first].frame.transform_point(vector(link.target_left));
                auto pick = [&](Key k, Vec3 v) {
                    size_t best = faces[k].front();
                    double distance = 1e100;
                    for (size_t f : faces[k]) {
                        double d = (closest_surface_point(graph.faces[f], v) - v).norm();
                        if (d < distance) {
                            distance = d;
                            best = f;
                        }
                    }
                    return best;
                };
                if (faces[key].empty() || faces[target->first].empty())
                    continue;
                size_t from = pick(key, point), to = pick(target->first, endpoint);
                if ((point - endpoint).norm() > eps) {
                    SurfaceFace bridge = graph.faces[p->poly_type ? from : to];
                    bridge.vertices = {point, endpoint};
                    size_t mid = graph.faces.size();
                    graph.faces.push_back(std::move(bridge));
                    join(graph, from, mid, point, point, false);
                    join(graph, mid, to, endpoint, endpoint, false);
                } else
                    join(graph, from, to, point, point, false);
            }
        graph.index();
        const auto edges = boundaries(graph);
        size_t native_count = graph.faces.size();
        for (const auto& seam : seams) {
            if (seam.from >= sources.size() || seam.to >= sources.size() || !std::isfinite(seam.max_extension) ||
                seam.max_extension < 0) {
                tc_log_warn("[SurfaceGraph] invalid seam declaration");
                continue;
            }
            std::vector<Boundary> aa, bb;
            for (const auto& edge : edges) {
                Boundary selected;
                if (graph.faces[edge.face].surface == seam.from &&
                    select_boundary(edge, seam.start_a, seam.start_b, seam.max_extension, selected))
                    aa.push_back(selected);
                if (graph.faces[edge.face].surface == seam.to &&
                    select_boundary(edge, seam.end_a, seam.end_b, seam.max_extension, selected))
                    bb.push_back(selected);
            }
            size_t accepted = 0;
            std::string reason = "no matching open boundary intervals";
            for (const auto& a : aa)
                for (const auto& b : bb) {
                    const auto& fa = graph.faces[a.face];
                    const auto& fb = graph.faces[b.face];
                    auto geo = extend_surface_seam(
                        {a.a, a.b, normal(fa), center(fa), b.a, b.b, normal(fb), center(fb), seam.max_extension, eps});
                    if (!geo.success) {
                        reason = geo.error;
                        continue;
                    }
                    size_t af = add_strip(graph, a.face, geo.source_a0, geo.source_a1, geo.edge0, geo.edge1);
                    size_t bf = add_strip(graph, b.face, geo.source_b0, geo.source_b1, geo.edge0, geo.edge1);
                    join(graph, af, bf, geo.edge0, geo.edge1, seam.bidirectional);
                    ++accepted;
                }
            if (!accepted)
                tc_log_warn("[SurfaceGraph] seam %zu -> %zu rejected: %s", seam.from, seam.to, reason.c_str());
        }
        // Neighbouring extension strips share lateral boundaries as well.
        for (size_t i = native_count; i < graph.faces.size(); ++i)
            for (size_t j = i + 1; j < graph.faces.size(); ++j)
                connect_faces(i, j, true);
        graph.index();
        return graph;
    }
} // namespace termin
