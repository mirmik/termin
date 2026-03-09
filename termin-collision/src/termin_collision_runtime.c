#include "termin_collision/termin_collision.h"
#include "physics/tc_collision_world.h"

static int g_termin_collision_runtime_refcount = 0;

void termin_collision_runtime_init(void) {
    if (g_termin_collision_runtime_refcount++ > 0) return;
    tc_collision_world_extension_init();
}

void termin_collision_runtime_shutdown(void) {
    if (g_termin_collision_runtime_refcount <= 0) return;
    g_termin_collision_runtime_refcount--;
}
