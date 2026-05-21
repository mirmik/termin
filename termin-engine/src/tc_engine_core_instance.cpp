// tc_engine_core_instance.cpp - EngineCore singleton storage
// Compiled into termin_engine to keep one process-wide EngineCore instance.

#include "engine/tc_engine_core.h"

static tc_engine_core* g_engine_core_instance = nullptr;

extern "C" {

tc_engine_core* tc_engine_core_instance(void) {
    return g_engine_core_instance;
}

void tc_engine_core_set_instance(tc_engine_core* engine) {
    g_engine_core_instance = engine;
}

} // extern "C"
