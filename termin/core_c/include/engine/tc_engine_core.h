// tc_engine_core.h - EngineCore C API for cross-DLL instance access
#ifndef TC_ENGINE_CORE_H
#define TC_ENGINE_CORE_H

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// Opaque pointer to EngineCore
typedef struct tc_engine_core tc_engine_core;

// Get global EngineCore instance
TC_API tc_engine_core* tc_engine_core_instance(void);

// Set global EngineCore instance
TC_API void tc_engine_core_set_instance(tc_engine_core* engine);

#ifdef __cplusplus
}
#endif

#endif // TC_ENGINE_CORE_H
