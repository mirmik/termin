#ifdef TGFX2_HAS_VULKAN

#include "tgfx2/pixel_format_utils.hpp"
#include "tgfx2/vulkan/internal/buffer_transfer_sync.hpp"
#include "tgfx2/vulkan/internal/readback_memory.hpp"
#include "tgfx2/vulkan/internal/image_transition_sync.hpp"
#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/vulkan/vulkan_type_conversions.hpp"

#include <vk_mem_alloc.h>

#include <algorithm>
#include <cstring>
#include <functional>
#include <limits>
#include <stdexcept>
#include <span>
#include <vector>

extern "C" {
#include <tcbase/tc_log.h>
}

namespace tgfx {

    namespace {

        static VkImageLayout texture_post_upload_layout(const TextureDesc& desc) {
            return has_flag(desc.usage, TextureUsage::Sampled) ? VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL
                                                               : VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        }

        static float half_to_float(uint16_t h) {
            const uint32_t sign = static_cast<uint32_t>(h & 0x8000u) << 16u;
            uint32_t exp = (h >> 10u) & 0x1fu;
            uint32_t mant = h & 0x03ffu;

            uint32_t bits = 0;
            if (exp == 0) {
                if (mant == 0) {
                    bits = sign;
                } else {
                    exp = 1;
                    while ((mant & 0x0400u) == 0) {
                        mant <<= 1u;
                        --exp;
                    }
                    mant &= 0x03ffu;
                    bits = sign | ((exp + 112u) << 23u) | (mant << 13u);
                }
            } else if (exp == 31) {
                bits = sign | 0x7f800000u | (mant << 13u);
            } else {
                bits = sign | ((exp + 112u) << 23u) | (mant << 13u);
            }

            float out = 0.0f;
            std::memcpy(&out, &bits, sizeof(out));
            return out;
        }

    } // namespace

    // --- Immediate command execution ---

    VkCommandBuffer VulkanRenderDevice::ensure_immediate_cb() {
        if (immediate_cb_open_)
            return immediate_cb_;

        // Always allocate a fresh cb. The previous frame's immediate_cb was
        // handed over to pending_destroy_current_ in submit(), so it will
        // be freed after the frame fence signals — safe. Re-recording the
        // same cb here would hit "buffer is in use" validation because
        // submit()'s fence wait hasn't necessarily run yet between calls.
        VkCommandBufferAllocateInfo ai{};
        ai.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
        ai.commandPool = command_pool_;
        ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        ai.commandBufferCount = 1;
        const auto allocate_result = vkAllocateCommandBuffers(device_, &ai, &immediate_cb_);
        if (allocate_result != VK_SUCCESS) {
            tc_log(TC_LOG_ERROR, "[Vulkan] immediate command allocation failed: VkResult=%d", int(allocate_result));
            throw std::runtime_error("Vulkan immediate command allocation failed");
        }

        VkCommandBufferBeginInfo bi{};
        bi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        const auto begin_result = vkBeginCommandBuffer(immediate_cb_, &bi);
        if (begin_result != VK_SUCCESS) {
            tc_log(TC_LOG_ERROR, "[Vulkan] immediate command begin failed: VkResult=%d", int(begin_result));
            vkFreeCommandBuffers(device_, command_pool_, 1, &immediate_cb_);
            immediate_cb_ = VK_NULL_HANDLE;
            throw std::runtime_error("Vulkan immediate command begin failed");
        }

        immediate_cb_open_ = true;
        return immediate_cb_;
    }

    void VulkanRenderDevice::execute_immediate(std::function<void(VkCommandBuffer)> fn) {
        // Record into the shared immediate cb. No submit, no wait — the cb
        // gets submitted together with the main draw cb in `submit()`, as
        // entry 0 of a multi-cb `vkQueueSubmit`. Transfer commands must record
        // their own memory dependencies; CB order alone does not provide them.
        // This is a submission prelude, not an insertion into a recording draw CB.
        //
        // Callers that used to do `staging; execute_immediate; destroy
        // staging;` must now push staging into `defer_vma_buffer_destroy` —
        // the GPU hasn't run the copy by the time this function returns.
        fn(ensure_immediate_cb());
    }

    // --- Image layout transition ---

