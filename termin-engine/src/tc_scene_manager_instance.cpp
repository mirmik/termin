// tc_scene_manager_instance.cpp - SceneManager singleton storage
// Compiled into termin_engine to keep one process-wide SceneManager instance.

#include "scene/tc_scene_manager.h"

static tc_scene_manager* g_scene_manager_instance = nullptr;

extern "C" {

tc_scene_manager* tc_scene_manager_instance(void) {
    return g_scene_manager_instance;
}

void tc_scene_manager_set_instance(tc_scene_manager* sm) {
    g_scene_manager_instance = sm;
}

} // extern "C"
