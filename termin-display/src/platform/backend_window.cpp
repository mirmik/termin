// backend_window.cpp - SDL window + IRenderDevice wrapper.
#include "termin/platform/backend_window.hpp"

#include <cstdint>
#include <stdexcept>
#include <string>

#include "tgfx2/device_factory.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/opengl/opengl_render_device.hpp"
#include "tgfx2/pipeline_cache.hpp"
#include "tgfx2/render_context.hpp"

extern "C" {
#include "tgfx/tc_gpu_context.h"
#include "tgfx/tgfx2_interop.h"
}

#ifdef TGFX2_HAS_VULKAN
#include <SDL2/SDL_vulkan.h>
#include <vulkan/vulkan.h>
#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/vulkan/vulkan_swapchain.hpp"
#endif

namespace termin {

// ---------------------------------------------------------------------------
// Impl — private backend state. Kept out of the header so apps don't
// need to know about SDL_GLContext / VkInstance / etc.
// ---------------------------------------------------------------------------

struct BackendWindow::Impl {
    tgfx::BackendType backend = tgfx::BackendType::OpenGL;
    // Owned IRenderDevice for primary windows; left empty on secondary
    // windows (they point `device_ref` at the primary's device instead).
    std::unique_ptr<tgfx::IRenderDevice> device;
    // Non-owning pointer used by the rest of the class. Always set —
    // equals device.get() for primary, or the shared device for
    // secondary.
    tgfx::IRenderDevice* device_ref = nullptr;
    // Lazily-built pipeline cache + RenderContext2 bound to `device`.
    // Owned only by primary windows; secondary windows forward context()
    // calls to the primary via `shared_ctx_owner`.
    std::unique_ptr<tgfx::PipelineCache> cache;
    std::unique_ptr<tgfx::RenderContext2> ctx;
    // Primary the secondary window borrows its device/context from.
    // nullptr on primaries. Used so context() / device() return the
    // same objects everywhere.
    BackendWindow* shared_ctx_owner = nullptr;

    // OpenGL state (only used when backend == OpenGL).
    SDL_GLContext gl_context = nullptr;

    // Vulkan state for secondary windows — each one owns its own
    // swapchain bound to its own VkSurfaceKHR. Primary windows have
    // the surface/swapchain owned by VulkanRenderDevice itself and
    // leave these empty.
#ifdef TGFX2_HAS_VULKAN
    VkSurfaceKHR secondary_surface = VK_NULL_HANDLE;
    std::unique_ptr<tgfx::VulkanSwapchain> secondary_swapchain;
#endif
};

// ---------------------------------------------------------------------------
// Ctor / dtor
// ---------------------------------------------------------------------------

BackendWindow::BackendWindow(const std::string& title, int width, int height)
    : impl_(std::make_unique<Impl>())
{
    if (SDL_WasInit(SDL_INIT_VIDEO) == 0 && SDL_InitSubSystem(SDL_INIT_VIDEO) != 0) {
        throw std::runtime_error(std::string("SDL_InitSubSystem failed: ") + SDL_GetError());
    }

    impl_->backend = tgfx::default_backend_from_env();

    if (impl_->backend == tgfx::BackendType::OpenGL) {
        // GL 4.3 core — gives us `layout(binding=N)` on UBOs (GL 4.2+,
        // needed for the push-constants ring UBO trick at binding 14)
        // plus `layout(location=N)` on varyings (GL 4.1+). The single
        // shader source that compiles on Vulkan SPIR-V via shaderc
        // (`#version 450`) then compiles on this GL context too —
        // `#version 450 core` is a subset of what 4.3 accepts. macOS
        // is a loss at core-profile 4.3, but the cross-backend story
        // is unusable on macOS anyway (no Vulkan natively).
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 4);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
        SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
        SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);

        Uint32 flags = SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE | SDL_WINDOW_SHOWN;
        window_ = SDL_CreateWindow(title.c_str(),
                                    SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED,
                                    width, height, flags);
        if (!window_) {
            throw std::runtime_error(std::string("SDL_CreateWindow failed: ") + SDL_GetError());
        }

