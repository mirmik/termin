// tc_rendering_manager_instance.cpp - RenderingManager singleton storage
// Compiled into termin_engine to keep one process-wide RenderingManager instance.

#include "render/tc_rendering_manager.h"

static tc_rendering_manager* g_rendering_manager_instance = nullptr;

extern "C" {

tc_rendering_manager* tc_rendering_manager_instance(void) {
    return g_rendering_manager_instance;
}

void tc_rendering_manager_set_instance(tc_rendering_manager* rm) {
    g_rendering_manager_instance = rm;
}

} // extern "C"
