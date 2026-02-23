// tc_opengl.cpp - OpenGL backend initialization C API implementation
#include "tc_opengl.h"
#include "tgfx/opengl/opengl_backend.hpp"
#include "tc_gpu_context.h"

static bool g_opengl_initialized = false;
static termin::OpenGLGraphicsBackend* g_graphics_backend = nullptr;

extern "C" {

TC_API bool tc_opengl_init(void) {
    if (g_opengl_initialized) {
        return true;
    }

    // Initialize GLAD - loads OpenGL function pointers
    // Requires an active OpenGL context
    if (!termin::init_opengl()) {
        return false;
    }

    // Register GPU operations vtable
    termin::gpu_ops_impl::register_gpu_ops();

    // Get graphics backend singleton
    g_graphics_backend = &termin::OpenGLGraphicsBackend::get_instance();
    g_graphics_backend->ensure_ready();

    // Create default GPUContext if none set (standalone paths need this)
    tc_ensure_default_gpu_context();

    g_opengl_initialized = true;
    return true;
}

TC_API bool tc_opengl_is_initialized(void) {
    return g_opengl_initialized;
}

TC_API void tc_opengl_shutdown(void) {
    // Singleton is not destroyed, just clear reference
    g_graphics_backend = nullptr;
    g_opengl_initialized = false;
}

TC_API void* tc_opengl_get_graphics(void) {
    return g_graphics_backend;
}

} // extern "C"
