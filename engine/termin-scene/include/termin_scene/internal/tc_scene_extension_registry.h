#pragma once

#include <stdbool.h>

#include "termin_scene/termin_scene.h"

#ifdef __cplusplus
extern "C" {
#endif

// Process-lifetime scene-extension registry boundary. Only the canonical
// bootstrap layer may call these functions.
TERMIN_SCENE_API void tc_scene_ext_registry_init(void);
TERMIN_SCENE_API void tc_scene_ext_registry_shutdown(void);
TERMIN_SCENE_API bool tc_scene_ext_registry_initialized(void);

#ifdef __cplusplus
}
#endif
