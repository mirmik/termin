#pragma once

#include <vk_mem_alloc.h>
#include <tcbase/tc_log.h>
#include <cstring>
#include <span>

namespace tgfx::vulkan_detail {

    // Explicit allocator operations also allow a non-coherent memory model in
    // tests on machines whose host-visible memory is always coherent.
    struct ReadbackMemoryOps {
        decltype(&vmaMapMemory) map = vmaMapMemory;
        decltype(&vmaInvalidateAllocation) invalidate = vmaInvalidateAllocation;
        decltype(&vmaUnmapMemory) unmap = vmaUnmapMemory;
    };

    inline bool copy_completed_readback(VkResult completion, VmaAllocator allocator, VmaAllocation allocation,
                                        VkDeviceSize offset, std::span<uint8_t> output,
                                        const ReadbackMemoryOps& ops = {}) {
        if (completion != VK_SUCCESS) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] GPU completion failed: VkResult=%d", int(completion));
            return false;
        }
        void* mapped = nullptr;
        const auto map_result = ops.map(allocator, allocation, &mapped);
        if (map_result != VK_SUCCESS || !mapped) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] map failed: VkResult=%d", int(map_result));
            if (map_result == VK_SUCCESS)
                ops.unmap(allocator, allocation);
            return false;
        }
        // Invalidate while mapped, after GPU completion and before any CPU
        // access. VMA rounds to nonCoherentAtomSize and skips coherent memory.
        const auto invalidate_result = ops.invalidate(allocator, allocation, offset, output.size());
        if (invalidate_result == VK_SUCCESS) {
            std::memcpy(output.data(), static_cast<const uint8_t*>(mapped) + offset, output.size());
        } else {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] invalidate failed: VkResult=%d", int(invalidate_result));
        }
        ops.unmap(allocator, allocation);
        return invalidate_result == VK_SUCCESS;
    }

} // namespace tgfx::vulkan_detail
