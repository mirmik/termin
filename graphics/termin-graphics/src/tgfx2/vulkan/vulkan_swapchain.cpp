#ifdef TGFX2_HAS_VULKAN

#include "tgfx2/vulkan/vulkan_swapchain.hpp"
#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/vulkan/vulkan_type_conversions.hpp"
#include "vulkan_stats.hpp"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <stdexcept>

extern "C" {
#include <tcbase/tc_log.h>
}

namespace tgfx {

    namespace {

        double us_between(std::chrono::steady_clock::time_point a, std::chrono::steady_clock::time_point b) {
            return std::chrono::duration<double, std::micro>(b - a).count();
        }

        const char* presentation_mode_name(PresentationMode mode) {
            switch (mode) {
            case PresentationMode::VSync:
                return "vsync";
            case PresentationMode::Immediate:
                return "immediate";
            }
            return "unknown";
        }

        VkPresentModeKHR pick_present_mode(PresentationMode requested, const std::vector<VkPresentModeKHR>& supported) {
            const VkPresentModeKHR required =
                requested == PresentationMode::VSync ? VK_PRESENT_MODE_FIFO_KHR : VK_PRESENT_MODE_IMMEDIATE_KHR;
            if (std::find(supported.begin(), supported.end(), required) != supported.end()) {
                return required;
            }

            tc_log_error(
                "VulkanSwapchain: requested presentation mode '%s' is unsupported "
                "(FIFO=%d IMMEDIATE=%d MAILBOX=%d FIFO_RELAXED=%d)",
                presentation_mode_name(requested),
                std::find(supported.begin(), supported.end(), VK_PRESENT_MODE_FIFO_KHR) != supported.end(),
                std::find(supported.begin(), supported.end(), VK_PRESENT_MODE_IMMEDIATE_KHR) != supported.end(),
                std::find(supported.begin(), supported.end(), VK_PRESENT_MODE_MAILBOX_KHR) != supported.end(),
                std::find(supported.begin(), supported.end(), VK_PRESENT_MODE_FIFO_RELAXED_KHR) != supported.end());
            throw std::runtime_error(std::string("VulkanSwapchain: requested presentation mode '") +
                                     presentation_mode_name(requested) + "' is unsupported");
        }

    } // namespace

    VkSurfaceFormatKHR select_swapchain_surface_format(std::span<const VkSurfaceFormatKHR> formats) noexcept {
        if (formats.size() == 1 && formats.front().format == VK_FORMAT_UNDEFINED) {
            return {VK_FORMAT_B8G8R8A8_SRGB, formats.front().colorSpace};
        }
        for (const VkSurfaceFormatKHR format : formats) {
            if ((format.format == VK_FORMAT_B8G8R8A8_SRGB || format.format == VK_FORMAT_R8G8B8A8_SRGB) &&
                format.colorSpace == VK_COLOR_SPACE_SRGB_NONLINEAR_KHR) {
                return format;
            }
        }
        return {VK_FORMAT_UNDEFINED, VK_COLOR_SPACE_SRGB_NONLINEAR_KHR};
    }

    // ---------------------------------------------------------------------------

