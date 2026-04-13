// tc_rendering_manager_instance.cpp - RenderingManager singleton storage
// This file is compiled into entity_lib (SHARED) to ensure single instance across all DLLs

#include "render/tc_rendering_manager.h"

// Global instance pointer - stored in entity_lib (SHARED)
static tc_rendering_manager* g_rendering_manager_instance = nullptr;

extern "C" {

tc_rendering_manager* tc_rendering_manager_instance(void) {
    return g_rendering_manager_instance;
}

void tc_rendering_manager_set_instance(tc_rendering_manager* rm) {
    g_rendering_manager_instance = rm;
}

} // extern "C"