        impl_->gl_context = SDL_GL_CreateContext(window_);
        if (!impl_->gl_context) {
            SDL_DestroyWindow(window_);
            throw std::runtime_error(std::string("SDL_GL_CreateContext failed: ") + SDL_GetError());
        }
        SDL_GL_MakeCurrent(window_, impl_->gl_context);
        SDL_GL_SetSwapInterval(1);

        // OpenGLRenderDevice ctor loads GLAD and validates the live
        // context — it expects MakeCurrent to already have happened.
        impl_->device = tgfx::create_device(tgfx::BackendType::OpenGL);
        impl_->device_ref = impl_->device.get();

        // Wire up legacy tgfx_gpu_ops so TcShader / TcTexture / TcMesh
        // calls (tc_shader_ensure_tgfx2, tc_mesh_upload_gpu, ...) route
        // through the tgfx2 device. Vulkan has no such interop yet —
        // the factory-default vtable stays unset there, legacy paths
        // aren't expected to run under Vulkan.
        tc_ensure_default_gpu_context();
        tgfx2_interop_set_device(impl_->device.get());
        tgfx2_gpu_ops_register();
    }
#ifdef TGFX2_HAS_VULKAN
    else if (impl_->backend == tgfx::BackendType::Vulkan) {
        Uint32 flags = SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE | SDL_WINDOW_SHOWN;
        window_ = SDL_CreateWindow(title.c_str(),
                                    SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED,
                                    width, height, flags);
        if (!window_) {
            throw std::runtime_error(std::string("SDL_CreateWindow(Vulkan) failed: ") + SDL_GetError());
        }

        uint32_t ext_count = 0;
        SDL_Vulkan_GetInstanceExtensions(window_, &ext_count, nullptr);
        std::vector<const char*> extensions(ext_count);
        SDL_Vulkan_GetInstanceExtensions(window_, &ext_count, extensions.data());

        int fb_w = 0, fb_h = 0;
        SDL_Vulkan_GetDrawableSize(window_, &fb_w, &fb_h);

        tgfx::VulkanDeviceCreateInfo info;
        info.enable_validation = true;  // TODO: gate on TERMIN_DEBUG env-var
        info.instance_extensions = extensions;
        info.swapchain_width = static_cast<uint32_t>(fb_w);
        info.swapchain_height = static_cast<uint32_t>(fb_h);
        SDL_Window* win = window_;
        info.surface_factory = [win](VkInstance inst) -> VkSurfaceKHR {
            VkSurfaceKHR surf = VK_NULL_HANDLE;
            if (!SDL_Vulkan_CreateSurface(win, inst, &surf)) {
                return VK_NULL_HANDLE;
            }
            return surf;
        };

        impl_->device = std::make_unique<tgfx::VulkanRenderDevice>(info);
        impl_->device_ref = impl_->device.get();
    }
#endif
    else {
        SDL_DestroyWindow(window_);
        throw std::runtime_error("BackendWindow: unsupported backend");
    }
}

// ---------------------------------------------------------------------------
// Secondary window — reuses the primary's IRenderDevice, adds its own
// OS window + surface/GL-context + (Vulkan) swapchain. The whole point
// is "one IRenderDevice per process" — secondary windows must not spin
// up their own devices.
// ---------------------------------------------------------------------------

