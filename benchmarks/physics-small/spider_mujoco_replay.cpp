// Replay a Termin keyframe with the MuJoCo 3.15.0 wheel's public C API.
// The model must include a key named "termin" with the snapshot pose, velocity and control.
#include <mujoco/mujoco.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace {
    using Clock = std::chrono::steady_clock;
    constexpr int trials = 7;
    constexpr int repeats = 3000;
    using Samples = std::array<double, trials>;

    void require(bool condition, const char* reason) {
        if (!condition) {
            std::fprintf(stderr, "Replay failed: %s\n", reason);
            std::exit(EXIT_FAILURE);
        }
    }

    double microseconds() {
        static const auto origin = Clock::now();
        return std::chrono::duration<double, std::micro>(Clock::now() - origin).count();
    }

    template <class Operation> double measure(Operation op) {
        const auto start = Clock::now();
        for (int i = 0; i < repeats; ++i) {
            op();
        }
        return std::chrono::duration<double, std::micro>(Clock::now() - start).count() / repeats;
    }

    void report(const char* label, Samples samples) {
        std::printf("%-34s", label);
        for (double us : samples) {
            std::printf(" %7.3f", us);
        }
        std::sort(samples.begin(), samples.end());
        std::printf("   median %7.3f us\n", samples[trials / 2]);
    }

    void verify(const mjModel* model, const mjData* expected, const mjData* actual) {
        require(actual->nefc == expected->nefc, "constraint count changed");
        const auto row_bytes = actual->nefc * sizeof(mjtNum);
        const auto dof_bytes = model->nv * sizeof(mjtNum);
        require(std::memcmp(actual->efc_force, expected->efc_force, row_bytes) == 0,
                "row force differs from mj_forward");
        require(std::memcmp(actual->qfrc_constraint, expected->qfrc_constraint, dof_bytes) == 0,
                "generalized contact force differs from mj_forward");
        require(std::memcmp(actual->qacc, expected->qacc, dof_bytes) == 0, "acceleration differs from mj_forward");
        for (int i = 0; i < actual->nefc; ++i) {
            require(std::isfinite(actual->efc_force[i]), "nonfinite row force");
        }
        for (int i = 0; i < model->nv; ++i) {
            require(std::isfinite(actual->qacc[i]) && std::isfinite(actual->qfrc_constraint[i]), "nonfinite solution");
        }
        for (const auto& warning : actual->warning) {
            require(warning.number == 0, "MuJoCo warning");
        }
    }
} // namespace

int main(int argc, char** argv) {
    require(argc == 2, "usage: spider_mujoco_replay KEYFRAME.xml");
    require(mj_version() == 3015000 && mj_version() == mjVERSION_HEADER, "requires MuJoCo 3.15.0 headers and library");
    char error[1024] = {};
    mjModel* model = mj_loadXML(argv[1], nullptr, error, sizeof(error));
    require(model != nullptr, error);
    require(model->opt.solver == mjSOL_NEWTON && model->opt.cone == mjCONE_ELLIPTIC &&
                model->opt.integrator == mjINT_EULER && model->nsensor == 0,
            "expected the Newton/elliptic/Euler spider");
    model->opt.timestep = 0.001;
    const int key = mj_name2id(model, mjOBJ_KEY, "termin");
    require(key >= 0, "missing termin key");
    mjData* data = mj_makeData(model);
    mjData* reference[2] = {mj_makeData(model), mj_makeData(model)};
    require(data && reference[0] && reference[1], "unable to allocate replay data");
    mj_resetDataKeyframe(model, data, key);
    for (int mode = 0; mode != 2; ++mode) {
        model->opt.noslip_iterations = mode ? 10 : 0;
        mj_resetDataKeyframe(model, reference[mode], key);
        mj_forward(model, reference[mode]);
    }
    mj_fwdPosition(model, data);
    mj_fwdVelocity(model, data);
    mj_fwdActuation(model, data);
    mj_fwdAcceleration(model, data);
    mj_fwdConstraint(model, data);
    verify(model, reference[1], data);
    require(data->ncon == 6 && data->nefc == 18, "expected six contacts with three rows each");
    std::printf("MuJoCo %s, nv %d, contacts %d, rows %d, islands %d, t %.6f, dt %.6f\n",
                mj_versionString(),
                (int)model->nv,
                data->ncon,
                data->nefc,
                data->nisland,
                data->time,
                model->opt.timestep);
    for (int i = 0; i < data->ncon; ++i) {
        const mjContact& c = data->contact[i];
        require(c.efc_address >= 0 && c.dim == 3, "inactive or unexpected contact");
        double wrench[6];
        mj_contactForce(model, data, i, wrench);
        require(std::isfinite(wrench[0]) && wrench[0] > 0, "unloaded foot");
        std::printf("%s / %s: %.9f N, gap %.9g m\n",
                    mj_id2name(model, mjOBJ_GEOM, c.geom[0]),
                    mj_id2name(model, mjOBJ_GEOM, c.geom[1]),
                    wrench[0],
                    c.dist);
    }
    std::printf("iterations (island 0) Newton %d, Newton+NoSlip %d\n",
                reference[0]->solver_niter[0],
                reference[1]->solver_niter[0]);

    for (int i = 0; i < repeats; ++i) {
        mj_forward(model, data);
    }
    Samples make, project, ref, newton, combined, incremental, forward;
    for (int trial = 0; trial < trials; ++trial) {
        model->opt.noslip_iterations = 10;
        forward[trial] = measure([&] { mj_forward(model, data); });

        // Use the engine's internal scopes, with a monotonic callback in microseconds.
        // Include contact assembly and island formation, then metric projection. The
        // full position stage resets the arena as part of normal collision detection.
        mjcb_time = microseconds;
        std::memset(data->timer, 0, sizeof(data->timer));
        for (int i = 0; i < repeats; ++i) {
            mj_fwdPosition(model, data);
        }
        mjcb_time = nullptr;
        require(data->timer[mjTIMER_POS_MAKE].number == repeats && data->timer[mjTIMER_POS_PROJECT].number == repeats,
                "missing position timers");
        make[trial] = data->timer[mjTIMER_POS_MAKE].duration / repeats;
        project[trial] = data->timer[mjTIMER_POS_PROJECT].duration / repeats;
        mj_fwdVelocity(model, data);
        ref[trial] = measure([&] { mj_referenceConstraint(model, data); });
        mj_fwdActuation(model, data);
        mj_fwdAcceleration(model, data);

        // Toggle only the NoSlip post-pass after preparation. Both arms use the
        // same AR, inertia, reference accelerations and zero keyframe warm-start.
        for (int arm = 0; arm < 2; ++arm) {
            const int mode = (trial + arm) % 2;
            model->opt.noslip_iterations = mode ? 10 : 0;
            auto& samples = mode ? combined : newton;
            samples[trial] = measure([&] { mj_fwdConstraint(model, data); });
            verify(model, reference[mode], data);
        }
        incremental[trial] = combined[trial] - newton[trial];
    }
    report("make constraints + islands", make);
    report("project constraint matrix", project);
    report("constraint velocity + reference", ref);
    report("fwdConstraint Newton", newton);
    report("fwdConstraint Newton + NoSlip", combined);
    report("paired increment NoSlip + finish", incremental);
    report("mj_forward Newton + NoSlip", forward);
    mj_deleteData(reference[0]);
    mj_deleteData(reference[1]);
    mj_deleteData(data);
    mj_deleteModel(model);
}
