#include "termin_scene/termin_scene.h"
#include "core/tc_scene_extension.h"

static int g_termin_scene_runtime_refcount = 0;

void termin_scene_runtime_init(void) {
    if (g_termin_scene_runtime_refcount++ > 0) return;
    tc_scene_ext_registry_init();
}

void termin_scene_runtime_shutdown(void) {
    if (g_termin_scene_runtime_refcount <= 0) return;
    g_termin_scene_runtime_refcount--;
    if (g_termin_scene_runtime_refcount == 0) {
        tc_scene_ext_registry_shutdown();
    }
}
