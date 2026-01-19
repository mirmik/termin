// tc_profiler.h - Hierarchical profiler for timing code sections
#ifndef TC_PROFILER_H
#define TC_PROFILER_H

#include "tc_types.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Configuration
// ============================================================================

#define TC_PROFILER_MAX_DEPTH 16
#define TC_PROFILER_MAX_SECTIONS 256
#define TC_PROFILER_MAX_NAME_LEN 64

// ============================================================================
// Section Timing Data
// ============================================================================

typedef struct tc_section_timing {
    char name[TC_PROFILER_MAX_NAME_LEN];
    double cpu_ms;
    int call_count;
    int parent_index;  // -1 for root sections
    int first_child;   // -1 if no children
    int next_sibling;  // -1 if no more siblings
} tc_section_timing;

typedef struct tc_frame_profile {
    int frame_number;
    double total_ms;
    tc_section_timing sections[TC_PROFILER_MAX_SECTIONS];
    int section_count;
} tc_frame_profile;

// ============================================================================
// Profiler API
// ============================================================================

// Get singleton profiler instance
TC_API void* tc_profiler_instance(void);

// Enable/disable
TC_API bool tc_profiler_enabled(void);
TC_API void tc_profiler_set_enabled(bool enabled);

// Profile components flag
TC_API bool tc_profiler_profile_components(void);
TC_API void tc_profiler_set_profile_components(bool enabled);

// Detailed rendering profiling (adds per-pass sections in render code)
TC_API bool tc_profiler_detailed_rendering(void);
TC_API void tc_profiler_set_detailed_rendering(bool enabled);

// Frame control
TC_API void tc_profiler_begin_frame(void);
TC_API void tc_profiler_end_frame(void);

// Section timing
TC_API void tc_profiler_begin_section(const char* name);
TC_API void tc_profiler_end_section(void);

// Get current frame data (valid between begin_frame and end_frame)
TC_API tc_frame_profile* tc_profiler_current_frame(void);

// History access
TC_API int tc_profiler_history_count(void);
TC_API tc_frame_profile* tc_profiler_history_at(int index);
TC_API void tc_profiler_clear_history(void);

// Get frame number
TC_API int tc_profiler_frame_count(void);

#ifdef __cplusplus
}
#endif

#endif // TC_PROFILER_H
