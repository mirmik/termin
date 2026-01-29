// tc_project_settings.h - Project-level settings accessible from C/C++
#ifndef TC_PROJECT_SETTINGS_H
#define TC_PROJECT_SETTINGS_H

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Render Sync Mode
// ============================================================================

typedef enum tc_render_sync_mode {
    TC_RENDER_SYNC_NONE = 0,    // No sync between passes (fastest)
    TC_RENDER_SYNC_FLUSH = 1,   // glFlush between passes
    TC_RENDER_SYNC_FINISH = 2   // glFinish between passes (slowest)
} tc_render_sync_mode;

// ============================================================================
// Project Settings API
// ============================================================================

// Get/set render sync mode
TC_API tc_render_sync_mode tc_project_settings_get_render_sync_mode(void);
TC_API void tc_project_settings_set_render_sync_mode(tc_render_sync_mode mode);

#ifdef __cplusplus
}
#endif

#endif // TC_PROJECT_SETTINGS_H
