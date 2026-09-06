#pragma once

#include <array>
#include <vulkan/vulkan.h>

namespace tgfx::vulkan_detail {
    // Native WSI boundary, injectable for fault tests of the actual lifecycle.
    struct SwapchainOps {
        PFN_vkWaitForFences wait_for_fences = vkWaitForFences;
        PFN_vkResetFences reset_fences = vkResetFences;
        PFN_vkAcquireNextImageKHR acquire_next_image = vkAcquireNextImageKHR;
        PFN_vkQueueSubmit queue_submit = vkQueueSubmit;
        PFN_vkQueuePresentKHR queue_present = vkQueuePresentKHR;
    };

    inline void configure_swapchain_sharing(VkSwapchainCreateInfoKHR& info,
                                             const std::array<uint32_t, 2>& families) {
        const bool separate = families[0] != families[1];
        info.imageSharingMode = separate ? VK_SHARING_MODE_CONCURRENT : VK_SHARING_MODE_EXCLUSIVE;
        info.queueFamilyIndexCount = separate ? 2u : 0u;
        info.pQueueFamilyIndices = separate ? families.data() : nullptr;
    }
}
