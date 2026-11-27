#include "predict_contact_sweep.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace predict_contact {
    namespace {

        bool primitive(int type) {
            return type == mjGEOM_PLANE || (type >= mjGEOM_SPHERE && type <= mjGEOM_BOX);
        }

        bool eligible(const mjModel* m, int i, int j) {
            if (!(m->geom_contype[i] & m->geom_conaffinity[j]) && !(m->geom_contype[j] & m->geom_conaffinity[i])) {
                return false;
            }
            int b1 = m->geom_bodyid[i], b2 = m->geom_bodyid[j];
            int w1 = m->body_weldid[b1], w2 = m->body_weldid[b2];
            if (w1 == w2 ||
                (!(m->opt.disableflags & mjDSBL_FILTERPARENT) && w1 && w2 &&
                 (m->body_weldid[m->body_parentid[w1]] == w2 || m->body_weldid[m->body_parentid[w2]] == w1))) {
                return false;
            }
            int signature = (std::min(b1, b2) << 16) + std::max(b1, b2);
            for (int k = 0; k < m->nexclude; ++k) {
                if (m->exclude_signature[k] == signature)
                    return false;
            }
            return true;
        }

        // Bound every material point's path length throughout the generalized-coordinate drift.
        // Work back toward the root. A rotation adds |angle| times the maximum arm to its axis.
        // Each off-centre pivot can move the body origin by at most twice its local offset.
        double travel_bound(const mjModel* m,
                            const mjData* d,
                            int g,
                            const double* v,
                            double h,
                            double* translation,
                            double& curvature) {
            mju_zero3(translation);
            curvature = 0;
            // A sphere's orientation has no effect on its occupied region. Only its centre must be swept.
            double radius = mju_norm3(m->geom_pos + 3 * g);
            if (m->geom_type[g] != mjGEOM_SPHERE)
                radius += m->geom_rbound[g];
            double travel = 0;
            for (int b = m->geom_bodyid[g]; b; b = m->body_parentid[b]) {
                for (int k = m->body_jntnum[b] - 1; k >= 0; --k) {
                    const int joint = m->body_jntadr[b] + k;
                    const double* speed = v + m->jnt_dofadr[joint];
                    switch (m->jnt_type[joint]) {
                    case mjJNT_FREE: {
                        mju_scl3(translation, speed, h);
                        const double angle = h * mju_norm3(speed + 3);
                        curvature += 2 * angle * travel + angle * angle * radius;
                        travel += angle * radius;
                        break;
                    }
                    case mjJNT_SLIDE: {
                        const int q = m->jnt_qposadr[joint];
                        const double offset = d->qpos[q] - m->qpos0[q];
                        radius += std::max(std::abs(offset), std::abs(offset + h * speed[0]));
                        travel += h * std::abs(speed[0]);
                        break;
                    }
                    default: {
                        const double pivot = mju_norm3(m->jnt_pos + 3 * joint);
                        const double rate = m->jnt_type[joint] == mjJNT_BALL ? mju_norm3(speed) : std::abs(speed[0]);
                        const double angle = h * rate;
                        curvature += 2 * angle * travel + angle * angle * (radius + pivot);
                        travel += angle * (radius + pivot);
                        radius += 2 * pivot;
                        break;
                    }
                    }
                }
                radius += mju_norm3(m->body_pos + 3 * b);
            }
            return travel;
        }

        // Half-width of a centred primitive projected onto a fixed unit direction.
        double support_radius(const mjModel* m, const mjData* d, int g, const double* direction) {
            const auto* size = m->geom_size + 3 * g;
            if (m->geom_type[g] == mjGEOM_SPHERE)
                return size[0];
            if (m->geom_type[g] == mjGEOM_PLANE)
                return 0; // direction is the plane normal
            double n[3];
            mju_mulMatTVec3(n, d->geom_xmat + 9 * g, direction);
            switch (m->geom_type[g]) {
            case mjGEOM_BOX:
                return size[0] * std::abs(n[0]) + size[1] * std::abs(n[1]) + size[2] * std::abs(n[2]);
            case mjGEOM_CAPSULE:
                return size[0] + size[1] * std::abs(n[2]);
            case mjGEOM_CYLINDER:
                return size[0] * std::hypot(n[0], n[1]) + size[1] * std::abs(n[2]);
            case mjGEOM_ELLIPSOID:
                return std::hypot(size[0] * n[0], size[1] * n[1], size[2] * n[2]);
            default:
                throw std::logic_error("Unsupported projected primitive");
            }
        }

        struct PairQuery {
            const mjModel* model;
            const mjData* start;
            mjData* scratch;
            const double* velocity;
            double h, travel;
            int a, b;
            double curvature; // bound on relative point acceleration in normalised step time
            double axis[3]{};
            int queries = 0;

            double projected_gap() const {
                double base[3];
                mju_sub3(base, scratch->geom_xpos + 3 * b, scratch->geom_xpos + 3 * a);
                return mju_dot3(base, axis) - support_radius(model, scratch, a, axis) -
                       support_radius(model, scratch, b, axis);
            }

            double distance(double t, double* witnesses = nullptr) {
                // A persistent near-tangency can defeat a scalar Lipschitz test. Report it
                // as unresolved instead of taking exponential time or classifying a miss.
                if (++queries > 1024)
                    throw std::runtime_error("Unresolved sweep: distance-query budget exhausted");
                if (t == 0) {
                    // mj_geomDistance uses a temporary stack in mjData. The start state belongs to
                    // the caller; copy the geom poses into the reusable scratch to keep it read-only.
                    for (int g : {a, b}) {
                        mju_copy3(scratch->geom_xpos + 3 * g, start->geom_xpos + 3 * g);
                        mju_copy(scratch->geom_xmat + 9 * g, start->geom_xmat + 9 * g, 9);
                    }
                } else {
                    mju_copy(scratch->qpos, start->qpos, model->nq);
                    mj_integratePos(model, scratch->qpos, velocity, t * h);
                    mj_kinematics(model, scratch);
                }
                // A truncated distance is still a valid lower bound for interval rejection.
                return mj_geomDistance(model, scratch, a, b, travel + 1e-8, witnesses);
            }

            // A separation can change by at most travel * (hi-lo) over an interval. If
            // its two endpoint distances sum to more than that, no crossing fits inside.
            // Otherwise inspect the interior, even when both endpoints are separated.
            bool
            crossing(double lo, double flo, double plo, double hi, double fhi, double phi, int depth, double& first) {
                const double width = hi - lo;
                // An observed contact brackets a crossing even within roundoff of a subdivision boundary.
                if (fhi > 0 && flo + fhi > travel * width + 1e-14)
                    return false;
                // Along the fixed axis each pair of material points stays within
                // curvature * width²/8 of the linear interpolation of its endpoint
                // projections. Minimise that bound over both convex shapes.
                if (fhi > 0 && std::min(plo, phi) > curvature * width * width / 8 + 1e-14)
                    return false;
                if (depth == 25) {
                    if (fhi > 0 || flo <= 0)
                        return false;
                    first = lo + width * flo / (flo - fhi);
                    return true;
                }
                const double mid = (hi + lo) * 0.5;
                const double fmid = distance(mid);
                const double pmid = projected_gap();
                if (crossing(lo, flo, plo, mid, fmid, pmid, depth + 1, first))
                    return true;
                return fmid > 0 && crossing(mid, fmid, pmid, hi, fhi, phi, depth + 1, first);
            }

            Hit hit(double fraction, double initial) {
                // At exact impact the two witnesses coincide and no longer define a normal.
                // Approach from the separated side, retaining their material coordinates.
                double witnesses[6], normal[3];
                double back = 1e-7;
                for (;;) {
                    double t = std::max(0.0, fraction - back);
                    distance(t, witnesses);
                    mju_sub3(normal, witnesses + 3, witnesses);
                    const double n = mju_norm3(normal);
                    if (n > 1e-12 || t == 0) {
                        if (!(n > 0))
                            throw std::runtime_error("Sweep has no separated witness normal");
                        mju_scl3(normal, normal, 1. / n);
                        break;
                    }
                    back *= 8;
                }
                Hit result{a, b, fraction, initial, {}, {}};
                mju_copy3(result.normal, normal);
                for (int side : {0, 1}) {
                    const int g = side ? b : a;
                    double rel[3], local[3], current[3];
                    mju_sub3(rel, witnesses + 3 * side, scratch->geom_xpos + 3 * g);
                    mju_mulMatTVec3(local, scratch->geom_xmat + 9 * g, rel);
                    mju_mulMatVec3(current, start->geom_xmat + 9 * g, local);
                    mju_addTo3(current, start->geom_xpos + 3 * g);
                    mju_addToScl3(result.position, current, .5);
                }
                return result;
            }
        };

    } // namespace

    Sweep::Sweep(const mjModel* m)
        : model_(m),
          scratch_(mj_makeData(m), &mj_deleteData),
          travel_(m->ngeom, -1),
          curvature_(m->ngeom),
          extent_(3 * m->ngeom),
          translation_(m->ngeom) {
        if (!scratch_)
            throw std::runtime_error("Could not allocate sweep scratch");
        if (m->npair || m->nflex || m->nmocap || mjcb_contactfilter ||
            (m->opt.enableflags & (mjENBL_SLEEP | mjENBL_OVERRIDE)) || (m->opt.disableflags & mjDSBL_NATIVECCD)) {
            throw std::invalid_argument("Sweep requires rigid geoms, default filtering and native convex distances");
        }
        for (int i = 0; i < m->ngeom; ++i) {
            for (int j = i + 1; j < m->ngeom; ++j) {
                if (!eligible(m, i, j))
                    continue;
                for (int g : {i, j}) {
                    if (!primitive(m->geom_type[g]) || m->geom_margin[g] || m->geom_gap[g] ||
                        (m->geom_type[g] == mjGEOM_PLANE && m->body_weldid[m->geom_bodyid[g]])) {
                        throw std::invalid_argument("Sweep supports zero-margin convex primitives and fixed planes");
                    }
                    travel_[g] = 0;
                }
                pairs_.push_back({i, j});
            }
        }
    }

    const std::vector<Hit>& Sweep::find(const mjData* d, const mjtNum* v, double h) {
        const mjModel* m = model_;
        hits_.clear();
        if (m->opt.disableflags & mjDSBL_CONTACT)
            return hits_;
        for (int g = 0; g < m->ngeom; ++g) {
            if (travel_[g] < 0)
                continue;
            travel_[g] = travel_bound(m, d, g, v, h, translation_[g].data(), curvature_[g]);
            if (m->geom_type[g] == mjGEOM_PLANE)
                continue;
            const double* size = m->geom_aabb + 6 * g + 3;
            for (int axis = 0; axis < 3; ++axis) {
                const double* row = d->geom_xmat + 9 * g + 3 * axis;
                extent_[3 * g + axis] =
                    std::abs(row[0]) * size[0] + std::abs(row[1]) * size[1] + std::abs(row[2]) * size[2];
            }
        }
        for (const auto& [a, b] : pairs_) {
            double translation[3];
            mju_sub3(translation, translation_[a].data(), translation_[b].data());
            const double residual = travel_[a] + travel_[b];
            const double bound = mju_norm3(translation) + residual;
            if (bound == 0)
                continue;
            if (m->geom_type[a] != mjGEOM_PLANE && m->geom_type[b] != mjGEOM_PLANE) {
                bool separated = false;
                for (int k = 0; k < 3; k++) {
                    if (std::abs(d->geom_xpos[3 * b + k] - d->geom_xpos[3 * a + k]) >
                        extent_[3 * a + k] + extent_[3 * b + k] + bound)
                        separated = true;
                }
                if (separated)
                    continue;
            }
            bool has_contact = false;
            for (int k = 0; k < d->ncon; k++) {
                const int* g = d->contact[k].geom;
                if ((g[0] == a && g[1] == b) || (g[0] == b && g[1] == a)) {
                    has_contact = true;
                    break;
                }
            }
            if (has_contact)
                continue;
            PairQuery q{m, d, scratch_.get(), v, h, bound, a, b, curvature_[a] + curvature_[b]};
            double witnesses[6], direction[3];
            const double initial = q.distance(0, witnesses);
            if (initial <= 0 || initial > bound)
                continue;
            mju_sub3(direction, witnesses + 3, witnesses);
            const double len = mju_norm3(direction);
            if (m->geom_type[a] == mjGEOM_PLANE || m->geom_type[b] == mjGEOM_PLANE) {
                const int plane = m->geom_type[a] == mjGEOM_PLANE ? a : b;
                for (int k = 0; k < 3; k++)
                    q.axis[k] = (plane == a ? 1 : -1) * d->geom_xmat[9 * plane + k * 3 + 2];
            } else if (len > 0) {
                mju_scl3(q.axis, direction, 1. / len);
            } else {
                throw std::runtime_error("Missing separated witnesses");
            }
            // Witness subtraction loses direction accuracy for very small gaps. A box
            // face axis provides an exact alternative separating plane near flat contact.
            double plo = q.projected_gap();
            if (m->geom_type[a] != mjGEOM_PLANE && m->geom_type[b] != mjGEOM_PLANE) {
                for (int g : {a, b})
                    if (m->geom_type[g] == mjGEOM_BOX) {
                        for (int n = 0; n < 3; n++) {
                            double old[3];
                            mju_copy3(old, q.axis);
                            const double sign =
                                (d->geom_xmat[9 * g + n] * direction[0] + d->geom_xmat[9 * g + n + 3] * direction[1] +
                                 d->geom_xmat[9 * g + n + 6] * direction[2]) >= 0
                                    ? 1
                                    : -1;
                            for (int k = 0; k < 3; k++)
                                q.axis[k] = sign * d->geom_xmat[9 * g + 3 * k + n];
                            const double candidate = q.projected_gap();
                            if (candidate > plo)
                                plo = candidate;
                            else
                                mju_copy3(q.axis, old);
                        }
                    }
            }
            // This is a true separation along the chosen axis even when two
            // nearly coincident witnesses gave an imprecise initial direction.
            if (plo > std::max(0., mju_dot3(translation, q.axis) + residual) + 1e-14)
                continue;
            const double endpoint = q.distance(1);
            const double phi = q.projected_gap();
            double t;
            if (q.crossing(0, initial, plo, 1, endpoint, phi, 0, t))
                hits_.push_back(q.hit(t, initial));
        }
        return hits_;
    }

} // namespace predict_contact
