// backend_window.hpp - Backend-neutral SDL window wrapper for tgfx2.
//
// Replaces the hand-rolled "create SDL window + make GL context + call
// SDL_GL_SwapWindow" boilerplate that lived in every app. One class,
// one API; the backend (OpenGL / Vulkan / future) is picked from the
// TERMIN_BACKEND env-var at construction. Apps that use BackendWindow
// never need to know which backend is live.
//
//   BackendWindow win("Editor", 1280, 720);
//   auto* dev = win.device();
//   while (!win.should_close()) {
//       win.poll_events();
//       // render into my_color_tex via dev / RenderContext2
//       win.present(my_color_tex);
//   }
#pragma once

#include <memory>
#include <string>
#include <utility>

#include <SDL2/SDL.h>

#include "tgfx2/handles.hpp"
#include "render/termin_display_api.h"

namespace tgfx {
class IRenderDevice;
class PipelineCache;
class RenderContext2;
}

namespace termin {

class TERMIN_DISPLAY_API BackendWindow {
public:
    // Create a window + backend device. Throws std::runtime_error on
    // SDL / device failure. The selected backend is TERMIN_BACKEND
    // (defaults to OpenGL).
    BackendWindow(const std::string& title, int width, int height);

    // Secondary-window constructor. Uses the IRenderDevice owned by
    // `share_with` — no new device, no new instance, preserves the
    // "one IRenderDevice per process" invariant. The new window owns:
    //   - its own SDL window,
    //   - its own GL context (OpenGL, created with sharing) or its
    //     own VkSurfaceKHR + VulkanSwapchain (Vulkan).
    // All resource handles (textures, buffers, pipelines) created on
    // the primary remain valid here and vice versa.
    //
    // Throws std::runtime_error on SDL / surface / swapchain failure.
    BackendWindow(const std::string& title, int width, int height,
                  BackendWindow& share_with);

    ~BackendWindow();

    BackendWindow(const BackendWindow&) = delete;
    BackendWindow& operator=(const BackendWindow&) = delete;

    // The render device bound to this window. Apps create all resources
    // / pipelines / command lists through this — no backend-specific
    // calls anywhere else.
    tgfx::IRenderDevice* device();

    // A RenderContext2 bound to this window's device. Created lazily on
    // first call. Share this across frames — it holds a pipeline cache
    // that gets warmer as the app runs.
    tgfx::RenderContext2* context();

    // Raw SDL handle for hosts that need to forward events or embed
    // the window. Prefer should_close() / poll_events() for the common
    // path.
    SDL_Window* sdl_window() const { return window_; }

    bool should_close() const { return should_close_; }
    void set_should_close(bool v) { should_close_ = v; }

    // Drainable to SDL_QUIT / ESC. Apps that want more fine-grained
    // event handling should use poll_event() in a loop.
    void poll_events();
    bool poll_event(SDL_Event& out_event);

    // Current drawable-framebuffer size (width, height). Adjusts after
    // host window resize; the next present() will recreate the Vulkan
    // swapchain automatically.
    std::pair<int, int> framebuffer_size() const;

    // Publish a frame. `color_tex` must have been created on this
    // window's device. Semantics:
    //   OpenGL: blit color_tex onto FBO 0 with SDL_GL_SwapWindow.
    //   Vulkan: acquire swapchain image, blit, submit, present, advance.
    // Any resolution mismatch between color_tex and the window is
    // resolved by a linear-filter blit.
    void present(tgfx::TextureHandle color_tex);

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    SDL_Window* window_ = nullptr;
    bool should_close_ = false;
};

} // namespace termin
