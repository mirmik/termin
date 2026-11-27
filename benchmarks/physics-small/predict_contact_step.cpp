#include "predict_contact_step.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>

namespace predict_contact {
    namespace {
        void use_surface_material(mjContact& con, const mjModel* m) {
            // Combine implicit rigid-geom pairs by MuJoCo's contact material rules.
            int a = con.geom[0], b = con.geom[1];
            if (m->geom_priority[a] > m->geom_priority[b])
                b = a;
            if (m->geom_priority[b] > m->geom_priority[a])
                a = b;
            con.dim = std::max(m->geom_condim[a], m->geom_condim[b]);
            double mix_a = m->geom_solmix[a], mix_b = m->geom_solmix[b];
            if (mix_a < mjMINVAL)
                mix_a = 0;
            if (mix_b < mjMINVAL)
                mix_b = 0;
            const double weight = mix_a + mix_b == 0 ? .5 : mix_a / (mix_a + mix_b);
            const double* ref_a = m->geom_solref + mjNREF * a;
            const double* ref_b = m->geom_solref + mjNREF * b;
            for (int k = 0; k < mjNREF; ++k) {
                con.solref[k] = ref_a[0] > 0 && ref_b[0] > 0 ? weight * ref_a[k] + (1 - weight) * ref_b[k]
                                                             : std::min(ref_a[k], ref_b[k]);
            }
            for (int k = 0; k < mjNIMP; ++k) {
                con.solimp[k] = weight * m->geom_solimp[mjNIMP * a + k] + (1 - weight) * m->geom_solimp[mjNIMP * b + k];
            }
            constexpr int directions[] = {0, 0, 1, 2, 2};
            for (int k = 0; k < 5; ++k) {
                const int j = directions[k];
                con.friction[k] = std::max({mjMINMU, m->geom_friction[3 * a + j], m->geom_friction[3 * b + j]});
            }
        }

        mjContact normal_contact(const Hit& hit) {
            mjContact con{};
            con.geom1 = con.geom[0] = hit.geom1;
            con.geom2 = con.geom[1] = hit.geom2;
            con.flex[0] = con.flex[1] = con.vert[0] = con.vert[1] = con.elem[0] = con.elem[1] = -1;
            con.dist = hit.gap;
            con.dim = 1;
            con.efc_address = -1;
            mju_copy3(con.pos, hit.position);
            mju_copy3(con.frame, hit.normal);
            // mj_contactForce reports in this orthonormal frame.
            double basis[3] = {};
            basis[std::abs(con.frame[2]) > 0.8 ? 1 : 2] = 1;
            mju_cross(con.frame + 3, basis, con.frame);
            mju_normalize3(con.frame + 3);
            mju_cross(con.frame + 6, con.frame, con.frame + 3);
            // A unilateral velocity limit, with the maximum impedance supported by
            // MuJoCo. The regularizer still applies. The physical gap stays positive.
            mj_defaultSolRefImp(con.solref, con.solimp);
            con.solimp[0] = con.solimp[1] = mjMAXIMP;
            return con;
        }
    } // namespace

    Step::Step(const mjModel* model)
        : model_(model),
          sweep_(model),
          end_velocity_(model->nv) {
        if (mj_version() != 3015000 || mj_version() != mjVERSION_HEADER || model->opt.integrator != mjINT_EULER ||
            model->opt.solver != mjSOL_NEWTON || (model->opt.enableflags & mjENBL_SLEEP) || model->nsensor ||
            model->nplugin) {
            throw std::runtime_error(
                "Predictive experiment requires MuJoCo 3.15 Euler/Newton without sensors, plugins or sleeping");
        }
        if (!mju_isZero(model->geom_adhesion, model->ngeom))
            throw std::runtime_error("Predictive handoff requires nonadhesive surfaces");
        // The sweep uses exactly v + h * a_free. Implicit joint damping would
        // integrate a different free velocity, including damping from actuators.
        if (!(model->opt.disableflags & mjDSBL_EULERDAMP) &&
            (!mju_isZero(model->dof_damping, model->nv) || !mju_isZero(model->dof_dampingpoly, mjNPOLY * model->nv) ||
             !mju_isZero(model->actuator_damping, model->nactuator) ||
             !mju_isZero(model->actuator_dampingpoly, mjNPOLY * model->nactuator)))
            throw std::runtime_error(
                "Predictive drift requires explicit free velocity (disable implicit Euler damping)");
    }