    VulkanSwapchain::VulkanSwapchain(VulkanRenderDevice& dev,
                                     VkSurfaceKHR surface,
                                     uint32_t width,
                                     uint32_t height,
                                     PresentationMode presentation_mode,
                                     const vulkan_detail::SwapchainOps& ops)
        : device_(dev),
          ops_(ops),
          surface_(surface),
          requested_presentation_mode_(presentation_mode),
          width_(width),
          height_(height) {
        VkBool32 present_support = VK_FALSE;
        const VkResult support_result = vkGetPhysicalDeviceSurfaceSupportKHR(
            device_.physical_device(), device_.present_queue_family(), surface_, &present_support);
        if (support_result != VK_SUCCESS || present_support != VK_TRUE) {
            tc_log_error("VulkanSwapchain: present queue does not support surface (VkResult=%d)", int(support_result));
            throw std::runtime_error("VulkanSwapchain: runtime present queue cannot present to this surface");
        }
        try {
            create_swapchain();
            create_sync_objects();

            // Pre-allocate one command buffer per in-flight slot.
            std::array<VkCommandBuffer, MAX_FRAMES_IN_FLIGHT> commands{};
            VkCommandBufferAllocateInfo ai{};
            ai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
            ai.commandPool = device_.command_pool();
            ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
            ai.commandBufferCount = MAX_FRAMES_IN_FLIGHT;
            check(vkAllocateCommandBuffers(device_.device(), &ai, commands.data()), "allocate compose commands");
            compose_command_buffers_.assign(commands.begin(), commands.end());
        } catch (const std::exception& error) {
            tc_log_error("VulkanSwapchain construction failed: %s", error.what());
            destroy_sync_objects();
            destroy_swapchain();
            throw;
        }
    }

    VulkanSwapchain::~VulkanSwapchain() {
        try { wait_for_retirement(); }
        catch (const std::exception& error) {
            tc_log_error("VulkanSwapchain shutdown: %s", error.what());
        }
        if (!compose_command_buffers_.empty()) {
            vkFreeCommandBuffers(device_.device(),
                                 device_.command_pool(),
                                 static_cast<uint32_t>(compose_command_buffers_.size()),
                                 compose_command_buffers_.data());
            compose_command_buffers_.clear();
        }
        destroy_sync_objects();
        destroy_swapchain();
    }

    // ---------------------------------------------------------------------------
    // Swapchain lifecycle
    // ---------------------------------------------------------------------------

    void VulkanSwapchain::create_swapchain() {
        VkPhysicalDevice physical_device = device_.physical_device();

        VkSurfaceCapabilitiesKHR caps{};
        vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical_device, surface_, &caps);

        // Clamp requested extent to the surface's min/max. currentExtent
        // is authoritative on most platforms unless it's the special
        // 0xFFFFFFFF value (Wayland in particular) — in which case we
        // use our own size clamped to min/max.
        VkExtent2D extent;
        if (caps.currentExtent.width != UINT32_MAX) {
            extent = caps.currentExtent;
        } else {
            extent.width = std::clamp(width_, caps.minImageExtent.width, caps.maxImageExtent.width);
            extent.height = std::clamp(height_, caps.minImageExtent.height, caps.maxImageExtent.height);
        }
        width_ = extent.width;
        height_ = extent.height;

        uint32_t fmt_count = 0;
        vkGetPhysicalDeviceSurfaceFormatsKHR(physical_device, surface_, &fmt_count, nullptr);
        std::vector<VkSurfaceFormatKHR> formats(fmt_count);
        vkGetPhysicalDeviceSurfaceFormatsKHR(physical_device, surface_, &fmt_count, formats.data());
        VkSurfaceFormatKHR fmt = select_swapchain_surface_format(formats);
        if (fmt.format == VK_FORMAT_UNDEFINED) {
            throw std::runtime_error(
                "VulkanSwapchain: the surface exposes no sRGB attachment format required by the window color contract");
        }
        format_ = fmt.format;
        color_space_ = fmt.colorSpace;

        uint32_t pm_count = 0;
        vkGetPhysicalDeviceSurfacePresentModesKHR(physical_device, surface_, &pm_count, nullptr);
        std::vector<VkPresentModeKHR> modes(pm_count);
        vkGetPhysicalDeviceSurfacePresentModesKHR(physical_device, surface_, &pm_count, modes.data());
        present_mode_ = pick_present_mode(requested_presentation_mode_, modes);

        // Aim for minImageCount + 1 so we always have an image ready for
        // the next frame while the current one is being presented. Clamp
        // to maxImageCount if the driver caps it (0 means no cap).
        uint32_t image_count = caps.minImageCount + 1;
        if (caps.maxImageCount > 0 && image_count > caps.maxImageCount) {
            image_count = caps.maxImageCount;
        }

