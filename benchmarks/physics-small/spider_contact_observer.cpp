// Linux benchmark probe. Read the committed contact state once per step.
// It is loaded only for trajectory recording, outside the timed processes.
#include <termin/physics_qopt/contact3d.hpp>

#include <dlfcn.h>

#include <cstdio>
#include <cstdlib>
#include <vector>

using namespace termin::physics_qopt;

namespace {
    struct FootContact {
        double x, y, z;
        double gap, normal_impulse, tangent_speed, tangent_travel, work;
        int sliding;
    };

    std::vector<FootContact> committed;
    std::vector<termin::Vec3> initial_separation;
    int passes, commits;

    template <class Function> Function original(const char* symbol) {
        static void* library = dlopen("libtermin_physics_qopt.so.0", RTLD_NOW | RTLD_NOLOAD);
        auto* address = library ? dlsym(library, symbol) : nullptr;
        if (!address) {
            std::fprintf(stderr, "Cannot locate contact observer target %s\n", symbol);
            std::abort();
        }
        return reinterpret_cast<Function>(address);
    }
}

extern "C" void spider_begin_observation() {
    committed.clear();
    passes = commits = 0;
}

extern "C" const FootContact* spider_contacts(int* count, int* friction_passes, int* accepted) {
    *count = static_cast<int>(committed.size());
    *friction_passes = passes;
    *accepted = commits;
    return committed.data();
}

namespace termin::physics_qopt {
    AssemblyDiagnostic ContactSet3DContribution::begin_step() noexcept {
        using Begin = AssemblyDiagnostic (*)(ContactSet3DContribution*);
        static const auto begin = original<Begin>("_ZN6termin12physics_qopt24ContactSet3DContribution10begin_stepEv");
        const auto status = begin(this);
        initial_separation.clear();
        for (const auto& contact : contacts()) {
            const auto a = contact.endpoint_a.point_motion(), b = contact.endpoint_b.point_motion();
            if (!a.ok() || !b.ok()) {
                std::fprintf(stderr, "Invalid initial contact points\n");
                std::abort();
            }
            initial_separation.push_back(b.value.position_world - a.value.position_world);
        }
        return status;
    }

    void ContactSet3DContribution::apply_friction_solution(const DynamicsFrictionTopology& topology,
                                                          ConstDenseVectorView normal,
                                                          ConstDenseVectorView tangent,
                                                          ConstDenseVectorView work) noexcept {
        using Apply = void (*)(ContactSet3DContribution*, const DynamicsFrictionTopology&, ConstDenseVectorView,
                               ConstDenseVectorView, ConstDenseVectorView);
        static const auto apply = original<Apply>(
            "_ZN6termin12physics_qopt24ContactSet3DContribution23apply_friction_solutionERKNS0_24DynamicsFrictionTopologyENS_4qopt20ConstDenseVectorViewES6_S6_");
        apply(this, topology, normal, tangent, work);
        ++passes;
    }

    void ContactSet3DContribution::commit_step() noexcept {
        using Commit = void (*)(ContactSet3DContribution*);
        static const auto commit =
            original<Commit>("_ZN6termin12physics_qopt24ContactSet3DContribution11commit_stepEv");
        commit(this);
        ++commits;
        for (size_t i = 0; i < states().size(); ++i) {
            const auto& contact = contacts()[i];
            const auto& state = states()[i];
            if (contact.endpoint_a.is_static() == contact.endpoint_b.is_static()) {
                continue;
            }
            const auto a = contact.endpoint_a.point_motion(), b = contact.endpoint_b.point_motion();
            if (!a.ok() || !b.ok() || initial_separation.size() != states().size()) {
                std::fprintf(stderr, "Invalid committed contact points\n");
                std::abort();
            }
            const auto p = (contact.endpoint_a.is_static() ? b : a).value.position_world;
            const auto delta = b.value.position_world - a.value.position_world - initial_separation[i];
            const auto normal = contact.normal_from_a_to_b_world;
            const double tangent_travel = (delta - normal * delta.dot(normal)).norm();
            committed.push_back({p.x, p.y, p.z, state.signed_gap, state.normal_impulse,
                                 state.tangent_velocity_world.norm(), tangent_travel, state.friction_work, state.sliding});
        }
    }
}
