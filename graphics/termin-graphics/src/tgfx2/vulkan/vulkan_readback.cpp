#ifdef TGFX2_HAS_VULKAN

#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/vulkan/internal/buffer_transfer_sync.hpp"
#include "tgfx2/vulkan/internal/readback_memory.hpp"

namespace tgfx {

    bool VulkanRenderDevice::create_readback_buffer(size_t size, VkBuffer& buffer, VmaAllocation& allocation) {
        VkBufferCreateInfo ci{};
        ci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
        ci.size = size;
        ci.usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT;
        VmaAllocationCreateInfo alloc{};
        alloc.usage = VMA_MEMORY_USAGE_GPU_TO_CPU;
        const auto result = vmaCreateBuffer(allocator_, &ci, &alloc, &buffer, &allocation, nullptr);
        if (result != VK_SUCCESS) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] staging allocation failed (%zu bytes): VkResult=%d", size, int(result));
            return false;
        }
        return true;
    }

    VkCommandBuffer VulkanRenderDevice::begin_readback_commands() {
        device_failure_.require_operational("synchronous readback recording");
        VkCommandBufferAllocateInfo ai{};
        ai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
        ai.commandPool = command_pool_;
        ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        ai.commandBufferCount = 1;
        VkCommandBuffer cb = VK_NULL_HANDLE;
        auto result = vkAllocateCommandBuffers(device_, &ai, &cb);
        if (result != VK_SUCCESS) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] command allocation failed: VkResult=%d", int(result));
            return VK_NULL_HANDLE;
        }
        VkCommandBufferBeginInfo bi{};
        bi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        result = vkBeginCommandBuffer(cb, &bi);
        if (result != VK_SUCCESS) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] command begin failed: VkResult=%d", int(result));
            vkFreeCommandBuffers(device_, command_pool_, 1, &cb);
            return VK_NULL_HANDLE;
        }
        return cb;
    }

    bool VulkanRenderDevice::finish_readback(VkCommandBuffer cb, VkBuffer staging, VmaAllocation allocation,
                                            VkDeviceSize offset, std::span<uint8_t> output) {
        // Synchronous readback deliberately blocks. The producer must already
        // have been submitted; unsubmitted draw buffers are not executed here.
        device_failure_.require_operational("synchronous readback submit");
        const VkResult end_result = vkEndCommandBuffer(cb);
        if (end_result != VK_SUCCESS) {
            (void)vulkan_detail::copy_completed_readback(end_result, allocator_, allocation, offset, output);
            vkFreeCommandBuffers(device_, command_pool_, 1, &cb);
            if (staging)
                vmaDestroyBuffer(allocator_, staging, allocation);
            device_failure_.fail("synchronous readback command end", end_result);
        }

        VkSubmitInfo si{};
        si.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
        si.commandBufferCount = 1;
        si.pCommandBuffers = &cb;
        try {
            vulkan_detail::submit_or_fail(
                device_failure_, device_ops_, graphics_queue_, si, VK_NULL_HANDLE, "synchronous readback submit");
        } catch (...) {
            (void)vulkan_detail::copy_completed_readback(
                device_failure_.result(), allocator_, allocation, offset, output);
            vkFreeCommandBuffers(device_, command_pool_, 1, &cb);
            if (staging)
                vmaDestroyBuffer(allocator_, staging, allocation);
            throw;
        }

        const VkResult result = device_ops_.queue_wait_idle(graphics_queue_);
        const bool ok = vulkan_detail::copy_completed_readback(result, allocator_, allocation, offset, output);
        if (result != VK_SUCCESS) {
            // A failed wait is not proof that the GPU stopped accessing these
            // objects. Terminal teardown owns their cleanup; never publish or
            // free in-flight bytes here, and never submit a retry.
            defer_cmd_buffer_free(cb);
            if (staging)
                defer_vma_buffer_destroy(staging, allocation);
            device_failure_.fail("synchronous readback queue idle wait", result);
        } else {
            vkFreeCommandBuffers(device_, command_pool_, 1, &cb);
            if (staging)
                vmaDestroyBuffer(allocator_, staging, allocation);
        }
        return ok;
    }

    bool VulkanRenderDevice::validate_image_readback(const VkTextureResource& image, VkOffset3D offset,
                                                     VkExtent3D extent) {
        if (!has_flag(image.desc.usage, TextureUsage::CopySrc) || image.desc.sample_count != 1 ||
            image.current_layout == VK_IMAGE_LAYOUT_UNDEFINED || offset.x < 0 || offset.y < 0 || offset.z != 0 ||
            extent.width == 0 || extent.height == 0 || extent.depth != 1 ||
            uint32_t(offset.x) > image.desc.width || extent.width > image.desc.width - uint32_t(offset.x) ||
            uint32_t(offset.y) > image.desc.height || extent.height > image.desc.height - uint32_t(offset.y)) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] image requires initialized single-sample CopySrc and valid bounds");
            return false;
        }
        return true;
    }

    void VulkanRenderDevice::record_image_readback(VkCommandBuffer cb, VkTextureResource& image, VkBuffer staging,
                                                   VkImageAspectFlags aspect, VkOffset3D offset,
                                                   VkExtent3D extent, size_t size) {
        const auto previous = image.current_layout;
        transition_image_layout(cb, image.image, previous, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, aspect,
                                image.desc.array_layers);
        VkBufferImageCopy copy{};
        copy.imageSubresource = {aspect, 0, 0, 1};
        copy.imageOffset = offset;
        copy.imageExtent = extent;
        vkCmdCopyImageToBuffer(cb, image.image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, staging, 1, &copy);
        vulkan_detail::buffer_barrier(cb, staging, 0, size,
                                     {VK_PIPELINE_STAGE_TRANSFER_BIT, VK_ACCESS_TRANSFER_WRITE_BIT},
                                     {VK_PIPELINE_STAGE_HOST_BIT, VK_ACCESS_HOST_READ_BIT});
        transition_image_layout(cb, image.image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, previous, aspect,
                                image.desc.array_layers);
    }

    bool VulkanRenderDevice::read_image_bytes(VkTextureResource& image, VkImageAspectFlags aspect,
                                              VkOffset3D offset, VkExtent3D extent, std::span<uint8_t> output) {
        if (!validate_image_readback(image, offset, extent))
            return false;
        VkBuffer staging = VK_NULL_HANDLE;
        VmaAllocation allocation = VK_NULL_HANDLE;
        if (!create_readback_buffer(output.size(), staging, allocation))
            return false;
        const auto cb = begin_readback_commands();
        if (!cb) {
            vmaDestroyBuffer(allocator_, staging, allocation);
            return false;
        }
        record_image_readback(cb, image, staging, aspect, offset, extent, output.size());
        return finish_readback(cb, staging, allocation, 0, output);
    }

    void VulkanRenderDevice::read_buffer(BufferHandle src, std::span<uint8_t> data, uint64_t offset) {
        auto* res = buffers_.get(src.id);
        if (!res || !res->allocation || offset > res->desc.size || data.size() > res->desc.size - offset) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] invalid buffer handle/allocation/range: handle=%u", src.id);
            return;
        }
        if (data.empty())
            return;
        if (!res->desc.cpu_visible && !has_flag(res->desc.usage, BufferUsage::CopySrc)) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] device-local buffer requires CopySrc: handle=%u", src.id);
            return;
        }
        VkBuffer staging = VK_NULL_HANDLE;
        VmaAllocation allocation = res->allocation;
        if (!res->desc.cpu_visible && !create_readback_buffer(data.size(), staging, allocation))
            return;
        const auto cb = begin_readback_commands();
        if (!cb) {
            if (staging) vmaDestroyBuffer(allocator_, staging, allocation);
            return;
        }
        if (staging) {
            vulkan_detail::buffer_before_transfer(cb, res->buffer, res->desc.usage, offset, data.size(),
                                                  VK_ACCESS_TRANSFER_READ_BIT);
            VkBufferCopy copy{offset, 0, data.size()};
            vkCmdCopyBuffer(cb, res->buffer, staging, 1, &copy);
            vulkan_detail::buffer_barrier(cb, staging, 0, data.size(),
                                         {VK_PIPELINE_STAGE_TRANSFER_BIT, VK_ACCESS_TRANSFER_WRITE_BIT},
                                         {VK_PIPELINE_STAGE_HOST_BIT, VK_ACCESS_HOST_READ_BIT});
        } else {
            vulkan_detail::buffer_barrier(cb, res->buffer, offset, data.size(),
                                         vulkan_detail::buffer_access_scope(res->desc.usage),
                                         {VK_PIPELINE_STAGE_HOST_BIT, VK_ACCESS_HOST_READ_BIT});
        }
        finish_readback(cb, staging, allocation, staging ? 0 : offset, data);
    }

} // namespace tgfx
#endif