    void Step::prepare(mjData* d) {
        const double h = model_->opt.timestep;
        if (previous_data_ != d || d->time != next_time_)
            previous_pairs_.clear();
        previous_data_ = d;
        next_time_ = d->time + h;
        if (model_->opt.disableflags & (mjDSBL_CONSTRAINT | mjDSBL_CONTACT)) {
            previous_pairs_.clear();
            fractions_.clear();
            return;
        }
        mju_addScl(end_velocity_.data(), d->qvel, d->qacc_smooth, h, model_->nv);
        const auto& hits = sweep_.find(d, end_velocity_.data(), h);
        fractions_.clear();
        next_pairs_.clear();
        arrival_indices_.clear();
        const int first = d->ncon;
        for (int i = 0; i < first; ++i) {
            const auto& c = d->contact[i];
            if (!c.exclude)
                next_pairs_.push_back({std::min(c.geom[0], c.geom[1]), std::max(c.geom[0], c.geom[1])});
        }
        for (const auto& hit : hits) {
            std::array<int, 2> pair{hit.geom1, hit.geom2};
            next_pairs_.push_back(pair);
            auto con = normal_contact(hit);
            if (std::find(previous_pairs_.begin(), previous_pairs_.end(), pair) != previous_pairs_.end()) {
                // This pair reached contact last step. If free motion crosses again
                // while measured surfaces are still just apart, retain its normal
                // and tangential material response, instead of repeatedly braking
                // the normal in mid-air and starving friction. A separating sweep
                // produces no row and automatically expires the pair.
                use_surface_material(con, model_);
            } else {
                arrival_indices_.push_back(d->ncon);
            }
            if (mj_addContact(model_, d, &con))
                throw std::runtime_error("Predictive contact arena exhausted");
            fractions_.push_back(hit.fraction);
        }
        previous_pairs_.swap(next_pairs_);
        if (fractions_.empty())
            return;
        // mj_addContact invalidates the old constraint arena. Rebuild only on steps
        // with an incoming pair. Existing loaded contacts retain their usual rows.
        mj_makeConstraint(model_, d);
        mj_island(model_, d);
        mj_projectConstraint(model_, d);
        mj_referenceConstraint(model_, d);
        normal_velocity_.resize(d->nefc);
        mj_mulJacVec(model_, d, normal_velocity_.data(), end_velocity_.data());
        for (int i : arrival_indices_) {
            const int row = d->contact[i].efc_address;
            if (row < 0)
                throw std::runtime_error("Predicted contact has no constraint row");
            // In linear normal motion fraction * free_speed = -gap/h. The body
            // travels the remaining separation during this step instead of being
            // stopped at its initial pose. For rotation this is a local approximation.
            const double target = std::min(0.0, fractions_[i - first] * normal_velocity_[row]);
            d->efc_aref[row] = (target - d->efc_vel[row]) / h;
        }
    }

    void Step::advance(mjData* d) {
        mj_step1(model_, d);
        mj_fwdActuation(model_, d);
        mj_fwdAcceleration(model_, d);
        prepare(d);
        mj_fwdConstraint(model_, d);
        mj_checkAcc(model_, d);
        mj_Euler(model_, d);
    }

    int Step::hit_count() const {
        return static_cast<int>(fractions_.size());
    }
    double Step::fraction(int i) const {
        return i >= 0 && i < hit_count() ? fractions_[i] : std::numeric_limits<double>::quiet_NaN();
    }
} // namespace predict_contact

extern "C" predict_contact::Step* predict_contact_create(const mjModel* m) {
    try {
        return new predict_contact::Step(m);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Predictive workspace: %s\n", e.what());
        return nullptr;
    }
}
extern "C" void predict_contact_destroy(predict_contact::Step* work) {
    delete work;
}
extern "C" int predict_contact_step(predict_contact::Step* work, mjData* d) {
    try {
        work->advance(d);
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Predictive step: %s\n", e.what());
        return -1;
    }
}
extern "C" int predict_contact_hits(const predict_contact::Step* work) {
    return work->hit_count();
}
extern "C" double predict_contact_fraction(const predict_contact::Step* work, int i) {
    return work->fraction(i);
}
