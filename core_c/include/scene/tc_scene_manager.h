// tc_scene_manager.h - SceneManager C API for cross-DLL instance access
#ifndef TC_SCENE_MANAGER_H
#define TC_SCENE_MANAGER_H

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// Opaque pointer to SceneManager
typedef struct tc_scene_manager tc_scene_manager;

// Get global SceneManager instance
TC_API tc_scene_manager* tc_scene_manager_instance(void);

// Set global SceneManager instance
TC_API void tc_scene_manager_set_instance(tc_scene_manager* sm);

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_MANAGER_H
