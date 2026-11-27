// Optional MuJoCo 3.15 spider experiment. Build separately against the two SDKs.
// The robot's CRBA and RNEA run in Termin on every step, in the solver's live state.
#include <mujoco/mujoco.h>
#include <termin/robotics/articulation3d.hpp>
#include <termin/robotics/detail/articulation3d_access.hpp>

#ifdef TERMIN_CONTACT_PREDICTION
#include "predict_contact_step.hpp"
#endif

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <memory>
#include <stdexcept>
#include <vector>

namespace {
    using namespace termin;
    using namespace termin::robotics;

    Vec3 vector3(const double* x) {
        return {x[0], x[1], x[2]};
    }

    Pose3 pose(const double* p, const double* q) {
        return {{q[1], q[2], q[3], q[0]}, vector3(p)};
    }

    SpatialInertia3 body_inertia(const mjModel* m, int body) {
        return {m->body_mass[body],
                vector3(m->body_inertia + 3 * body),
                pose(m->body_ipos + 3 * body, m->body_iquat + 4 * body)};
    }

    struct Dynamics {
        const mjModel* model;
        std::unique_ptr<Articulation3D> tree;
        Articulation3DWorkspace workspace;
        std::vector<double> velocity, acceleration, mass, bias;
        double peak_mass_error = 0, peak_bias_error = 0;
#ifdef TERMIN_CONTACT_PREDICTION
        std::unique_ptr<predict_contact::Step> prediction;
#endif

        explicit Dynamics(const mjModel* m)
            : model(m),
              velocity(m->nv),
              acceleration(m->nv) {
            if (mj_version() != 3015000 || m->nv != m->njnt + 5 || m->nbody != m->njnt + 1 ||
                m->jnt_type[0] != mjJNT_FREE || m->jnt_bodyid[0] != 1 || m->opt.integrator != mjINT_EULER ||
                m->opt.solver != mjSOL_NEWTON || m->opt.cone != mjCONE_ELLIPTIC || m->opt.enableflags || m->ntendon ||
                m->nflex || m->neq || m->nsensor || m->na || m->nmocap || m->nplugin) {
                throw std::runtime_error("Expected the exported floating-base spider and MuJoCo 3.15.0");
            }
            for (int i = 0; i < m->nv; ++i) {
                if (m->dof_armature[i] != 0)
                    throw std::runtime_error("Unsupported DOF armature");
            }
            std::vector<ArticulationUnit3D> units;
            for (int j = 1; j < m->njnt; ++j) {
                const int b = j + 1;
                if (m->jnt_bodyid[j] != b || m->jnt_dofadr[j] != j + 5 || m->jnt_qposadr[j] != j + 6 ||
                    m->jnt_type[j] != mjJNT_HINGE || vector3(m->jnt_pos + 3 * j).norm() != 0) {
                    throw std::runtime_error("Expected one origin-centred hinge per link in tree order");
                }
                ArticulationUnit3D unit;
                const int parent = m->body_parentid[b];
                unit.parent_unit = parent == 1 ? articulation_root_frame : static_cast<std::size_t>(parent - 2);
                unit.parent_to_unit_zero = pose(m->body_pos + 3 * b, m->body_quat + 4 * b);
                unit.motion_twist_at_unit = {vector3(m->jnt_axis + 3 * j), Vec3::zero()};
                unit.inertia = body_inertia(m, b);
                units.push_back(unit);
            }
            ArticulationFloatingBase3D base;
            base.inertia = body_inertia(m, 1);
            Articulation3DState state{std::vector<double>(units.size()), std::vector<double>(units.size())};
            tree = std::make_unique<Articulation3D>(base, std::move(units), std::move(state), "MuJoCo spider");
            if (tree->diagnostic() != Articulation3DDiagnostic::None)
                throw std::runtime_error("Invalid Termin tree");
            workspace.reserve(tree->unit_count());
        }