    void VulkanRenderDevice::transition_image_layout(VkCommandBuffer cmd,
                                                     VkImage image,
                                                     VkImageLayout old_layout,
                                                     VkImageLayout new_layout,
                                                     VkImageAspectFlags aspect,
                                                     uint32_t array_layers) {
        VkImageMemoryBarrier barrier{};
        barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        barrier.oldLayout = old_layout;
        barrier.newLayout = new_layout;
        barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.image = image;
        barrier.subresourceRange.aspectMask = aspect;
        barrier.subresourceRange.baseMipLevel = 0;
        barrier.subresourceRange.levelCount = VK_REMAINING_MIP_LEVELS;
        barrier.subresourceRange.baseArrayLayer = 0;
        barrier.subresourceRange.layerCount = array_layers;

        VkPipelineStageFlags src_stage = VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;
        VkPipelineStageFlags dst_stage = VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;

        if (old_layout == VK_IMAGE_LAYOUT_UNDEFINED) {
            barrier.srcAccessMask = 0;
        } else if (old_layout == VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL) {
            barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
            src_stage = VK_PIPELINE_STAGE_TRANSFER_BIT;
        } else if (old_layout == VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL) {
            barrier.srcAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
            src_stage = VK_PIPELINE_STAGE_TRANSFER_BIT;
        } else if (old_layout == VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL) {
            barrier.srcAccessMask = vulkan_detail::color_attachment_accesses();
            src_stage = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        } else if (old_layout == VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL) {
            barrier.srcAccessMask = vulkan_detail::depth_stencil_attachment_accesses();
            src_stage = vulkan_detail::depth_stencil_attachment_stages();
        } else if (old_layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL) {
            barrier.srcAccessMask = VK_ACCESS_SHADER_READ_BIT;
            src_stage = vulkan_detail::image_shader_stages();
        } else if (old_layout == VK_IMAGE_LAYOUT_GENERAL) {
            barrier.srcAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;
        }

        if (new_layout == VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL) {
            barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
            dst_stage = VK_PIPELINE_STAGE_TRANSFER_BIT;
        } else if (new_layout == VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL) {
            barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
            dst_stage = VK_PIPELINE_STAGE_TRANSFER_BIT;
        } else if (new_layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL) {
            barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
            dst_stage = vulkan_detail::image_shader_stages();
        } else if (new_layout == VK_IMAGE_LAYOUT_GENERAL) {
            barrier.dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;
        } else if (new_layout == VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL) {
            barrier.dstAccessMask = vulkan_detail::color_attachment_accesses();
            dst_stage = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        } else if (new_layout == VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL) {
            barrier.dstAccessMask = vulkan_detail::depth_stencil_attachment_accesses();
            dst_stage = vulkan_detail::depth_stencil_attachment_stages();
        }

        vkCmdPipelineBarrier(cmd, src_stage, dst_stage, 0, 0, nullptr, 0, nullptr, 1, &barrier);
    }

    // --- Upload ---

