// tc_project_settings.h - Project-level render settings accessible from C/C++
#ifndef TC_PROJECT_SETTINGS_H
#define TC_PROJECT_SETTINGS_H

#include "tc_render_core_settings.h"

#ifdef __cplusplus
extern "C" {
#endif

TC_API tc_render_sync_mode tc_project_settings_get_render_sync_mode(void);
TC_API void tc_project_settings_set_render_sync_mode(tc_render_sync_mode mode);

#ifdef __cplusplus
}
#endif

#endif
