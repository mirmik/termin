#include "tgfx2/vulkan/vulkan_render_device.hpp"

#include <cstdio>
#include <cstring>
#include <exception>

// This executable deliberately returns success even for invalid native work.
// The enclosing CTest regression proves that diagnostics override that result.
int main(int argc, char** argv) {
    if (argc != 2)
        return 2;
    const char* mode = argv[1];
    try {
        tgfx::VulkanDeviceCreateInfo info;
        info.enable_validation = false; // The required test gate must override this.
        if (std::strcmp(mode, "init") == 0)
            info.instance_extensions.push_back("VK_TERMIN_intentionally_missing_extension");
        tgfx::VulkanRenderDevice device(info);
        if (std::strcmp(mode, "invalid") == 0) {
            VkBufferCreateInfo ci{};
            ci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
            ci.size = 0; // VUID-VkBufferCreateInfo-size-00912
            ci.usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT;
            VkBuffer buffer = VK_NULL_HANDLE;
            if (vkCreateBuffer(device.device(), &ci, nullptr, &buffer) == VK_SUCCESS)
                vkDestroyBuffer(device.device(), buffer, nullptr);
        } else if (std::strcmp(mode, "shutdown") == 0) {
            VkSemaphoreCreateInfo ci{};
            ci.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;
            VkSemaphore semaphore = VK_NULL_HANDLE;
            if (vkCreateSemaphore(device.device(), &ci, nullptr, &semaphore) != VK_SUCCESS)
                return 2;
            // Deliberately leave an unowned native child for vkDestroyDevice
            // to diagnose. No command ever refers to this semaphore.
        } else if (std::strcmp(mode, "clean") != 0 && std::strcmp(mode, "missing-layer") != 0) {
            return 2;
        }
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Vulkan device creation failed, skipping: %s\n", e.what());
    }
    std::puts("probe returning zero");
    std::fflush(stdout); // LeakSanitizer may terminate before normal stdio teardown.
    return 0;
}