    void VulkanRenderDevice::upload_buffer(BufferHandle dst, std::span<const uint8_t> data, uint64_t offset) {
        auto* res = buffers_.get(dst.id);
        if (!res) {
            tc_log(TC_LOG_ERROR, "VulkanRenderDevice::upload_buffer: invalid buffer handle %u", dst.id);
            return;
        }
        if (offset > res->desc.size || data.size() > res->desc.size - offset) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::upload_buffer: write out of bounds for buffer %u "
                   "(offset=%llu size=%zu capacity=%llu)",
                   dst.id,
                   (unsigned long long)offset,
                   data.size(),
                   (unsigned long long)res->desc.size);
            return;
        }
        if (data.empty()) {
            return;
        }

        if (res->mapped_ptr) {
            // Persistently-mapped host-visible buffer. The common path for
            // every per-frame UBO (PerFrame / ShadowBlock / BoneBlock /
            // material params). One memcpy — no map/unmap, no submit, no
            // stall. Non-coherent writes are merged per allocation and all
            // allocations are flushed together immediately before submit.
            std::memcpy(static_cast<uint8_t*>(res->mapped_ptr) + offset, data.data(), data.size());
            if (!res->host_coherent) {
                if (!res->host_dirty_range.include(offset, data.size(), res->desc.size)) {
                    tc_log(TC_LOG_ERROR,
                           "VulkanRenderDevice::upload_buffer: invalid mapped dirty "
                           "range for buffer %u",
                           dst.id);
                    return;
                }
                if (!res->host_write_pending) {
                    res->host_write_pending = true;
                    pending_mapped_buffer_writes_.push_back(dst);
                }
            }
        } else if (res->desc.cpu_visible) {
            // Fallback: host-visible but not persistently mapped (e.g. buffer
            // registered externally). Keep the old explicit map path.
            void* mapped;
            vmaMapMemory(allocator_, res->allocation, &mapped);
            std::memcpy(static_cast<uint8_t*>(mapped) + offset, data.data(), data.size());
            vmaUnmapMemory(allocator_, res->allocation);
        } else {
            // Staging buffer
            VkBufferCreateInfo stage_ci{};
            stage_ci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
            stage_ci.size = data.size();
            stage_ci.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT;

            VmaAllocationCreateInfo stage_alloc{};
            stage_alloc.usage = VMA_MEMORY_USAGE_CPU_ONLY;

            VkBuffer staging;
            VmaAllocation staging_alloc;
            vmaCreateBuffer(allocator_, &stage_ci, &stage_alloc, &staging, &staging_alloc, nullptr);

            void* mapped;
            vmaMapMemory(allocator_, staging_alloc, &mapped);
            std::memcpy(mapped, data.data(), data.size());
            vmaUnmapMemory(allocator_, staging_alloc);

            execute_immediate([&](VkCommandBuffer cmd) {
                vulkan_detail::buffer_before_transfer(cmd, res->buffer, res->desc.usage, offset, data.size(),
                                                      VK_ACCESS_TRANSFER_WRITE_BIT);
                VkBufferCopy region{};
                region.srcOffset = 0;
                region.dstOffset = offset;
                region.size = data.size();
                vkCmdCopyBuffer(cmd, staging, res->buffer, 1, &region);
                vulkan_detail::buffer_after_transfer_write(cmd, res->buffer, res->desc.usage, offset, data.size());
            });

            // Defer staging destroy — GPU runs the copy after the frame submit.
            defer_vma_buffer_destroy(staging, staging_alloc);
        }
    }

    void VulkanRenderDevice::upload_texture(TextureHandle dst, std::span<const uint8_t> data, uint32_t mip) {
        auto* res = textures_.get(dst.id);
        if (!res) {
            tc_log(TC_LOG_ERROR, "VulkanRenderDevice::upload_texture: invalid texture handle %u", dst.id);
            return;
        }
        if (mip >= res->desc.mip_levels) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::upload_texture: mip %u out of range for texture %u (mips=%u)",
                   mip,
                   dst.id,
                   res->desc.mip_levels);
            return;
        }

        uint32_t w = std::max(1u, res->desc.width >> mip);
        uint32_t h = std::max(1u, res->desc.height >> mip);
        const uint32_t bytes_per_pixel = pixel_format_byte_size(res->desc.format);
        if (bytes_per_pixel == 0) {
            tc_log(
                TC_LOG_ERROR, "VulkanRenderDevice::upload_texture: unsupported texture format for texture %u", dst.id);
            return;
        }
        const size_t expected_size = static_cast<size_t>(w) * h * bytes_per_pixel;
        if (data.size() != expected_size) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::upload_texture: data size mismatch for texture %u mip %u (%zu bytes, expected "
                   "%zu)",
                   dst.id,
                   mip,
                   data.size(),
                   expected_size);
            return;
        }

        // Staging buffer
        VkBufferCreateInfo stage_ci{};
        stage_ci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
        stage_ci.size = data.size();
        stage_ci.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT;

        VmaAllocationCreateInfo stage_alloc_ci{};
        stage_alloc_ci.usage = VMA_MEMORY_USAGE_CPU_ONLY;

        VkBuffer staging;
        VmaAllocation staging_alloc;
        vmaCreateBuffer(allocator_, &stage_ci, &stage_alloc_ci, &staging, &staging_alloc, nullptr);

        void* mapped;
        vmaMapMemory(allocator_, staging_alloc, &mapped);
        std::memcpy(mapped, data.data(), data.size());
        vmaUnmapMemory(allocator_, staging_alloc);

        execute_immediate([&](VkCommandBuffer cmd) {
            transition_image_layout(cmd,
                                    res->image,
                                    res->current_layout,
                                    VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                                    vk::format_aspect_flags(res->desc.format));

            VkBufferImageCopy region{};
            region.imageSubresource.aspectMask = vk::format_aspect_flags(res->desc.format);
            region.imageSubresource.mipLevel = mip;
            region.imageSubresource.layerCount = 1;
            region.imageExtent = {w, h, 1};

            vkCmdCopyBufferToImage(cmd, staging, res->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);

            VkImageLayout final_layout = texture_post_upload_layout(res->desc);
            if (final_layout != VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL) {
                transition_image_layout(cmd,
                                        res->image,
                                        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                                        final_layout,
                                        vk::format_aspect_flags(res->desc.format));
            }
        });

        res->current_layout = texture_post_upload_layout(res->desc);
        defer_vma_buffer_destroy(staging, staging_alloc);
    }

    void VulkanRenderDevice::upload_texture_region(TextureHandle dst,
                                                   uint32_t x,
                                                   uint32_t y,
                                                   uint32_t w,
                                                   uint32_t h,
                                                   std::span<const uint8_t> data,
                                                   uint32_t mip) {
        auto* res = textures_.get(dst.id);
        if (!res) {
            tc_log(TC_LOG_ERROR, "VulkanRenderDevice::upload_texture_region: invalid texture handle %u", dst.id);
            return;
        }
        if (w == 0 || h == 0) {
            return;
        }
        if (mip >= res->desc.mip_levels) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::upload_texture_region: mip %u out of range for texture %u (mips=%u)",
                   mip,
                   dst.id,
                   res->desc.mip_levels);
            return;
        }

        const uint32_t mip_w = std::max(1u, res->desc.width >> mip);
        const uint32_t mip_h = std::max(1u, res->desc.height >> mip);
        if (x >= mip_w || y >= mip_h || w > mip_w - x || h > mip_h - y) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::upload_texture_region: region (%u,%u %ux%u) outside texture %u mip %u (%ux%u)",
                   x,
                   y,
                   w,
                   h,
                   dst.id,
                   mip,
                   mip_w,
                   mip_h);
            return;
        }

        const uint32_t bytes_per_pixel = pixel_format_byte_size(res->desc.format);
        if (bytes_per_pixel == 0) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::upload_texture_region: unsupported texture format for texture %u",
                   dst.id);
            return;
        }

        const size_t expected_size = static_cast<size_t>(w) * h * bytes_per_pixel;
        if (data.size() != expected_size) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::upload_texture_region: data size mismatch for texture %u region (%zu bytes, "
                   "expected %zu)",
                   dst.id,
                   data.size(),
                   expected_size);
            return;
        }

        VkBufferCreateInfo stage_ci{};
        stage_ci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
        stage_ci.size = expected_size;
        stage_ci.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT;

        VmaAllocationCreateInfo stage_alloc_ci{};
        stage_alloc_ci.usage = VMA_MEMORY_USAGE_CPU_ONLY;

        VkBuffer staging = VK_NULL_HANDLE;
        VmaAllocation staging_alloc = VK_NULL_HANDLE;
        if (vmaCreateBuffer(allocator_, &stage_ci, &stage_alloc_ci, &staging, &staging_alloc, nullptr) != VK_SUCCESS) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::upload_texture_region: failed to allocate staging buffer for texture %u",
                   dst.id);
            return;
        }

        void* mapped = nullptr;
        if (vmaMapMemory(allocator_, staging_alloc, &mapped) != VK_SUCCESS || !mapped) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::upload_texture_region: failed to map staging buffer for texture %u",
                   dst.id);
            vmaDestroyBuffer(allocator_, staging, staging_alloc);
            return;
        }
        std::memcpy(mapped, data.data(), expected_size);
        vmaUnmapMemory(allocator_, staging_alloc);

        const VkImageAspectFlags aspect = vk::format_aspect_flags(res->desc.format);
        execute_immediate([&](VkCommandBuffer cmd) {
            transition_image_layout(cmd, res->image, res->current_layout, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, aspect);

            VkBufferImageCopy region{};
            region.bufferOffset = 0;
            region.bufferRowLength = 0;
            region.bufferImageHeight = 0;
            region.imageSubresource.aspectMask = aspect;
            region.imageSubresource.mipLevel = mip;
            region.imageSubresource.baseArrayLayer = 0;
            region.imageSubresource.layerCount = 1;
            region.imageOffset = {
                static_cast<int32_t>(x),
                static_cast<int32_t>(y),
                0,
            };
            region.imageExtent = {w, h, 1};

            vkCmdCopyBufferToImage(cmd, staging, res->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);

            VkImageLayout final_layout = texture_post_upload_layout(res->desc);
            if (final_layout != VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL) {
                transition_image_layout(cmd, res->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, final_layout, aspect);
            }
        });

        res->current_layout = texture_post_upload_layout(res->desc);
        defer_vma_buffer_destroy(staging, staging_alloc);
    }

    // --- Readback ---

    bool VulkanRenderDevice::read_pixel_rgba8(TextureHandle tex, int x, int y, float out_rgba[4]) {
        auto* res = textures_.get(tex.id);
        if (!res || !out_rgba ||
            (res->desc.format != PixelFormat::RGBA8_UNorm && res->desc.format != PixelFormat::RGBA8_sRGB)) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] RGBA8 pixel requires RGBA8 texture and valid output");
            return false;
        }
        std::array<uint8_t, 4> pixel{};
        if (!read_image_bytes(*res, VK_IMAGE_ASPECT_COLOR_BIT, {x, y, 0}, {1, 1, 1}, pixel))
            return false;
        for (size_t i = 0; i < pixel.size(); ++i)
            out_rgba[i] = pixel[i] / 255.0f;
        return true;
    }

    bool VulkanRenderDevice::read_pixel_depth_float(TextureHandle tex, int x, int y, float* out_depth) {
        auto* res = textures_.get(tex.id);
        if (!res || !out_depth || res->desc.format != PixelFormat::D32F) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] depth pixel requires D32F texture and valid output");
            return false;
        }
        return read_image_bytes(*res, VK_IMAGE_ASPECT_DEPTH_BIT, {x, y, 0}, {1, 1, 1},
                                {reinterpret_cast<uint8_t*>(out_depth), sizeof(float)});
    }

    bool VulkanRenderDevice::read_texture_rgba_float(TextureHandle tex, float* out) {
        auto* res = textures_.get(tex.id);
        if (!res || !out) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] invalid color texture handle/output");
            return false;
        }
        if (is_depth_format(res->desc.format)) {
            tc_log(TC_LOG_ERROR, "VulkanRenderDevice::read_texture_rgba_float: texture %u is a depth format", tex.id);
            return false;
        }
        if (!has_flag(res->desc.usage, TextureUsage::CopySrc)) {
            tc_log(
                TC_LOG_ERROR, "VulkanRenderDevice::read_texture_rgba_float: texture %u missing CopySrc usage", tex.id);
            return false;
        }

        const uint32_t bytes_per_pixel = pixel_format_byte_size(res->desc.format);
        if (bytes_per_pixel == 0) {
            tc_log(TC_LOG_ERROR,
                   "VulkanRenderDevice::read_texture_rgba_float: unsupported texture format for texture %u",
                   tex.id);
            return false;
        }

        const uint32_t width = res->desc.width;
        const uint32_t height = res->desc.height;
        const uint64_t pixel_count = uint64_t(width) * height;
        if (pixel_count > std::numeric_limits<size_t>::max() / std::max<size_t>(bytes_per_pixel, 4 * sizeof(float))) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] color texture byte size overflow");
            return false;
        }
        const size_t byte_size = static_cast<size_t>(pixel_count) * bytes_per_pixel;

        std::vector<uint8_t> bytes(byte_size);
        if (!read_image_bytes(*res, VK_IMAGE_ASPECT_COLOR_BIT, {0, 0, 0}, {width, height, 1}, bytes))
            return false;

        for (size_t i = 0; i < pixel_count; ++i) {
            const uint8_t* src = bytes.data() + static_cast<size_t>(i) * bytes_per_pixel;
            float* dst = out + static_cast<size_t>(i) * 4;
            switch (res->desc.format) {
            case PixelFormat::R8_UNorm:
                dst[0] = src[0] / 255.0f;
                dst[1] = 0.0f;
                dst[2] = 0.0f;
                dst[3] = 1.0f;
                break;
            case PixelFormat::RG8_UNorm:
                dst[0] = src[0] / 255.0f;
                dst[1] = src[1] / 255.0f;
                dst[2] = 0.0f;
                dst[3] = 1.0f;
                break;
            case PixelFormat::RGB8_UNorm:
                dst[0] = src[0] / 255.0f;
                dst[1] = src[1] / 255.0f;
                dst[2] = src[2] / 255.0f;
                dst[3] = 1.0f;
                break;
            case PixelFormat::RGBA8_UNorm:
            case PixelFormat::RGBA8_sRGB:
                dst[0] = src[0] / 255.0f;
                dst[1] = src[1] / 255.0f;
                dst[2] = src[2] / 255.0f;
                dst[3] = src[3] / 255.0f;
                break;
            case PixelFormat::BGRA8_UNorm:
            case PixelFormat::BGRA8_sRGB:
                dst[0] = src[2] / 255.0f;
                dst[1] = src[1] / 255.0f;
                dst[2] = src[0] / 255.0f;
                dst[3] = src[3] / 255.0f;
                break;
            case PixelFormat::R16F: {
                uint16_t r = 0;
                std::memcpy(&r, src, sizeof(r));
                dst[0] = half_to_float(r);
                dst[1] = 0.0f;
                dst[2] = 0.0f;
                dst[3] = 1.0f;
                break;
            }
            case PixelFormat::RG16F: {
                uint16_t rg[2] = {};
                std::memcpy(rg, src, sizeof(rg));
                dst[0] = half_to_float(rg[0]);
                dst[1] = half_to_float(rg[1]);
                dst[2] = 0.0f;
                dst[3] = 1.0f;
                break;
            }
            case PixelFormat::RGBA16F: {
                uint16_t rgba[4] = {};
                std::memcpy(rgba, src, sizeof(rgba));
                dst[0] = half_to_float(rgba[0]);
                dst[1] = half_to_float(rgba[1]);
                dst[2] = half_to_float(rgba[2]);
                dst[3] = half_to_float(rgba[3]);
                break;
            }
            case PixelFormat::R32F:
                std::memcpy(&dst[0], src, sizeof(float));
                dst[1] = 0.0f;
                dst[2] = 0.0f;
                dst[3] = 1.0f;
                break;
            case PixelFormat::RG32F:
                std::memcpy(&dst[0], src, sizeof(float) * 2);
                dst[2] = 0.0f;
                dst[3] = 1.0f;
                break;
            case PixelFormat::RGBA32F:
                std::memcpy(dst, src, sizeof(float) * 4);
                break;
            default:
                tc_log(TC_LOG_ERROR,
                       "VulkanRenderDevice::read_texture_rgba_float: unsupported texture format for texture %u",
                       tex.id);
                return false;
            }
        }
        return true;
    }

    bool VulkanRenderDevice::read_texture_depth_float(TextureHandle tex, float* out) {
        auto* res = textures_.get(tex.id);
        if (!res || !out) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] invalid depth texture handle/output");
            return false;
        }
        if (res->desc.format != PixelFormat::D32F) {
            tc_log(TC_LOG_ERROR, "VulkanRenderDevice::read_texture_depth_float: texture %u format is not D32F", tex.id);
            return false;
        }
        if (!has_flag(res->desc.usage, TextureUsage::CopySrc)) {
            tc_log(
                TC_LOG_ERROR, "VulkanRenderDevice::read_texture_depth_float: texture %u missing CopySrc usage", tex.id);
            return false;
        }

        const uint32_t width = res->desc.width;
        const uint32_t height = res->desc.height;
        const uint64_t pixel_count = uint64_t(width) * height;
        if (pixel_count > std::numeric_limits<size_t>::max() / sizeof(float)) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] depth texture byte size overflow");
            return false;
        }
        const size_t byte_size = static_cast<size_t>(pixel_count) * sizeof(float);

        return read_image_bytes(*res, VK_IMAGE_ASPECT_DEPTH_BIT, {0, 0, 0}, {width, height, 1},
                                {reinterpret_cast<uint8_t*>(out), byte_size});
    }

    uint64_t VulkanRenderDevice::request_pixel_rgba8(TextureHandle tex, int x, int y) {
        return request_pixel_readback(tex, x, y, PixelReadbackKind::Rgba8);
    }

    bool VulkanRenderDevice::poll_pixel_rgba8(uint64_t request_id, float out_rgba[4]) {
        if (request_id == 0 || !out_rgba)
            return false;
        auto it = completed_pixel_readbacks_.find(request_id);
        if (it == completed_pixel_readbacks_.end())
            return false;
        if (it->second.kind != PixelReadbackKind::Rgba8) {
            completed_pixel_readbacks_.erase(it);
            return false;
        }
        const auto bytes = it->second.bytes;
        completed_pixel_readbacks_.erase(it);
        out_rgba[0] = bytes[0] / 255.0f;
        out_rgba[1] = bytes[1] / 255.0f;
        out_rgba[2] = bytes[2] / 255.0f;
        out_rgba[3] = bytes[3] / 255.0f;
        return true;
    }

    uint64_t VulkanRenderDevice::request_pixel_depth_float(TextureHandle tex, int x, int y) {
        return request_pixel_readback(tex, x, y, PixelReadbackKind::DepthF32);
    }

    bool VulkanRenderDevice::poll_pixel_depth_float(uint64_t request_id, float* out_depth) {
        if (request_id == 0 || !out_depth)
            return false;
        auto it = completed_pixel_readbacks_.find(request_id);
        if (it == completed_pixel_readbacks_.end())
            return false;
        if (it->second.kind != PixelReadbackKind::DepthF32) {
            completed_pixel_readbacks_.erase(it);
            return false;
        }
        std::memcpy(out_depth, it->second.bytes.data(), sizeof(float));
        completed_pixel_readbacks_.erase(it);
        return true;
    }

    uint64_t VulkanRenderDevice::request_pixel_readback(TextureHandle tex, int x, int y, PixelReadbackKind kind) {
        auto* res = textures_.get(tex.id);
        const bool depth = kind == PixelReadbackKind::DepthF32;
        if (!res || (depth ? res->desc.format != PixelFormat::D32F :
                     (res->desc.format != PixelFormat::RGBA8_UNorm && res->desc.format != PixelFormat::RGBA8_sRGB))) {
            tc_log(TC_LOG_ERROR, "[Vulkan readback] async pixel format/handle mismatch");
            return 0;
        }
        if (!validate_image_readback(*res, {x, y, 0}, {1, 1, 1}))
            return 0;
        // Open before allocating staging: a command allocation failure must not
        // orphan the pixel allocation.
        const auto cb = ensure_immediate_cb();
        VkBuffer staging = VK_NULL_HANDLE;
        VmaAllocation allocation = VK_NULL_HANDLE;
        if (!create_readback_buffer(4, staging, allocation))
            return 0;
        record_image_readback(cb, *res, staging, depth ? VK_IMAGE_ASPECT_DEPTH_BIT : VK_IMAGE_ASPECT_COLOR_BIT,
                              {x, y, 0}, {1, 1, 1}, 4);
        const uint64_t request_id = next_pixel_readback_id_++;
        pixel_readbacks_current_.push_back(PendingPixelReadback{request_id, kind, staging, allocation});
        return request_id;
    }

    void VulkanRenderDevice::complete_pixel_readbacks(std::vector<PendingPixelReadback>& pending, VkResult completion) {
        for (const PendingPixelReadback& rb : pending) {
            CompletedPixelReadback completed{};
            completed.kind = rb.kind;
            if (vulkan_detail::copy_completed_readback(completion, allocator_, rb.allocation, 0, completed.bytes)) {
                completed_pixel_readbacks_[rb.request_id] = completed;
            } else {
                tc_log(TC_LOG_ERROR, "[Vulkan readback] async request failed: %llu",
                       static_cast<unsigned long long>(rb.request_id));
            }
            vmaDestroyBuffer(allocator_, rb.staging, rb.allocation);
        }
        pending.clear();
    }

    void VulkanRenderDevice::destroy_pixel_readbacks(std::vector<PendingPixelReadback>& pending) {
        for (const PendingPixelReadback& rb : pending) {
            vmaDestroyBuffer(allocator_, rb.staging, rb.allocation);
        }
        pending.clear();
    }

} // namespace tgfx

#endif // TGFX2_HAS_VULKAN
