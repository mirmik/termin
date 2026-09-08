#pragma once

#include <tcbase/tc_log.h>
#include <vk_mem_alloc.h>

#include <cstring>
#include <span>

namespace tgfx::vulkan_detail {

    struct UploadMemoryOps {
        decltype(&vmaCreateBuffer) create_buffer = vmaCreateBuffer;
        decltype(&vmaMapMemory) map = vmaMapMemory;
        decltype(&vmaUnmapMemory) unmap = vmaUnmapMemory;
        decltype(&vmaDestroyBuffer) destroy_buffer = vmaDestroyBuffer;
    };

    inline bool copy_to_mapped_allocation(VmaAllocator allocator,
                                          VmaAllocation allocation,
                                          VkDeviceSize offset,
                                          std::span<const uint8_t> data,
                                          const UploadMemoryOps& ops = {}) {
        void* mapped = nullptr;
        const VkResult map_result = ops.map(allocator, allocation, &mapped);
        if (map_result != VK_SUCCESS || !mapped) {
            tc_log(TC_LOG_ERROR, "[Vulkan upload] map failed: VkResult=%d", static_cast<int>(map_result));
            // A successful VMA map owns a matching unmap even if a faulty
            // implementation returned no pointer.
            if (map_result == VK_SUCCESS)
                ops.unmap(allocator, allocation);
            return false;
        }
        std::memcpy(static_cast<uint8_t*>(mapped) + offset, data.data(), data.size());
        ops.unmap(allocator, allocation);
        return true;
    }

    inline bool create_and_fill_upload_buffer(VmaAllocator allocator,
                                              const VkBufferCreateInfo& buffer_info,
                                              const VmaAllocationCreateInfo& allocation_info,
                                              std::span<const uint8_t> data,
                                              VkBuffer& buffer,
                                              VmaAllocation& allocation,
                                              const UploadMemoryOps& ops = {}) {
        buffer = VK_NULL_HANDLE;
        allocation = VK_NULL_HANDLE;
        const VkResult create_result =
            ops.create_buffer(allocator, &buffer_info, &allocation_info, &buffer, &allocation, nullptr);
        if (create_result != VK_SUCCESS || buffer == VK_NULL_HANDLE || allocation == VK_NULL_HANDLE) {
            tc_log(TC_LOG_ERROR,
                   "[Vulkan upload] staging allocation failed: VkResult=%d",
                   static_cast<int>(create_result));
            return false;
        }
        if (!copy_to_mapped_allocation(allocator, allocation, 0, data, ops)) {
            ops.destroy_buffer(allocator, buffer, allocation);
            buffer = VK_NULL_HANDLE;
            allocation = VK_NULL_HANDLE;
            return false;
        }
        return true;
    }

} // namespace tgfx::vulkan_detail
