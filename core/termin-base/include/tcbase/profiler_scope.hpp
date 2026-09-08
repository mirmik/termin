#pragma once
#include "tc_profiler.h"

namespace tc {
    // Fixed-name CPU scope. No allocation when profiling is disabled.
    class ProfilerScope {
    public:
        explicit ProfilerScope(const char* name) : enabled_(tc_profiler_enabled()) {
            if (enabled_) tc_profiler_begin_section(name);
        }
        ~ProfilerScope() {
            if (enabled_) tc_profiler_end_section();
        }
        ProfilerScope(const ProfilerScope&) = delete;
        ProfilerScope& operator=(const ProfilerScope&) = delete;
    private:
        bool enabled_;
    };
}
