#include "termin/frame_profiler/frame_profiler_source.hpp"

#include <algorithm>

namespace termin {

    const FrameProfilerFrame* FrameProfilerSnapshot::find(std::int64_t frame_number) const {
        const auto found = std::find_if(frames.begin(), frames.end(), [frame_number](const auto& frame) {
            return frame.frame_number == frame_number;
        });
        return found == frames.end() ? nullptr : &*found;
    }

} // namespace termin
