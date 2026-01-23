// tc_opengl.cpp - OpenGL backend initialization C API implementation
#include "tc_opengl.h"
#include "tc_render.h"
#include "termin/render/opengl/opengl_backend.hpp"
#include <memory>

static bool g_opengl_initialized = false;
static std::unique_ptr<termin::OpenGLGraphicsBackend> g_graphics_backend;

// tc_render_ops callback implementations that delegate to GraphicsBackend
namespace render_ops_impl {

static void* create_fbo(int width, int height, int samples, const char* format) {
    if (!g_graphics_backend) return nullptr;
    auto fbo = g_graphics_backend->create_framebuffer(width, height, samples, format ? format : "");
    // Transfer ownership - caller is responsible for destruction
    return fbo.release();
}

static void destroy_fbo(void* fbo) {
    delete static_cast<termin::FramebufferHandle*>(fbo);
}

static void resize_fbo(void* fbo, int width, int height) {
    auto* fb = static_cast<termin::FramebufferHandle*>(fbo);
    if (fb) {
        fb->resize(width, height);
    }
}

static void bind_fbo(void* fbo) {
    if (!g_graphics_backend) return;
    g_graphics_backend->bind_framebuffer(static_cast<termin::FramebufferHandle*>(fbo));
}

static void clear_color(float r, float g, float b, float a) {
    if (!g_graphics_backend) return;
    g_graphics_backend->clear_color(r, g, b, a);
}

static void clear_depth(float depth) {
    if (!g_graphics_backend) return;
    g_graphics_backend->clear_depth(depth);
}

static void clear_color_depth(float r, float g, float b, float a) {
    if (!g_graphics_backend) return;
    g_graphics_backend->clear_color_depth(r, g, b, a);
}

static void set_viewport(int x, int y, int w, int h) {
    if (!g_graphics_backend) return;
    g_graphics_backend->set_viewport(x, y, w, h);
}

static void reset_state() {
    if (!g_graphics_backend) return;
    g_graphics_backend->reset_state();
}

static void register_render_ops() {
    static tc_render_ops ops = {
        create_fbo,
        destroy_fbo,
        resize_fbo,
        bind_fbo,
        clear_color,
        clear_depth,
        clear_color_depth,
        set_viewport,
        reset_state
    };
    tc_render_set_ops(&ops);
}

} // namespace render_ops_impl

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

    // Register render operations vtable
    render_ops_impl::register_render_ops();

    g_opengl_initialized = true;
    return true;
}

TC_API bool tc_opengl_is_initialized(void) {
    return g_opengl_initialized;
}

TC_API void tc_opengl_shutdown(void) {
    g_graphics_backend.reset();
    tc_render_set_ops(nullptr);
    g_opengl_initialized = false;
}

TC_API void* tc_opengl_get_graphics(void) {
    return g_graphics_backend.get();
}

} // extern "C"
