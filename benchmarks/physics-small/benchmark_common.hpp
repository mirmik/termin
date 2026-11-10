#pragma once

#include <termin/robotics/articulation3d.hpp>

#include <chrono>
#include <vector>

using Clock = std::chrono::steady_clock;
inline constexpr double dt = 0.001;

void require(bool condition, const char* message);
void vector_json(const std::vector<double>& values);
void timings_json(const char* name, const std::vector<double>& samples);
std::vector<termin::robotics::ArticulationUnit3D> units(int n);
termin::robotics::Articulation3DState initial(int n);
void controller(int n, int steps, int warmups, int repeats);
void contact_pipeline(int steps, int warmups, int repeats);

template <class Function> double timed(int count, Function function) {
    const auto start = Clock::now();
    for (int i = 0; i < count; ++i)
        function();
    return std::chrono::duration<double, std::micro>(Clock::now() - start).count() / count;
}
