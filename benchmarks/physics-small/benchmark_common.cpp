#include "benchmark_common.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>

using namespace termin;
using namespace termin::robotics;

void require(bool condition, const char* message) {
    if (!condition)
        throw std::runtime_error(message);
}

std::vector<ArticulationUnit3D> units(int n) {
    std::vector<ArticulationUnit3D> result;
    for (int i = 0; i < n; ++i) {
        result.push_back({
            .parent_unit = i ? std::size_t(i - 1) : articulation_root_frame,
            .parent_to_unit_zero = Pose3::translation(i ? 0.3 : 0.0, 0, 0),
            .motion_twist_at_unit = {i % 2 ? Vec3::unit_z() : Vec3::unit_y(), Vec3::zero()},
            .inertia = SpatialInertia3{1.0, {0.02, 0.025, 0.03}, Pose3::translation(0.15, 0, 0)},
            .diagnostic_name = "link",
        });
    }
    return result;
}

Articulation3DState initial(int n) {
    Articulation3DState state{std::vector<double>(n), std::vector<double>(n)};
    for (int i = 0; i < n; ++i)
        state.coordinates[i] = i % 2 ? -0.15 : 0.2;
    return state;
}

void vector_json(const std::vector<double>& values) {
    std::cout << '[';
    for (std::size_t i = 0; i < values.size(); ++i) {
        require(std::isfinite(values[i]), "non-finite benchmark output");
        if (i)
            std::cout << ',';
        std::cout << values[i];
    }
    std::cout << ']';
}

void timings_json(const char* name, const std::vector<double>& samples) {
    auto sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    const auto half = sorted.size() / 2;
    const double median = sorted.size() % 2 ? sorted[half] : 0.5 * (sorted[half - 1] + sorted[half]);
    std::cout << '"' << name << "\":{\"median_us\":" << median << ",\"min_us\":" << sorted.front()
              << ",\"max_us\":" << sorted.back() << ",\"samples_us\":";
    vector_json(samples);
    std::cout << '}';
}
