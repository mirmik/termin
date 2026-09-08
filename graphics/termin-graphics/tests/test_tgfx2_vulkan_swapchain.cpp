#define SDL_MAIN_HANDLED
#include "tgfx2/i_command_list.hpp"
#include "tgfx2/vulkan/internal/swapchain_ops.hpp"
#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/vulkan/vulkan_swapchain.hpp"
#include <SDL.h>
#include <SDL_vulkan.h>

#include <algorithm>
#include <array>
#include <cstdio>
#include <stdexcept>
#include <vector>

namespace {
    void require(bool condition, const char* message) {
        if (!condition)
            throw std::runtime_error(message);
    }

    struct Trace {
        VkResult acquire_result = VK_SUCCESS;
        VkResult submit_result = VK_SUCCESS;
        VkResult present_result = VK_SUCCESS;
        unsigned acquires = 0, submits = 0, presents = 0, waits = 0, resets = 0;
        unsigned fail_reset_after = 0;
        bool fail_wait = false;
        VkFence failed_submit_fence = VK_NULL_HANDLE;
        uint32_t image = 0;
        VkSemaphore signal = VK_NULL_HANDLE;
        std::vector<VkSemaphore> image_signals;
        bool valid = true;
    } trace;

    VKAPI_ATTR VkResult VKAPI_CALL
    wait_fences(VkDevice device, uint32_t count, const VkFence* fences, VkBool32 all, uint64_t timeout) {
        ++trace.waits;
        for (uint32_t i = 0; i < count; ++i) {
            if (fences[i] == trace.failed_submit_fence) {
                trace.valid = false;
                return VK_TIMEOUT; // Fail deterministically instead of hanging on the bug.
            }
        }
        if (trace.fail_wait) {
            trace.fail_wait = false;
            return VK_ERROR_OUT_OF_DEVICE_MEMORY;
        }
        return vkWaitForFences(device, count, fences, all, timeout);
    }

    VKAPI_ATTR VkResult VKAPI_CALL reset_fences(VkDevice device, uint32_t count, const VkFence* fences) {
        ++trace.resets;
        if (trace.fail_reset_after && --trace.fail_reset_after == 0)
            return VK_ERROR_OUT_OF_DEVICE_MEMORY;
        return vkResetFences(device, count, fences);
    }

    VKAPI_ATTR VkResult VKAPI_CALL acquire(VkDevice device,
                                           VkSwapchainKHR swapchain,
                                           uint64_t timeout,
                                           VkSemaphore semaphore,
                                           VkFence fence,
                                           uint32_t* image) {
        ++trace.acquires;
        if (trace.acquire_result != VK_SUCCESS)
            return trace.acquire_result;
        const auto result = vkAcquireNextImageKHR(device, swapchain, timeout, semaphore, fence, image);
        if (result == VK_SUCCESS || result == VK_SUBOPTIMAL_KHR)
            trace.image = *image;
        return result;
    }

    VKAPI_ATTR VkResult VKAPI_CALL submit(VkQueue queue, uint32_t count, const VkSubmitInfo* info, VkFence fence) {
        ++trace.submits;
        if (trace.submit_result != VK_SUCCESS) {
            trace.failed_submit_fence = fence;
            return trace.submit_result;
        }
        trace.valid &= count == 1 && info[0].signalSemaphoreCount == 1;
        if (count == 1 && info[0].signalSemaphoreCount == 1) {
            trace.signal = info[0].pSignalSemaphores[0];
            trace.valid &= trace.image < trace.image_signals.size();
            if (trace.image < trace.image_signals.size()) {
                auto& previous = trace.image_signals[trace.image];
                trace.valid &= previous == VK_NULL_HANDLE || previous == trace.signal;
                previous = trace.signal;
                for (size_t i = 0; i < trace.image_signals.size(); ++i)
                    if (i != trace.image)
                        trace.valid &= trace.image_signals[i] != trace.signal;
            }
        }
        return vkQueueSubmit(queue, count, info, fence);
    }

    VKAPI_ATTR VkResult VKAPI_CALL present(VkQueue queue, const VkPresentInfoKHR* info) {
        ++trace.presents;
        trace.valid &= info->waitSemaphoreCount == 1 && info->pWaitSemaphores[0] == trace.signal;
        if (trace.present_result != VK_SUCCESS)
            return trace.present_result;
        return vkQueuePresentKHR(queue, info);
    }