        // v_T = diag(R^T, I) v_M. Zero world base acceleration corresponds to
        // d(v_local)/dt = -omega_local x v_local in the rotating base frame.
        void assemble(const mjData* d) {
            auto& base = *robotics::detail::Articulation3DMutableAccess::floating_base(*tree);
            base.pose_world = pose(d->qpos, d->qpos + 3);
            base.velocity_local = {vector3(d->qvel + 3), base.pose_world.ang.inverse_rotate(vector3(d->qvel))};
            auto& state = robotics::detail::Articulation3DMutableAccess::state(*tree);
            for (std::size_t j = 0; j < state.coordinates.size(); ++j) {
                state.coordinates[j] = d->qpos[7 + j] - model->qpos0[7 + j];
                state.velocities[j] = d->qvel[6 + j];
            }
            std::copy_n(d->qvel, model->nv, velocity.begin());
            const Vec3 shift = base.velocity_local.lin.cross(base.velocity_local.ang);
            for (int i = 0; i < 3; ++i) {
                velocity[i] = base.velocity_local.lin[i];
                acceleration[i] = shift[i];
            }
            if (!robotics::detail::Articulation3DMutableAccess::update_kinematics(*tree) ||
                !tree->mass_matrix(mass, workspace) ||
                !tree->inverse_dynamics(velocity, acceleration, vector3(model->opt.gravity), bias, workspace)) {
                throw std::runtime_error("Termin tree dynamics failed");
            }
            const Vec3 force = base.pose_world.ang.rotate(vector3(bias.data()));
            for (int i = 0; i < 3; ++i)
                bias[i] = force[i];

            // R M_base R^T in the upper 3x3 block; rotate the three columns of
            // each lower row coupling world translation to other velocities.
            const int n = model->nv;
            for (int i = 0; i < n; ++i) {
                const Vec3 row = base.pose_world.ang.rotate(vector3(mass.data() + n * i));
                for (int k = 0; k < 3; ++k)
                    mass[n * i + k] = row[k];
            }
            for (int j = 0; j < 3; ++j) {
                const Vec3 column = base.pose_world.ang.rotate({mass[j], mass[n + j], mass[2 * n + j]});
                for (int k = 0; k < 3; ++k)
                    mass[n * k + j] = column[k];
            }
        }

        void step(mjData* d, bool validate) {
            const mjModel* m = model;
            mj_fwdKinematics(m, d);
            assemble(d);
            if (validate)
                mj_makeM(m, d);
            for (int i = 0; i < m->nv; ++i) {
                const int start = m->M_rowadr[i];
                for (int k = start; k < start + m->M_rownnz[i]; ++k) {
                    const double value = mass[i * m->nv + m->M_colind[k]];
                    if (validate)
                        peak_mass_error = std::max(peak_mass_error, std::abs(value - d->M[k]));
                    d->M[k] = value;
                }
            }
            mj_factorM(m, d);
            mj_collision(m, d);
            mj_makeConstraint(m, d);
            mj_island(m, d);
            mj_projectConstraint(m, d);
            mj_transmission(m, d);
            for (int r = 0; r < m->nout; ++r) {
                double value = 0;
                const int start = d->moment_rowadr[r];
                for (int k = start; k < start + d->moment_rownnz[r]; ++k) {
                    value += d->actuator_moment[k] * d->qvel[d->moment_colind[k]];
                }
                d->actuator_velocity[r] = value;
            }
            mj_comVel(m, d);
            mj_passive(m, d);
            mj_referenceConstraint(m, d);
            if (validate) {
                mj_rne(m, d, 0, d->qfrc_bias);
                for (int i = 0; i < m->nv; ++i) {
                    peak_bias_error = std::max(peak_bias_error, std::abs(bias[i] - d->qfrc_bias[i]));
                }
            }
            std::copy(bias.begin(), bias.end(), d->qfrc_bias);
            mj_fwdActuation(m, d);
            mj_fwdAcceleration(m, d);
#ifdef TERMIN_CONTACT_PREDICTION
            if (prediction)
                prediction->prepare(d);
#endif
            mj_fwdConstraint(m, d);
            mj_Euler(m, d);
        }
    };
} // namespace

extern "C" void* spider_dynamics_create(const mjModel* m) {
    try {
        return new Dynamics(m);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Spider dynamics: %s\n", e.what());
        return nullptr;
    }
}
extern "C" void spider_dynamics_destroy(Dynamics* work) {
    delete work;
}
#ifdef TERMIN_CONTACT_PREDICTION
extern "C" int spider_dynamics_enable_prediction(Dynamics* work) {
    try {
        work->prediction = std::make_unique<predict_contact::Step>(work->model);
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Spider predictive workspace: %s\n", e.what());
        return -1;
    }
}
extern "C" int spider_dynamics_prediction_hits(const Dynamics* work) {
    return work->prediction ? work->prediction->hit_count() : 0;
}
extern "C" double spider_dynamics_prediction_fraction(const Dynamics* work, int i) {
    return work->prediction ? work->prediction->fraction(i) : std::nan("");
}
#endif
extern "C" int spider_dynamics_step(Dynamics* work, mjData* d, int validate) {
    try {
        work->step(d, validate);
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Spider step: %s\n", e.what());
        return -1;
    }
}
extern "C" void spider_dynamics_errors(const Dynamics* work, double* mass, double* bias) {
    *mass = work->peak_mass_error;
    *bias = work->peak_bias_error;
}

// One batch has one Python boundary in both branches. Timing includes the same
// target changes and terminal-pose FK as the spider's scene benchmark.
extern "C" int
spider_dynamics_batch(Dynamics* work, const mjModel* m, mjData* d, int hip, const double* targets, int count) {
    try {
        for (int i = 0; i < count; ++i) {
            d->ctrl[hip] = targets[i];
            if (work)
                work->step(d, false);
            else
                mj_step(m, d);
            mj_kinematics(m, d);
        }
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Spider batch: %s\n", e.what());
        return -1;
    }
}