BackendWindow::BackendWindow(const std::string& title, int width, int height,
                              BackendWindow& share_with)
    : impl_(std::make_unique<Impl>())
{
    if (!share_with.impl_->device_ref) {
        throw std::runtime_error(
            "BackendWindow(secondary): primary window has no device");
    }
    impl_->backend = share_with.impl_->backend;
    impl_->device_ref = share_with.impl_->device_ref;
    impl_->shared_ctx_owner = &share_with;

    if (impl_->backend == tgfx::BackendType::OpenGL) {
        // Secondary GL windows don't get their own GL context — they
        // borrow the primary's. One context can be made current against
        // any of its owner's compatible windows, which is exactly what
        // we need here: no share-group complexity, no second set of
        // cached FBOs, no risk of desynchronised GLAD function tables.
        // present() will MakeCurrent the primary's context against
        // this window before blitting + SwapWindow.
        Uint32 flags = SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE | SDL_WINDOW_SHOWN;
        window_ = SDL_CreateWindow(title.c_str(),
                                    SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED,
                                    width, height, flags);
        if (!window_) {
            throw std::runtime_error(std::string("SDL_CreateWindow(secondary) failed: ") +
                                     SDL_GetError());
        }
        // impl_->gl_context stays null — the dtor skips SDL_GL_DeleteContext.

        // Re-make the primary context current. Creating a new
        // SDL_WINDOW_OPENGL window can unbind the current GL context
        // on some drivers (Mesa/GLX in particular), after which any
        // GL call dispatched through GLAD hits a null function pointer
        // and segfaults.
        SDL_GL_MakeCurrent(share_with.window_, share_with.impl_->gl_context);
    }
#ifdef TGFX2_HAS_VULKAN
    else if (impl_->backend == tgfx::BackendType::Vulkan) {
        Uint32 flags = SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE | SDL_WINDOW_SHOWN;
        window_ = SDL_CreateWindow(title.c_str(),
                                    SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED,
                                    width, height, flags);
        if (!window_) {
            throw std::runtime_error(std::string("SDL_CreateWindow(Vulkan secondary) failed: ") +
                                     SDL_GetError());
        }

        auto* vk_dev = static_cast<tgfx::VulkanRenderDevice*>(impl_->device_ref);
        VkSurfaceKHR surf = VK_NULL_HANDLE;
        if (!SDL_Vulkan_CreateSurface(window_, vk_dev->instance(), &surf)) {
            SDL_DestroyWindow(window_);
            throw std::runtime_error(std::string("SDL_Vulkan_CreateSurface(secondary) failed: ") +
                                     SDL_GetError());
        }
        impl_->secondary_surface = surf;

        int fb_w = 0, fb_h = 0;
        SDL_Vulkan_GetDrawableSize(window_, &fb_w, &fb_h);
        impl_->secondary_swapchain = std::make_unique<tgfx::VulkanSwapchain>(
            *vk_dev, surf,
            static_cast<uint32_t>(fb_w),
            static_cast<uint32_t>(fb_h));
    }
#endif
    else {
        SDL_DestroyWindow(window_);
        throw std::runtime_error("BackendWindow(secondary): unsupported backend");
    }
}

BackendWindow::~BackendWindow() {
    // Teardown in reverse dependency order. Secondary windows skip the
    // context/device reset because those are owned by the primary —
    // tearing them down here would yank the rug out from under the
    // primary and every other secondary.
#ifdef TGFX2_HAS_VULKAN
    // Vulkan secondary: wait idle before destroying the swapchain /
    // surface to avoid killing resources still in flight.
    if (impl_->secondary_swapchain) {
        if (impl_->device_ref) {
            impl_->device_ref->wait_idle();
        }
        impl_->secondary_swapchain.reset();
    }
    if (impl_->secondary_surface != VK_NULL_HANDLE && impl_->device_ref) {
        auto* vk_dev = static_cast<tgfx::VulkanRenderDevice*>(impl_->device_ref);
        vkDestroySurfaceKHR(vk_dev->instance(), impl_->secondary_surface, nullptr);
        impl_->secondary_surface = VK_NULL_HANDLE;
    }
#endif
    if (impl_->shared_ctx_owner == nullptr) {
        // Primary window — we own the device/ctx/cache chain.
        impl_->ctx.reset();
        impl_->cache.reset();
        impl_->device.reset();
    }
    if (impl_->gl_context) {
        SDL_GL_DeleteContext(impl_->gl_context);
        impl_->gl_context = nullptr;
    }
    if (window_) {
        SDL_DestroyWindow(window_);
        window_ = nullptr;
    }
}

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------

tgfx::IRenderDevice* BackendWindow::device() {
    return impl_->device_ref;
}

tgfx::RenderContext2* BackendWindow::context() {
    // Secondary windows never build their own RenderContext2 — that
    // would defeat "one PipelineCache per device" and force redundant
    // pipeline compilations. They forward to the primary instead.
    if (impl_->shared_ctx_owner) {
        return impl_->shared_ctx_owner->context();
    }
    if (!impl_->ctx && impl_->device_ref) {
        impl_->cache = std::make_unique<tgfx::PipelineCache>(*impl_->device_ref);
        impl_->ctx = std::make_unique<tgfx::RenderContext2>(*impl_->device_ref, *impl_->cache);
    }
    return impl_->ctx.get();
}