    template <class Call> void throws(Call call) {
        bool rejected = false;
        try {
            call();
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        require(rejected, "fatal WSI failure was not reported");
    }

    void reset_trace(const tgfx::VulkanSwapchain& swapchain) {
        trace = {};
        trace.image_signals.resize(swapchain.image_count(), VK_NULL_HANDLE);
    }

    void exercise(tgfx::VulkanRenderDevice& device,
                  VkSurfaceKHR surface,
                  SDL_Window* window,
                  tgfx::PresentationMode mode,
                  bool finish_with_terminal_failure) {
        tgfx::vulkan_detail::SwapchainOps ops;
        ops.acquire_next_image = acquire;
        ops.queue_submit = submit;
        ops.queue_present = present;
        ops.wait_for_fences = wait_fences;
        ops.reset_fences = reset_fences;
        tgfx::VulkanSwapchain swapchain(device, surface, 96, 96, mode, ops);
        reset_trace(swapchain);
        tgfx::TextureDesc desc;
        desc.width = desc.height = 16;
        desc.usage = tgfx::TextureUsage::CopySrc | tgfx::TextureUsage::CopyDst;
        const auto source = device.create_texture(desc);
        std::vector<uint8_t> pixels(16 * 16 * 4, 127);
        device.upload_texture(source, pixels);
        auto producer = device.create_command_list();
        producer->begin();
        producer->end();
        device.submit(*producer);
        device.wait_idle();
        producer.reset();
        const auto clear = [&] {
            return swapchain.clear_and_present({0.2f, 0.4f, 0.6f, 1.0f});
        };
        const auto restore = [&] {
            swapchain.recreate(96, 96);
            require(trace.valid, "retirement waited on an unsubmitted fence");
            reset_trace(swapchain);
        };

        require(!swapchain.compose_and_present({}), "invalid source requested recreation");
        require(trace.acquires == 0, "invalid source acquired an image");
        for (const auto result : {VK_ERROR_OUT_OF_DATE_KHR, VK_TIMEOUT, VK_NOT_READY}) {
            const auto resets = trace.resets;
            trace.acquire_result = result;
            require(clear() == (result == VK_ERROR_OUT_OF_DATE_KHR), "acquire recovery result mismatch");
            require(trace.submits == 0 && trace.presents == 0, "failed acquisition submitted or presented");
            require(trace.resets == resets + 1 && trace.waits == 0,
                    "failed acquisition touched submit fence or waited for nonexistent work");
            trace.acquire_result = VK_SUCCESS;
        }
        restore();

        // Acquire/present failures belong to this swapchain generation and a
        // recreate may recover them. Submit/fence failures are exercised once
        // at the end because they now poison the shared render device.
        for (unsigned failure : {0u, 2u}) {
            if (failure == 0)
                trace.acquire_result = VK_ERROR_OUT_OF_DEVICE_MEMORY;
            if (failure == 2)
                trace.present_result = VK_ERROR_OUT_OF_DEVICE_MEMORY;
            throws(clear);
            if (failure == 0)
                require(trace.presents == 0, "failed acquire/submit reached present");
            const std::array<unsigned, 5> calls{
                trace.acquires, trace.submits, trace.presents, trace.waits, trace.resets};
            throws(clear);
            throws([&] { swapchain.compose_and_present(source); });
            require(
                calls ==
                    std::array<unsigned, 5>{trace.acquires, trace.submits, trace.presents, trace.waits, trace.resets},
                "poisoned swapchain issued native work");
            restore();
            require(!clear(), "recreated swapchain could not present");
            restore();
        }

        for (unsigned frame = 0; frame < 120; ++frame) {
            SDL_Event event;
            while (SDL_PollEvent(&event)) {
            }
            if (frame > 0 && frame % 30 == 0) {
                const int size = frame % 60 == 0 ? 96 : 128;
                SDL_SetWindowSize(window, size, size);
                SDL_PumpEvents();
                int width = 0, height = 0;
                SDL_Vulkan_GetDrawableSize(window, &width, &height);
                require(width > 0 && height > 0, "resize produced empty drawable");
                require(trace.valid, "presentation semaphore belongs to another image");
                swapchain.recreate(static_cast<uint32_t>(width), static_cast<uint32_t>(height));
                reset_trace(swapchain);
            }
            const bool recreate = frame % 2 == 0 ? clear() : swapchain.compose_and_present(source);
            if (recreate)
                restore();
            require(trace.valid, "presentation semaphore mismatch");
        }
        require(trace.presents > 0, "stress loop presented no images");
        if (finish_with_terminal_failure) {
            // Leave a reset-but-unsubmitted fence for teardown. The failed
            // submit poisons both this swapchain and the shared device; every
            // retry must stop before another native operation.
            trace.submit_result = VK_ERROR_OUT_OF_DEVICE_MEMORY;
            throws(clear);
            require(device.has_terminal_error(), "swapchain submit failure did not poison shared device");
            const std::array<unsigned, 5> calls{
                trace.acquires, trace.submits, trace.presents, trace.waits, trace.resets};
            throws(clear);
            require(calls ==
                        std::array<unsigned, 5>{trace.acquires, trace.submits, trace.presents, trace.waits, trace.resets},
                    "terminal device retry issued native swapchain work");
        }
        device.wait_idle();
        device.destroy(source);
    }
} // namespace

int main() {
    SDL_Window* window = nullptr;
    try {
        require(SDL_Init(SDL_INIT_VIDEO) == 0, SDL_GetError());
        window = SDL_CreateWindow("Vulkan swapchain lifecycle",
                                  SDL_WINDOWPOS_UNDEFINED,
                                  SDL_WINDOWPOS_UNDEFINED,
                                  96,
                                  96,
                                  SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE | SDL_WINDOW_SHOWN);
        require(window != nullptr, SDL_GetError());
        uint32_t count = 0;
        require(SDL_Vulkan_GetInstanceExtensions(window, &count, nullptr), SDL_GetError());
        std::vector<const char*> extensions(count);
        require(SDL_Vulkan_GetInstanceExtensions(window, &count, extensions.data()), SDL_GetError());
        const auto make_surface = [window](VkInstance instance) {
            VkSurfaceKHR surface = VK_NULL_HANDLE;
            require(SDL_Vulkan_CreateSurface(window, instance, &surface), SDL_GetError());
            return surface;
        };
        tgfx::VulkanDeviceCreateInfo info;
        info.instance_extensions = extensions;
        info.presentation_probe_surface_factory = make_surface;
        info.enable_validation = true;
        {
            tgfx::VulkanRenderDevice device(info);
            const auto surface = make_surface(device.instance());
            try {
                VkSwapchainCreateInfoKHR sharing{};
                const std::array<uint32_t, 2> same{3, 3}, different{3, 7};
                tgfx::vulkan_detail::configure_swapchain_sharing(sharing, different);
                require(sharing.imageSharingMode == VK_SHARING_MODE_CONCURRENT && sharing.queueFamilyIndexCount == 2 &&
                            sharing.pQueueFamilyIndices[0] == 3 && sharing.pQueueFamilyIndices[1] == 7,
                        "split family sharing incorrect");
                tgfx::vulkan_detail::configure_swapchain_sharing(sharing, same);
                require(sharing.imageSharingMode == VK_SHARING_MODE_EXCLUSIVE && sharing.queueFamilyIndexCount == 0 &&
                            sharing.pQueueFamilyIndices == nullptr,
                        "same family sharing incorrect");
                uint32_t mode_count = 0;
                require(vkGetPhysicalDeviceSurfacePresentModesKHR(
                            device.physical_device(), surface, &mode_count, nullptr) == VK_SUCCESS,
                        "present modes query failed");
                std::vector<VkPresentModeKHR> modes(mode_count);
                require(vkGetPhysicalDeviceSurfacePresentModesKHR(
                            device.physical_device(), surface, &mode_count, modes.data()) == VK_SUCCESS,
                        "present modes query failed");
                const bool has_immediate =
                    std::find(modes.begin(), modes.end(), VK_PRESENT_MODE_IMMEDIATE_KHR) != modes.end();
                exercise(device, surface, window, tgfx::PresentationMode::VSync, !has_immediate);
                require(trace.valid, "destructor waited on an unsubmitted fence");
                if (has_immediate) {
                    exercise(device, surface, window, tgfx::PresentationMode::Immediate, true);
                    require(trace.valid, "destructor waited on an unsubmitted fence");
                    std::puts("Immediate stress passed");
                } else {
                    std::puts("Immediate unavailable; FIFO exercised");
                }
            } catch (...) {
                vkDestroySurfaceKHR(device.instance(), surface, nullptr);
                throw;
            }
            vkDestroySurfaceKHR(device.instance(), surface, nullptr);
        }
        SDL_DestroyWindow(window);
        SDL_Quit();
        std::puts("Swapchain: acquire/submit/present failures, resize and image semaphore stress passed");
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Swapchain lifecycle: %s\n", error.what());
        if (window)
            SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }
}
