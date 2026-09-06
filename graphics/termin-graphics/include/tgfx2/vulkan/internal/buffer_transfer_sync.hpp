#pragma once

#include "tgfx2/enums.hpp"
#include <vulkan/vulkan.h>

namespace tgfx::vulkan_detail {

    struct BufferAccessScope {
        VkPipelineStageFlags stages;
        VkAccessFlags accesses;
    };

    inline BufferAccessScope buffer_access_scope(BufferUsage usage) {
        // Every native buffer supports staging uploads; CopySrc also permits
        // readbacks/copies. Include earlier copies and repeated overwrites.
        BufferAccessScope scope{VK_PIPELINE_STAGE_TRANSFER_BIT,
                                VK_ACCESS_TRANSFER_READ_BIT | VK_ACCESS_TRANSFER_WRITE_BIT};
        if (has_flag(usage, BufferUsage::Vertex)) {
            scope.stages |= VK_PIPELINE_STAGE_VERTEX_INPUT_BIT;
            scope.accesses |= VK_ACCESS_VERTEX_ATTRIBUTE_READ_BIT;
        }
        if (has_flag(usage, BufferUsage::Index)) {
            scope.stages |= VK_PIPELINE_STAGE_VERTEX_INPUT_BIT;
            scope.accesses |= VK_ACCESS_INDEX_READ_BIT;
        }
        if (has_flag(usage, BufferUsage::Uniform) || has_flag(usage, BufferUsage::Storage)) {
            scope.stages |= VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;
        }
        if (has_flag(usage, BufferUsage::Uniform))
            scope.accesses |= VK_ACCESS_UNIFORM_READ_BIT;
        if (has_flag(usage, BufferUsage::Storage))
            scope.accesses |= VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT;
        return scope;
    }

    inline void buffer_barrier(VkCommandBuffer cmd, VkBuffer buffer, VkDeviceSize offset, VkDeviceSize size,
                               BufferAccessScope source, BufferAccessScope destination) {
        VkBufferMemoryBarrier barrier{};
        barrier.sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER;
        barrier.srcAccessMask = source.accesses;
        barrier.dstAccessMask = destination.accesses;
        barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.buffer = buffer;
        barrier.offset = offset;
        barrier.size = size;
        vkCmdPipelineBarrier(cmd, source.stages, destination.stages, 0,
                             0, nullptr, 1, &barrier, 0, nullptr);
    }

    inline void buffer_before_transfer(VkCommandBuffer cmd, VkBuffer buffer, BufferUsage usage,
                                       VkDeviceSize offset, VkDeviceSize size, VkAccessFlags transfer_access) {
        buffer_barrier(cmd, buffer, offset, size, buffer_access_scope(usage),
                       {VK_PIPELINE_STAGE_TRANSFER_BIT, transfer_access});
    }

    inline void buffer_after_transfer_write(VkCommandBuffer cmd, VkBuffer buffer, BufferUsage usage,
                                            VkDeviceSize offset, VkDeviceSize size) {
        buffer_barrier(cmd, buffer, offset, size,
                       {VK_PIPELINE_STAGE_TRANSFER_BIT, VK_ACCESS_TRANSFER_WRITE_BIT}, buffer_access_scope(usage));
    }

} // namespace tgfx::vulkan_detail