std::pair<int, int> BackendWindow::framebuffer_size() const {
    if (!window_) return {0, 0};
    int w = 0, h = 0;
    if (impl_->backend == tgfx::BackendType::OpenGL) {
        SDL_GL_GetDrawableSize(window_, &w, &h);
    }
#ifdef TGFX2_HAS_VULKAN
    else if (impl_->backend == tgfx::BackendType::Vulkan) {
        SDL_Vulkan_GetDrawableSize(window_, &w, &h);
    }
#endif
    else {
        SDL_GetWindowSize(window_, &w, &h);
    }
    return {w, h};
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

bool BackendWindow::poll_event(SDL_Event& out_event) {
    return SDL_PollEvent(&out_event) != 0;
}

void BackendWindow::poll_events() {
    SDL_Event ev;
    while (SDL_PollEvent(&ev)) {
        if (ev.type == SDL_QUIT) should_close_ = true;
        else if (ev.type == SDL_WINDOWEVENT &&
                 ev.window.event == SDL_WINDOWEVENT_CLOSE &&
                 ev.window.windowID == SDL_GetWindowID(window_)) {
            should_close_ = true;
        }
        else if (ev.type == SDL_KEYDOWN &&
                 ev.key.keysym.scancode == SDL_SCANCODE_ESCAPE) {
            should_close_ = true;
        }
    }
}

// ---------------------------------------------------------------------------
// Present
// ---------------------------------------------------------------------------

void BackendWindow::present(tgfx::TextureHandle color_tex) {
    if (!impl_->device_ref || !window_) return;

    auto [w, h] = framebuffer_size();
    if (w <= 0 || h <= 0) return;

    if (impl_->backend == tgfx::BackendType::OpenGL) {
        // Secondary windows borrow the primary's GL context. Find it:
        // either we own it (primary) or the shared owner does.
        SDL_GLContext gl_ctx = impl_->gl_context
            ? impl_->gl_context
            : (impl_->shared_ctx_owner
                ? impl_->shared_ctx_owner->impl_->gl_context
                : nullptr);
        if (!gl_ctx) return;
        SDL_GL_MakeCurrent(window_, gl_ctx);

        // Query src size from the tgfx2 device so partial-resolution
        // FBOs composite correctly.
        auto desc = impl_->device_ref->texture_desc(color_tex);
        int src_w = static_cast<int>(desc.width);
        int src_h = static_cast<int>(desc.height);
        if (src_w <= 0 || src_h <= 0) { src_w = w; src_h = h; }

        impl_->device_ref->blit_to_external_target(
            /*dst=*/0,  // OpenGL default FBO = window framebuffer
            color_tex,
            0, 0, src_w, src_h,
            0, 0, w, h);

        SDL_GL_SwapWindow(window_);
    }
#ifdef TGFX2_HAS_VULKAN
    else if (impl_->backend == tgfx::BackendType::Vulkan) {
        auto* vk_dev = static_cast<tgfx::VulkanRenderDevice*>(impl_->device_ref);
        // Secondary windows carry their own swapchain; primary windows
        // use the one owned by VulkanRenderDevice. Either way, pick
        // the one that belongs to this window.
        tgfx::VulkanSwapchain* sc = impl_->secondary_swapchain
                                        ? impl_->secondary_swapchain.get()
                                        : vk_dev->swapchain();
        if (!sc) return;

        // If the window drawable size changed (resize event), recreate
        // the swapchain before acquiring.
        if (sc->width() != static_cast<uint32_t>(w) ||
            sc->height() != static_cast<uint32_t>(h)) {
            sc->recreate(static_cast<uint32_t>(w), static_cast<uint32_t>(h));
        }

        if (sc->compose_and_present(color_tex)) {
            // OUT_OF_DATE / SUBOPTIMAL after present — schedule
            // recreate for next frame by resampling current size.
            int nw = 0, nh = 0;
            SDL_Vulkan_GetDrawableSize(window_, &nw, &nh);
            sc->recreate(static_cast<uint32_t>(nw), static_cast<uint32_t>(nh));
        }
    }
#endif
}

} // namespace termin
