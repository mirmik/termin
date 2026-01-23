// tc_opengl.h - OpenGL backend initialization for C API
#pragma once

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// Initialize OpenGL backend.
// Must be called AFTER an OpenGL context is current (e.g., after OpenTK creates context).
// Loads OpenGL function pointers via glad and registers GPU operations vtable.
// Returns true on success, false if OpenGL initialization failed.
TC_API bool tc_opengl_init(void);

// Check if OpenGL backend is initialized
TC_API bool tc_opengl_is_initialized(void);

// Shutdown OpenGL backend (optional, for cleanup)
TC_API void tc_opengl_shutdown(void);

// Get the global OpenGL graphics backend.
// Returns NULL if not initialized.
// The returned pointer is valid until tc_opengl_shutdown() is called.
TC_API void* tc_opengl_get_graphics(void);

#ifdef __cplusplus
}
#endif
