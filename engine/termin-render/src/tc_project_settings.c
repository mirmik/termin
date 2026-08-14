#include "tc_project_settings.h"

tc_render_sync_mode tc_project_settings_get_render_sync_mode(void) {
    return tc_render_core_settings_get_sync_mode();
}

void tc_project_settings_set_render_sync_mode(tc_render_sync_mode mode) {
    tc_render_core_settings_set_sync_mode(mode);
}