        pre_transform_ = select_swapchain_pre_transform(caps.supportedTransforms);
        if (pre_transform_ == 0) {
            tc_log_error("VulkanSwapchain: identity surface transform is required but unsupported "
                         "(currentTransform=0x%x supportedTransforms=0x%x extent=%ux%u)",
                         static_cast<unsigned>(caps.currentTransform),
                         static_cast<unsigned>(caps.supportedTransforms),
                         extent.width,
                         extent.height);
            throw std::runtime_error("VulkanSwapchain: surface does not support identity presentation transform");
        }

        tc_log_info("VulkanSwapchain: presentation transform current=0x%x supported=0x%x "
                    "selected=0x%x extent=%ux%u",
                    static_cast<unsigned>(caps.currentTransform),
                    static_cast<unsigned>(caps.supportedTransforms),
                    static_cast<unsigned>(pre_transform_),
                    extent.width,
                    extent.height);

        VkSwapchainCreateInfoKHR ci{};
        ci.sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR;
        ci.surface = surface_;
        ci.minImageCount = image_count;
        ci.imageFormat = format_;
        ci.imageColorSpace = color_space_;
        ci.imageExtent = extent;
        ci.imageArrayLayers = 1;
        // TRANSFER_DST so we can blit into the swapchain image; COLOR_ATTACHMENT
        // so we can render directly into it through a VkRenderPass.
        ci.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
        const std::array<uint32_t, 2> families{device_.graphics_queue_family(), device_.present_queue_family()};
        vulkan_detail::configure_swapchain_sharing(ci, families);
        // The renderer and input pipeline already operate in the SurfaceView's
        // current physical orientation. Asking the presentation engine to apply
        // currentTransform rotates that upright image a second time on Android.
        ci.preTransform = pre_transform_;
        ci.compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
        ci.presentMode = present_mode_;
        ci.clipped = VK_TRUE;
        ci.oldSwapchain = VK_NULL_HANDLE;

        if (vkCreateSwapchainKHR(device_.device(), &ci, nullptr, &swapchain_) != VK_SUCCESS) {
            throw std::runtime_error("VulkanSwapchain: vkCreateSwapchainKHR failed");
        }

        // Grab the actual images.
        uint32_t got = 0;
        vkGetSwapchainImagesKHR(device_.device(), swapchain_, &got, nullptr);
        images_.resize(got);
        vkGetSwapchainImagesKHR(device_.device(), swapchain_, &got, images_.data());

