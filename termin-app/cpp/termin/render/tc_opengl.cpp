// tc_opengl.cpp - OpenGL backend initialization C API implementation
#include "tc_opengl.h"

#include <glad/glad.h>

#include "tgfx/opengl/opengl_backend.hpp"  // init_opengl()
#include <tgfx/tc_gpu_context.h>
#include <tgfx/tgfx_resource_gpu.h>
#include <tgfx/resources/tc_mesh.h>

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

    // The tgfx_gpu_ops vtable is filled by `RenderEngine::ensure_tgfx2()`
    // (or `Tgfx2ContextHolder` ctor for Python hosts) on first use. It
    // routes tc_mesh / tc_texture / tc_shader uploads through the tgfx2
    // IRenderDevice. Nothing should call those legacy entry points
    // before a render starts.

    // Register termin_mesh GPU ops (upload/draw/delete) so tc_mesh_upload_gpu
    // dispatches through the live vtable once it's installed.
    {
        static const tc_mesh_gpu_ops gl_mesh_ops = {
            tgfx_mesh_draw_gpu,
            tgfx_mesh_upload_gpu,
            tgfx_mesh_delete_gpu,
        };
        tc_mesh_set_gpu_ops(&gl_mesh_ops);
    }

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);
    glFrontFace(GL_CCW);

    // Create default GPUContext if none set (standalone paths need this)
    tc_ensure_default_gpu_context();

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
