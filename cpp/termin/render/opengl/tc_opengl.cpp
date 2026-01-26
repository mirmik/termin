// tc_opengl.cpp - OpenGL backend initialization C API implementation
#include "tc_opengl.h"
#include "termin/render/opengl/opengl_backend.hpp"
#include <memory>

static bool g_opengl_initialized = false;
static std::unique_ptr<termin::OpenGLGraphicsBackend> g_graphics_backend;

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

    // Register GPU operations vtable for tc_gpu module
    termin::gpu_ops_impl::register_gpu_ops();

    // Create graphics backend
    g_graphics_backend = std::make_unique<termin::OpenGLGraphicsBackend>();
    g_graphics_backend->ensure_ready();

    g_opengl_initialized = true;
    return true;
}

TC_API bool tc_opengl_is_initialized(void) {
    return g_opengl_initialized;
}

TC_API void tc_opengl_shutdown(void) {
    g_graphics_backend.reset();
    g_opengl_initialized = false;
}

TC_API void* tc_opengl_get_graphics(void) {
    return g_graphics_backend.get();
}

} // extern "C"
