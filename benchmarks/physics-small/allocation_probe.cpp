#include "benchmark_common.hpp"

#include <termin/physics_qopt/physics_qopt.hpp>

#include <atomic>
#include <charconv>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <memory>
#include <new>
#include <string_view>

namespace {
    std::atomic<bool> enabled{false};
    std::atomic<std::size_t> requests{0}, requested_bytes{0};

    void* allocate(std::size_t bytes, std::size_t alignment = 0) {
        void* pointer = nullptr;
        for (;;) {
            if (alignment == 0)
                pointer = std::malloc(bytes ? bytes : 1);
            else if (posix_memalign(&pointer, alignment, bytes ? bytes : 1) != 0)
                pointer = nullptr;
            if (pointer)
                break;
            const auto handler = std::get_new_handler();
            if (!handler)
                throw std::bad_alloc();
            handler();
        }
        if (enabled.load(std::memory_order_relaxed)) {
            requests.fetch_add(1, std::memory_order_relaxed);
            requested_bytes.fetch_add(bytes, std::memory_order_relaxed);
        }
        return pointer;
    }

    void start_counting() {
        requests.store(0, std::memory_order_relaxed);
        requested_bytes.store(0, std::memory_order_relaxed);
        enabled.store(true, std::memory_order_relaxed);
    }

    void setup(termin::physics_qopt::DynamicsSystem& system, termin::robotics::Articulation3D& arm) {
        using namespace termin::physics_qopt;
        require(system.add_contribution(std::make_unique<Articulation3DDynamicsContribution>(
                    arm, termin::Vec3{0, 0, -9.81}, "allocation probe")) == DynamicsSystemDiagnostic::None,
                "allocation probe contribution failed");
        require(system.finalize() == DynamicsSystemDiagnostic::None, "allocation probe finalize failed");
    }
} // namespace

// Separate ELF executable: these replacements never participate in throughput
// timings. C malloc (including Eigen buffers) is deliberately not intercepted.
void* operator new(std::size_t size) {
    return allocate(size);
}
void* operator new[](std::size_t size) {
    return allocate(size);
}
void* operator new(std::size_t size, std::align_val_t alignment) {
    return allocate(size, std::size_t(alignment));
}
void* operator new[](std::size_t size, std::align_val_t alignment) {
    return allocate(size, std::size_t(alignment));
}
void operator delete(void* pointer) noexcept {
    std::free(pointer);
}
void operator delete[](void* pointer) noexcept {
    std::free(pointer);
}
void operator delete(void* pointer, std::size_t) noexcept {
    std::free(pointer);
}
void operator delete[](void* pointer, std::size_t) noexcept {
    std::free(pointer);
}
void operator delete(void* pointer, std::align_val_t) noexcept {
    std::free(pointer);
}
void operator delete[](void* pointer, std::align_val_t) noexcept {
    std::free(pointer);
}
void operator delete(void* pointer, std::size_t, std::align_val_t) noexcept {
    std::free(pointer);
}
void operator delete[](void* pointer, std::size_t, std::align_val_t) noexcept {
    std::free(pointer);
}

void probe(int n, int steps) {
    using namespace termin::robotics;
    using namespace termin::physics_qopt;
    Articulation3D arm(units(n), initial(n), "allocation probe");
    DynamicsSystem system;
    setup(system, arm);

    // The current SDK RNEA allocates three temporary vector<Screw3> buffers.
    // Prewarm output storage, then require those DSO allocations to reach our
    // replacements. Update this check if RNEA acquires a reusable workspace.
    const std::vector<double> zero(n, 0.0);
    std::vector<double> effort;
    require(arm.inverse_dynamics(zero, zero, {}, effort), "allocation oracle prewarm failed");
    start_counting();
    const bool oracle_ok = arm.inverse_dynamics(zero, zero, {}, effort);
    enabled.store(false, std::memory_order_relaxed);
    const std::size_t dso_requests = requests.load(std::memory_order_relaxed);
    require(oracle_ok && dso_requests >= 3, "SDK C++ new interposition self-check failed");

    requests.store(0, std::memory_order_relaxed);
    requested_bytes.store(0, std::memory_order_relaxed);
    for (int step = 0; step < steps; ++step) {
        enabled.store(true, std::memory_order_relaxed);
        const auto result = system.step({.time_step = dt});
        enabled.store(false, std::memory_order_relaxed);
        require(result.ok(), "allocation probe dynamics step failed");
    }
    const auto calls = requests.load(std::memory_order_relaxed);
    const auto bytes = requested_bytes.load(std::memory_order_relaxed);
    // Validate that counting does not change the deterministic trajectory.
    Articulation3D reference(units(n), initial(n), "allocation reference");
    DynamicsSystem reference_system;
    setup(reference_system, reference);
    for (int step = 0; step < steps; ++step)
        require(reference_system.step({.time_step = dt}).ok(), "allocation reference step failed");
    require(arm.state().coordinates == reference.state().coordinates &&
                arm.state().velocities == reference.state().velocities,
            "allocation counting changed trajectory");
    std::cout << "{\"dof\":" << n << ",\"dso_self_check_requests\":" << dso_requests
              << ",\"cpp_new_requests_per_step\":" << static_cast<double>(calls) / steps
              << ",\"cpp_new_requested_bytes_per_step\":" << static_cast<double>(bytes) / steps << ",\"final_q\":";
    vector_json(arm.state().coordinates);
    std::cout << ",\"final_v\":";
    vector_json(arm.state().velocities);
    std::cout << '}';
}

int main(int argc, char** argv) {
    try {
        require(argc == 2, "usage: physics_small_allocation_probe steps");
        const std::string_view input{argv[1]};
        int steps = 0;
        const auto parsed = std::from_chars(input.data(), input.data() + input.size(), steps);
        require(parsed.ec == std::errc{} && parsed.ptr == input.data() + input.size() && steps > 0,
                "steps must be a positive integer");
        std::cout << std::setprecision(17)
                  << "{\"scope\":\"successful C++ new requests only; excludes malloc/Eigen buffers; not peak/live "
                     "memory or timing\","
                  << "\"steps\":" << steps << ",\"chains\":[";
        bool first = true;
        for (int n : {2, 6, 12, 24}) {
            if (!first)
                std::cout << ',';
            first = false;
            probe(n, steps);
        }
        std::cout << "]}\n";
    } catch (const std::exception& error) {
        enabled.store(false, std::memory_order_relaxed);
        std::cerr << "[physics-small-allocation-probe] " << error.what() << '\n';
        return 1;
    }
}
