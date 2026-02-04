// tc_project_settings.c - Project settings implementation
#include "tc_project_settings.h"

// ============================================================================
// Global State
// ============================================================================

static tc_render_sync_mode g_render_sync_mode = TC_RENDER_SYNC_NONE;

// ============================================================================
// API Implementation
// ============================================================================

tc_render_sync_mode tc_project_settings_get_render_sync_mode(void) {
    return g_render_sync_mode;
}

void tc_project_settings_set_render_sync_mode(tc_render_sync_mode mode) {
    g_render_sync_mode = mode;
}