        // Create one image view per image — same format, color aspect,
        // full-mip/layer range.
        image_views_.resize(got);
        for (uint32_t i = 0; i < got; ++i) {
            VkImageViewCreateInfo v{};
            v.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
            v.image = images_[i];
            v.viewType = VK_IMAGE_VIEW_TYPE_2D;
            v.format = format_;
            v.components = {VK_COMPONENT_SWIZZLE_IDENTITY,
                            VK_COMPONENT_SWIZZLE_IDENTITY,
                            VK_COMPONENT_SWIZZLE_IDENTITY,
                            VK_COMPONENT_SWIZZLE_IDENTITY};
            v.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
            v.subresourceRange.baseMipLevel = 0;
            v.subresourceRange.levelCount = 1;
            v.subresourceRange.baseArrayLayer = 0;
            v.subresourceRange.layerCount = 1;
            if (vkCreateImageView(device_.device(), &v, nullptr, &image_views_[i]) != VK_SUCCESS) {
                throw std::runtime_error("VulkanSwapchain: vkCreateImageView failed");
            }
        }
        render_finished_semaphores_.resize(got);
        VkSemaphoreCreateInfo semaphore_info{};
        semaphore_info.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;
        for (auto& semaphore : render_finished_semaphores_)
            check(vkCreateSemaphore(device_.device(), &semaphore_info, nullptr, &semaphore),
                  "create present semaphore");
    }

    void VulkanSwapchain::destroy_swapchain() {
        VkDevice dev = device_.device();
        for (auto semaphore : render_finished_semaphores_)
            if (semaphore) vkDestroySemaphore(dev, semaphore, nullptr);
        render_finished_semaphores_.clear();
        for (auto v : image_views_) {
            if (v)
                vkDestroyImageView(dev, v, nullptr);
        }
        image_views_.clear();
        images_.clear();
        if (swapchain_) {
            vkDestroySwapchainKHR(dev, swapchain_, nullptr);
            swapchain_ = VK_NULL_HANDLE;
        }
    }

    // ---------------------------------------------------------------------------
    // Sync objects
    // ---------------------------------------------------------------------------

    void VulkanSwapchain::create_sync_objects() {
        VkDevice dev = device_.device();
        image_available_semaphores_.resize(MAX_FRAMES_IN_FLIGHT);
        in_flight_fences_.resize(MAX_FRAMES_IN_FLIGHT);
        acquire_fences_.resize(MAX_FRAMES_IN_FLIGHT);

        VkSemaphoreCreateInfo sem_ci{};
        sem_ci.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;

        VkFenceCreateInfo fence_ci{};
        fence_ci.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
        // Only fences belonging to successful submissions are ever waited on.

        for (uint32_t i = 0; i < MAX_FRAMES_IN_FLIGHT; ++i) {
            if (vkCreateSemaphore(dev, &sem_ci, nullptr, &image_available_semaphores_[i]) != VK_SUCCESS ||
                vkCreateFence(dev, &fence_ci, nullptr, &acquire_fences_[i]) != VK_SUCCESS ||
                vkCreateFence(dev, &fence_ci, nullptr, &in_flight_fences_[i]) != VK_SUCCESS) {
                throw std::runtime_error("VulkanSwapchain: failed to create frame sync objects");
            }
        }
    }

    void VulkanSwapchain::destroy_sync_objects() {
        VkDevice dev = device_.device();
        for (auto s : image_available_semaphores_) {
            if (s)
                vkDestroySemaphore(dev, s, nullptr);
        }
        for (auto f : acquire_fences_)
            if (f) vkDestroyFence(dev, f, nullptr);
        for (auto f : in_flight_fences_) {
            if (f)
                vkDestroyFence(dev, f, nullptr);
        }
        image_available_semaphores_.clear();
        acquire_fences_.clear();
        in_flight_fences_.clear();
    }

    // ---------------------------------------------------------------------------
    // Frame cycle
    // ---------------------------------------------------------------------------

    void VulkanSwapchain::wait_for_current_frame() {
        require_usable();
        if (submitted_[current_frame_]) {
            const VkFence fence = in_flight_fences_[current_frame_];
            check(ops_.wait_for_fences(device_.device(), 1, &fence, VK_TRUE, UINT64_MAX), "wait frame fence");
            submitted_[current_frame_] = false;
        }
        if (acquire_pending_[current_frame_]) {
            const VkFence fence = acquire_fences_[current_frame_];
            check(ops_.wait_for_fences(device_.device(), 1, &fence, VK_TRUE, UINT64_MAX), "wait acquire fence");
            acquire_pending_[current_frame_] = false;
        }
    }

    void VulkanSwapchain::advance_frame() {
        current_frame_ = (current_frame_ + 1) % MAX_FRAMES_IN_FLIGHT;
    }

    VkResult VulkanSwapchain::acquire(uint32_t* out_image_index, VkSemaphore* out_image_available) {
        VkSemaphore sem = image_available_semaphores_[current_frame_];
        const VkFence fence = acquire_fences_[current_frame_];
        check(ops_.reset_fences(device_.device(), 1, &fence), "reset acquire fence");
        VkResult r = ops_.acquire_next_image(device_.device(), swapchain_, UINT64_MAX, sem, fence, out_image_index);
        if (r == VK_SUCCESS || r == VK_SUBOPTIMAL_KHR) {
            acquire_pending_[current_frame_] = true;
            if (out_image_available)
                *out_image_available = sem;
        } else if (r != VK_ERROR_OUT_OF_DATE_KHR && r != VK_TIMEOUT && r != VK_NOT_READY) {
            check(r, "acquire image");
        }
        return r;
    }

    VkResult VulkanSwapchain::present(uint32_t image_index, VkSemaphore render_finished) {
        VkPresentInfoKHR pi{};
        pi.sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR;
        pi.waitSemaphoreCount = 1;
        pi.pWaitSemaphores = &render_finished;
        pi.swapchainCount = 1;
        pi.pSwapchains = &swapchain_;
        pi.pImageIndices = &image_index;
        const VkResult result = ops_.queue_present(device_.present_queue(), &pi);
        if (result != VK_SUCCESS && result != VK_SUBOPTIMAL_KHR && result != VK_ERROR_OUT_OF_DATE_KHR)
            check(result, "present image");
        if (result == VK_ERROR_OUT_OF_DATE_KHR)
            failed_ = true; // Retire this generation before any further acquire.
        return result;
    }

    // ---------------------------------------------------------------------------
    // Resize
    // ---------------------------------------------------------------------------

    void VulkanSwapchain::recreate(uint32_t width, uint32_t height) {
        failed_ = true;
        wait_for_retirement();
        destroy_sync_objects();
        destroy_swapchain();
        width_ = width;
        height_ = height;
        try {
            create_swapchain();
            create_sync_objects();
        } catch (...) {
            destroy_sync_objects();
            destroy_swapchain();
            throw;
        }
        current_frame_ = 0;
        submitted_.fill(false);
        acquire_pending_.fill(false);
        failed_ = false;
    }

    void VulkanSwapchain::check(VkResult result, const char* operation) {
        if (result == VK_SUCCESS) return;
        failed_ = true;
        tc_log_error("VulkanSwapchain: %s failed: VkResult=%d; swapchain stopped", operation, int(result));
        throw std::runtime_error(std::string("VulkanSwapchain: ") + operation + " failed: " + std::to_string(result));
    }

    void VulkanSwapchain::require_usable() const {
        if (failed_) {
            tc_log_error("VulkanSwapchain: cannot publish after failure; recreate or destroy the swapchain");
            throw std::runtime_error("VulkanSwapchain is stopped");
        }
    }

    void VulkanSwapchain::wait_for_retirement() {
        // A failed submit may leave an acquired image with no queue wait. Its
        // acquire fence proves the WSI signal operation is complete before the
        // semaphore is destroyed; an unsignalled submit fence is never waited on.
        for (uint32_t slot = 0; slot < MAX_FRAMES_IN_FLIGHT; ++slot) {
            if (acquire_pending_[slot]) {
                check(ops_.wait_for_fences(device_.device(), 1, &acquire_fences_[slot], VK_TRUE, UINT64_MAX),
                      "retire acquired image");
                acquire_pending_[slot] = false;
            }
        }
        check(vkDeviceWaitIdle(device_.device()), "retire swapchain queues");
    }

    void VulkanSwapchain::submit_frame(VkCommandBuffer commands, uint32_t image_index, VkSemaphore available) {
        const VkPipelineStageFlags wait_stage = VK_PIPELINE_STAGE_TRANSFER_BIT;
        const VkSemaphore finished = render_finished_semaphores_[image_index];
        VkSubmitInfo info{};
        info.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
        info.waitSemaphoreCount = 1;
        info.pWaitSemaphores = &available;
        info.pWaitDstStageMask = &wait_stage;
        info.commandBufferCount = 1;
        info.pCommandBuffers = &commands;
        info.signalSemaphoreCount = 1;
        info.pSignalSemaphores = &finished;
        const VkFence fence = in_flight_fences_[current_frame_];
        check(ops_.reset_fences(device_.device(), 1, &fence), "reset submit fence");
        check(ops_.queue_submit(device_.graphics_queue(), 1, &info, fence), "submit frame");
        submitted_[current_frame_] = true;
        // The acquire fence signal is a distinct WSI operation. Keep it pending
        // until a host wait proves it can be reset or destroyed, even after the
        // semaphore wait has been consumed by this submission.
    }

    // ---------------------------------------------------------------------------
    // Compose + present — the one-shot frame publisher
    // ---------------------------------------------------------------------------

    bool VulkanSwapchain::compose_and_present(tgfx::TextureHandle color_tex) {
        require_usable();
        VkTextureResource* rt = device_.get_texture(color_tex);
        if (!rt || !rt->image || !has_flag(rt->desc.usage, TextureUsage::CopySrc) ||
            rt->desc.sample_count != 1 || vk::format_aspect_flags(rt->desc.format) != VK_IMAGE_ASPECT_COLOR_BIT ||
            rt->current_layout == VK_IMAGE_LAYOUT_UNDEFINED) {
            tc_log_error("VulkanSwapchain: invalid compose source texture id=%u", color_tex.id);
            return false; // No image acquired and no synchronization state changed.
        }
        using Clock = std::chrono::steady_clock;
        const bool stats_enabled = vulkan_stats_enabled();
        const auto timestamp = [stats_enabled] {
            return stats_enabled ? Clock::now() : Clock::time_point{};
        };
        const auto total0 = timestamp();

        // 1. Wait until the command buffer + sync objects for this slot
        //    are free.
        const auto wait0 = timestamp();
        wait_for_current_frame();
        const auto wait1 = timestamp();

        // 2. Acquire an image from the swapchain.
        uint32_t image_idx = 0;
        VkSemaphore image_available = VK_NULL_HANDLE;
        const auto acquire0 = timestamp();
        VkResult ar = acquire(&image_idx, &image_available);
        const auto acquire1 = timestamp();
        if (ar == VK_ERROR_OUT_OF_DATE_KHR) {
            return true; // caller should recreate
        }
        if (ar != VK_SUCCESS && ar != VK_SUBOPTIMAL_KHR) {
            return false;
        }

        // 4. Record the compose command buffer: transitions + blit +
        //    present-src transition.
        const auto record0 = timestamp();
        VkCommandBuffer cb = compose_command_buffers_[current_frame_];
        check(vkResetCommandBuffer(cb, 0), "reset compose commands");

        VkCommandBufferBeginInfo begin{};
        begin.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        begin.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        check(vkBeginCommandBuffer(cb, &begin), "begin compose commands");

        VkImage sc_image = images_[image_idx];
        VkImageSubresourceRange range{};
        range.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
        range.levelCount = 1;
        range.layerCount = 1;

        // rt_tex: current layout → TRANSFER_SRC.
        VkImageMemoryBarrier rt_to_src{};
        rt_to_src.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        rt_to_src.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        rt_to_src.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        rt_to_src.oldLayout = rt->current_layout;
        rt_to_src.newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        rt_to_src.image = rt->image;
        rt_to_src.subresourceRange = range;
        rt_to_src.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;
        rt_to_src.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
        vkCmdPipelineBarrier(cb,
                             VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                             VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0,
                             0,
                             nullptr,
                             0,
                             nullptr,
                             1,
                             &rt_to_src);

        // swapchain image: UNDEFINED → TRANSFER_DST.
        VkImageMemoryBarrier sc_to_dst{};
        sc_to_dst.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        sc_to_dst.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        sc_to_dst.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        sc_to_dst.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        sc_to_dst.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        sc_to_dst.image = sc_image;
        sc_to_dst.subresourceRange = range;
        sc_to_dst.srcAccessMask = 0;
        sc_to_dst.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
        vkCmdPipelineBarrier(cb,
                             VK_PIPELINE_STAGE_TRANSFER_BIT,
                             VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0,
                             0,
                             nullptr,
                             0,
                             nullptr,
                             1,
                             &sc_to_dst);

        const bool raw_copy = rt->desc.width == width_ && rt->desc.height == height_ &&
                              rt->desc.sample_count == 1 && vk::to_vk_format(rt->desc.format) == format_;
        if (raw_copy) {
            VkImageCopy copy{};
            copy.srcSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
            copy.srcSubresource.layerCount = 1;
            copy.dstSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
            copy.dstSubresource.layerCount = 1;
            copy.extent = {width_, height_, 1};
            vkCmdCopyImage(cb,
                           rt->image,
                           VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                           sc_image,
                           VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                           1,
                           &copy);
        } else {
            // Legacy callers may still provide a differently-sized source.
            // Presentation-aware callers pre-transform into a target-native
            // texture and therefore take the raw-copy path above.
            VkImageBlit blit{};
            blit.srcSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
            blit.srcSubresource.layerCount = 1;
            blit.srcOffsets[0] = {0, 0, 0};
            blit.srcOffsets[1] = {static_cast<int32_t>(rt->desc.width), static_cast<int32_t>(rt->desc.height), 1};
            blit.dstSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
            blit.dstSubresource.layerCount = 1;
            blit.dstOffsets[0] = {0, 0, 0};
            blit.dstOffsets[1] = {static_cast<int32_t>(width_), static_cast<int32_t>(height_), 1};
            vkCmdBlitImage(cb,
                           rt->image,
                           VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                           sc_image,
                           VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                           1,
                           &blit,
                           VK_FILTER_LINEAR);
        }

        // swapchain image: TRANSFER_DST → PRESENT_SRC.
        VkImageMemoryBarrier sc_to_present{};
        sc_to_present.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        sc_to_present.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        sc_to_present.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        sc_to_present.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        sc_to_present.newLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        sc_to_present.image = sc_image;
        sc_to_present.subresourceRange = range;
        sc_to_present.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
        sc_to_present.dstAccessMask = 0;
        vkCmdPipelineBarrier(cb,
                             VK_PIPELINE_STAGE_TRANSFER_BIT,
                             VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
                             0,
                             0,
                             nullptr,
                             0,
                             nullptr,
                             1,
                             &sc_to_present);

        // Reflect the transition on the tgfx2 side — next render pass
        // will see TRANSFER_SRC and transition appropriately.
        check(vkEndCommandBuffer(cb), "end compose commands");
        const auto record1 = timestamp();

        // 5. Submit waiting on image_available, signalling render_finished
        //    for this image and tripping the in-flight fence.
        VkSemaphore render_done = render_finished_semaphores_[image_idx];
        const auto submit0 = timestamp();
        submit_frame(cb, image_idx, image_available);
        rt->current_layout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        const auto submit1 = timestamp();

        // 6. Present. OUT_OF_DATE requires recreation. SUBOPTIMAL remains usable:
        // Android reports it continuously when identity differs from the current
        // surface transform, and resize callbacks already recreate explicitly.
        const auto present0 = timestamp();
        VkResult pr = present(image_idx, render_done);
        const auto present1 = timestamp();
        const bool should_recreate = swapchain_result_requires_recreate(pr);

        advance_frame();
        const auto total1 = timestamp();

        if (!stats_enabled) {
            return should_recreate;
        }

        auto& stats = compose_stats_;
        ++stats.frames;
        stats.wait_us += us_between(wait0, wait1);
        stats.acquire_us += us_between(acquire0, acquire1);
        stats.record_us += us_between(record0, record1);
        stats.submit_us += us_between(submit0, submit1);
        stats.present_us += us_between(present0, present1);
        stats.total_us += us_between(total0, total1);

        auto now = Clock::now();
        if (std::chrono::duration<double>(now - stats.window_start).count() >= 1.0) {
            const double denom = stats.frames > 0 ? static_cast<double>(stats.frames) : 1.0;
            tc_log(TC_LOG_INFO,
                   "[tgfx2-vulkan] swapchain stats: frames=%llu "
                   "avg_total_ms=%.3f avg_wait_ms=%.3f avg_acquire_ms=%.3f "
                   "avg_record_ms=%.3f avg_submit_ms=%.3f avg_present_ms=%.3f",
                   static_cast<unsigned long long>(stats.frames),
                   (stats.total_us / denom) / 1000.0,
                   (stats.wait_us / denom) / 1000.0,
                   (stats.acquire_us / denom) / 1000.0,
                   (stats.record_us / denom) / 1000.0,
                   (stats.submit_us / denom) / 1000.0,
                   (stats.present_us / denom) / 1000.0);
            stats.window_start = now;
            stats.frames = 0;
            stats.wait_us = 0.0;
            stats.acquire_us = 0.0;
            stats.record_us = 0.0;
            stats.submit_us = 0.0;
            stats.present_us = 0.0;
            stats.total_us = 0.0;
        }
        return should_recreate;
    }

    bool VulkanSwapchain::clear_and_present(termin::LinearColor color) {
        wait_for_current_frame();

        uint32_t image_idx = 0;
        VkSemaphore image_available = VK_NULL_HANDLE;
        VkResult ar = acquire(&image_idx, &image_available);
        if (ar == VK_ERROR_OUT_OF_DATE_KHR) {
            return true;
        }
        if (ar != VK_SUCCESS && ar != VK_SUBOPTIMAL_KHR) {
            return false;
        }
        VkCommandBuffer cb = compose_command_buffers_[current_frame_];
        check(vkResetCommandBuffer(cb, 0), "reset clear commands");

        VkCommandBufferBeginInfo begin{};
        begin.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        begin.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        check(vkBeginCommandBuffer(cb, &begin), "begin clear commands");

        VkImageSubresourceRange range{};
        range.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
        range.levelCount = 1;
        range.layerCount = 1;

        VkImage image = images_[image_idx];
        VkImageMemoryBarrier to_dst{};
        to_dst.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        to_dst.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        to_dst.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        to_dst.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        to_dst.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        to_dst.image = image;
        to_dst.subresourceRange = range;
        to_dst.srcAccessMask = 0;
        to_dst.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
        vkCmdPipelineBarrier(cb,
                             VK_PIPELINE_STAGE_TRANSFER_BIT,
                             VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0,
                             0,
                             nullptr,
                             0,
                             nullptr,
                             1,
                             &to_dst);

        VkClearColorValue clear{};
        clear.float32[0] = color.r;
        clear.float32[1] = color.g;
        clear.float32[2] = color.b;
        clear.float32[3] = color.a;
        vkCmdClearColorImage(cb, image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &clear, 1, &range);

        VkImageMemoryBarrier to_present{};
        to_present.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        to_present.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        to_present.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        to_present.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        to_present.newLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        to_present.image = image;
        to_present.subresourceRange = range;
        to_present.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
        to_present.dstAccessMask = 0;
        vkCmdPipelineBarrier(cb,
                             VK_PIPELINE_STAGE_TRANSFER_BIT,
                             VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
                             0,
                             0,
                             nullptr,
                             0,
                             nullptr,
                             1,
                             &to_present);

        check(vkEndCommandBuffer(cb), "end clear commands");
        VkSemaphore render_done = render_finished_semaphores_[image_idx];
        submit_frame(cb, image_idx, image_available);

        VkResult pr = present(image_idx, render_done);
        const bool should_recreate = swapchain_result_requires_recreate(pr);
        advance_frame();
        return should_recreate;
    }

} // namespace tgfx

#endif // TGFX2_HAS_VULKAN
