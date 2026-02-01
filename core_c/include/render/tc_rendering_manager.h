// tc_rendering_manager.h - C API for RenderingManager singleton access
// This ensures a single instance is shared across all DLLs

#ifndef TC_RENDERING_MANAGER_H
#define TC_RENDERING_MANAGER_H

#include "../tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// Opaque pointer to RenderingManager
typedef struct tc_rendering_manager tc_rendering_manager;

// Get the global RenderingManager instance (creates if not exists)
TC_API tc_rendering_manager* tc_rendering_manager_instance(void);

// Set the global RenderingManager instance (for initialization)
TC_API void tc_rendering_manager_set_instance(tc_rendering_manager* rm);

#ifdef __cplusplus
}
#endif

#endif // TC_RENDERING_MANAGER_H
