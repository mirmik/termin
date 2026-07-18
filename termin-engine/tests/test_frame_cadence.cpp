#include "frame_cadence.hpp"

#include <cmath>
#include <iostream>

namespace {

bool close_to(double left, double right) {
    return std::abs(left - right) < 1e-9;
}

} // namespace

int main() {
    using termin::engine_detail::observe_frame_start;

    const auto first = observe_frame_start(100.0, 0.0, 100.0, 16.0, false);
    if (!close_to(first.interval_ms, 0.0) ||
        !close_to(first.deadline_lateness_ms, 0.0) ||
        !close_to(first.next_scheduled_start_ms, 116.0)) {
        std::cerr << "first cadence observation is not neutral\n";
        return 1;
    }

    const auto on_time = observe_frame_start(116.0, 100.0, 116.0, 16.0, true);
    if (!close_to(on_time.interval_ms, 16.0) || on_time.missed_intervals != 0 ||
        !close_to(on_time.next_scheduled_start_ms, 132.0)) {
        std::cerr << "on-time cadence observation is incorrect\n";
        return 1;
    }

    const auto late = observe_frame_start(151.0, 116.0, 132.0, 16.0, true);
    if (!close_to(late.interval_ms, 35.0) ||
        !close_to(late.deadline_lateness_ms, 19.0) ||
        late.missed_intervals != 1 ||
        !close_to(late.next_scheduled_start_ms, 167.0)) {
        std::cerr << "late cadence observation did not preserve pre-resync lateness\n";
        return 1;
    }

    const auto unlimited = observe_frame_start(151.5, 151.0, 151.5, 0.0, true);
    if (!close_to(unlimited.interval_ms, 0.5) ||
        !close_to(unlimited.target_interval_ms, 0.0) ||
        unlimited.missed_intervals != 0 ||
        !close_to(unlimited.next_scheduled_start_ms, 151.5)) {
        std::cerr << "unlimited cadence should not invent a frame deadline\n";
        return 1;
    }
    return 0;
}
