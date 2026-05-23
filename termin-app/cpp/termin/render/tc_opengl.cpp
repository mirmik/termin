// tc_opengl.cpp - OpenGL backend initialization C API implementation
#include "tc_opengl.h"

#include <glad/glad.h>

#include "tgfx/opengl/opengl_backend.hpp"  // init_opengl()

static bool g_opengl_initialized = false;

extern "C" {

TC_API bool tc_opengl_init(void) {
    if (g_opengl_initialized) {
        return true;
    }

    // Initialize GLAD - loads OpenGL function pointers
    if (!termin::init_opengl()) {
        return false;
    }

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
    glFrontFace(GL_CCW);

    g_opengl_initialized = true;
    return true;
}

TC_API bool tc_opengl_is_initialized(void) {
    return g_opengl_initialized;
}

TC_API void tc_opengl_shutdown(void) {
    g_opengl_initialized = false;
}

} // extern "C"
