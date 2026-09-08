// vulkan_swapchain.hpp - VkSwapchainKHR wrapper for on-screen presentation.
//
// Owns per-image views/present semaphores and per-frame acquire/submit resources.
// The host publishes frames through compose_and_present()/clear_and_present().
#pragma once

#ifdef TGFX2_HAS_VULKAN

#include <chrono>
#include <cstdint>
#include <span>
#include <vector>
#include <vulkan/vulkan.h>

#include <termin/geom/color.hpp>

#include "tgfx2/enums.hpp"
#include "tgfx2/handles.hpp"
#include "tgfx2/tgfx2_api.h"
#include "tgfx2/vulkan/internal/swapchain_ops.hpp"

namespace tgfx {

    class VulkanRenderDevice;

    constexpr VkSurfaceTransformFlagBitsKHR
    select_swapchain_pre_transform(VkSurfaceTransformFlagsKHR supported_transforms) noexcept {
        return (supported_transforms & VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR) != 0
                   ? VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR
                   : static_cast<VkSurfaceTransformFlagBitsKHR>(0);
    }

    constexpr bool swapchain_result_requires_recreate(VkResult result) noexcept {
        // VK_SUBOPTIMAL_KHR is usable and may be persistent when Android's
        // currentTransform differs from our deliberate identity pre-transform.
        return result == VK_ERROR_OUT_OF_DATE_KHR;
    }

    TGFX2_API VkSurfaceFormatKHR
    select_swapchain_surface_format(std::span<const VkSurfaceFormatKHR> formats) noexcept;

    class TGFX2_TYPE_API VulkanSwapchain {
    public:
        // Number of CPU/GPU frames in flight. Must be >=1. 2 is a sensible
        // default — one GPU frame is queued while the next is being recorded
        // on the CPU. Larger numbers trade memory for smoother latency at
        // the cost of input lag.
        static constexpr uint32_t MAX_FRAMES_IN_FLIGHT = 2;

    private:
        VulkanRenderDevice& device_;
        vulkan_detail::SwapchainOps ops_;
        bool failed_ = false;
        VkSurfaceKHR surface_ = VK_NULL_HANDLE;

        VkSwapchainKHR swapchain_ = VK_NULL_HANDLE;
        VkFormat format_ = VK_FORMAT_B8G8R8A8_UNORM;
        VkColorSpaceKHR color_space_ = VK_COLOR_SPACE_SRGB_NONLINEAR_KHR;
        VkPresentModeKHR present_mode_ = VK_PRESENT_MODE_FIFO_KHR;
        PresentationMode requested_presentation_mode_ = PresentationMode::VSync;
        VkSurfaceTransformFlagBitsKHR pre_transform_ = VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
        uint32_t width_ = 0;
        uint32_t height_ = 0;

        std::vector<VkImage> images_;
        std::vector<VkImageView> image_views_;

        // Per-in-flight-frame sync. Indexed by `current_frame_` which
        // wraps on MAX_FRAMES_IN_FLIGHT.
        std::vector<VkSemaphore> image_available_semaphores_;
        // Indexed by acquired image, not by frame slot. Reacquisition plus the
        // submit wait proves the previous presentation has consumed this signal.
        std::vector<VkSemaphore> render_finished_semaphores_;
        std::vector<VkFence> in_flight_fences_;
        std::vector<VkFence> acquire_fences_;
        std::array<bool, MAX_FRAMES_IN_FLIGHT> submitted_{};
        std::array<bool, MAX_FRAMES_IN_FLIGHT> acquire_pending_{};

        // Per-in-flight-frame command buffer for compose_and_present.
        // Allocated once at swapchain construction, reused each cycle.
        std::vector<VkCommandBuffer> compose_command_buffers_;

        uint32_t current_frame_ = 0;

        struct ComposeStats {
            std::chrono::steady_clock::time_point window_start = std::chrono::steady_clock::now();
            uint64_t frames = 0;
            double wait_us = 0.0;
            double acquire_us = 0.0;
            double record_us = 0.0;
            double submit_us = 0.0;
            double present_us = 0.0;
            double total_us = 0.0;
        };
        ComposeStats compose_stats_;

    public:
        VulkanSwapchain(VulkanRenderDevice& dev,
                        VkSurfaceKHR surface,
                        uint32_t width,
                        uint32_t height,
                        PresentationMode presentation_mode = PresentationMode::VSync,
                        const vulkan_detail::SwapchainOps& ops = {});
        ~VulkanSwapchain();

        VulkanSwapchain(const VulkanSwapchain&) = delete;
        VulkanSwapchain& operator=(const VulkanSwapchain&) = delete;

    private:
        // SUCCESS/SUBOPTIMAL acquire an image; OUT_OF_DATE requests recreation.
        // TIMEOUT/NOT_READY acquire nothing. Other errors stop this swapchain.
        VkResult acquire(uint32_t* out_image_index, VkSemaphore* out_image_available);

        // Present the given image. `render_finished` is the semaphore that
        // the caller signalled when it submitted its command buffer —
        // presentation waits on it before actually putting the image on
        // screen. OUT_OF_DATE requests recreation; SUBOPTIMAL remains usable.
        VkResult present(uint32_t image_index, VkSemaphore render_finished);

    public:
        // Recreate the swapchain at a new size (e.g. on window resize
        // or after an OUT_OF_DATE from acquire/present). Waits for the
        // device to be idle first — safe to call while a previous frame
        // might still be in flight.
        void recreate(uint32_t width, uint32_t height);

    private:
        void wait_for_current_frame();
        void advance_frame();
    public:
        PresentationMode presentation_mode() const {
            return requested_presentation_mode_;
        }

        // One-shot helper: composite `color_tex` onto the next swapchain
        // image and publish the frame. Handles the full wait → acquire →
        // layout transitions → vkCmdBlitImage → submit → present →
        // advance cycle internally, so the host only needs one call per
        // frame. `color_tex` must have been created on the same device
        // as this swapchain and can be any size — it's scaled to the
        // swapchain extent with VK_FILTER_LINEAR.
        //
        // Returns whether a recreate is required (OUT_OF_DATE from acquire or
        // present). SUBOPTIMAL remains usable; host resize callbacks recreate
        // explicitly. True means the caller
        // should call recreate(w, h) before the next frame.
        bool compose_and_present(tgfx::TextureHandle color_tex);

        // One-shot smoke helper: clear the acquired swapchain image directly
        // and present it. This bypasses tgfx2 textures/blits and is intended
        // for platform bring-up diagnostics.
        bool clear_and_present(termin::LinearColor color);

        // Introspection
        VkSwapchainKHR handle() const {
            return swapchain_;
        }
        VkFormat format() const {
            return format_;
        }
        VkSurfaceTransformFlagBitsKHR pre_transform() const {
            return pre_transform_;
        }
        uint32_t width() const {
            return width_;
        }
        uint32_t height() const {
            return height_;
        }
        uint32_t image_count() const {
            return static_cast<uint32_t>(images_.size());
        }
        VkImage image(uint32_t i) const {
            return images_[i];
        }
        VkImageView image_view(uint32_t i) const {
            return image_views_[i];
        }

    private:
        void check(VkResult result, const char* operation);
        void check_device(VkResult result, const char* operation);
        void require_usable() const;
        void wait_for_retirement();
        void submit_frame(VkCommandBuffer commands, uint32_t image_index, VkSemaphore image_available);
        void create_swapchain();
        void destroy_swapchain();
        void create_sync_objects();
        void destroy_sync_objects();
    };

} // namespace tgfx

#endif // TGFX2_HAS_VULKAN
