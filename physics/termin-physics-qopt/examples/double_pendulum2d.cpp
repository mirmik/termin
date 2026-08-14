#include <termin/physics_qopt/multibody2d.hpp>

#include <cmath>
#include <cstdio>

using namespace termin;
using namespace termin::physics_qopt;

int main() {
    Multibody2DSystem system;
    const auto upper = system.add_body({1.0, 0.1, {}}, {{0.0, {std::sin(0.35), -std::cos(0.35)}}, {}, 0.0}, "upper");
    const auto lower = system.add_body({1.0, 0.1, {}},
                                       {
                                           {
                                               0.0,
                                               {
                                                   std::sin(0.35) + std::sin(-0.2),
                                                   -std::cos(0.35) - std::cos(-0.2),
                                               },
                                           },
                                           {},
                                           0.0,
                                       },
                                       "lower");
    if (!upper.ok() || !lower.ok()) {
        return 1;
    }
    if (!system.add_fixed_point_joint(upper.handle, {-std::sin(0.35), std::cos(0.35)}, {}, "world").ok() ||
        !system.add_revolute_joint(upper.handle, {}, lower.handle, {-std::sin(-0.2), std::cos(-0.2)}, "elbow").ok() ||
        system.finalize() != Multibody2DDiagnostic::None) {
        return 2;
    }

    const Vec2 gravity{0.0, -10.0};
    const double initial_energy = system.total_energy(gravity);
    for (std::size_t step = 0; step < 1000; ++step) {
        const Multibody2DStepResult result = system.step(gravity,
                                                         {
                                                             .time_step = 0.001,
                                                             .position_tolerance = 1e-9,
                                                             .velocity_tolerance = 1e-9,
                                                             .max_position_iterations = 4,
                                                             .qp_tolerance = {},
                                                         });
        if (result.status != QpStatus::Optimal) {
            std::fprintf(stderr,
                         "double pendulum failed at step %zu: %.*s\n",
                         step,
                         static_cast<int>(multibody2d_diagnostic_name(result.diagnostic).size()),
                         multibody2d_diagnostic_name(result.diagnostic).data());
            return 3;
        }
    }

    const double drift =
        std::abs(system.total_energy(gravity) - initial_energy) / std::max(1.0, std::abs(initial_energy));
    std::printf("constraint=%g velocity=%g relative_energy_drift=%g\n",
                system.max_position_constraint_error(),
                system.max_velocity_constraint_error(),
                drift);
    return drift <= 0.08 ? 0 : 4;
}
