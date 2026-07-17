#pragma once

#include <algorithm>
#include <cmath>

namespace termin::engine_detail {

struct FrameCadenceObservation {
    double start_time_ms = 0.0;
    double interval_ms = 0.0;
    double target_interval_ms = 0.0;
    double deadline_lateness_ms = 0.0;
    int missed_intervals = 0;
    double next_scheduled_start_ms = 0.0;
};

inline FrameCadenceObservation observe_frame_start(
    double start_time_ms,
    double previous_start_time_ms,
    double scheduled_start_time_ms,
    double target_interval_ms,
    bool has_previous
) {
    FrameCadenceObservation result;
    result.start_time_ms = start_time_ms;
    result.target_interval_ms = target_interval_ms;
    if (!has_previous) {
        result.next_scheduled_start_ms = start_time_ms + target_interval_ms;
        return result;
    }

    result.interval_ms = std::max(0.0, start_time_ms - previous_start_time_ms);
    result.deadline_lateness_ms = std::max(0.0, start_time_ms - scheduled_start_time_ms);
    if (target_interval_ms > 0.0) {
        result.missed_intervals = static_cast<int>(
            std::floor(result.deadline_lateness_ms / target_interval_ms)
        );
    }
    const double resynchronized_start =
        result.deadline_lateness_ms > 0.0 ? start_time_ms : scheduled_start_time_ms;
    result.next_scheduled_start_ms = resynchronized_start + target_interval_ms;
    return result;
}

} // namespace termin::engine_detail
