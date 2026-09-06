#pragma once

#include "tgfx2/descriptors.hpp"
#include <vulkan/vulkan.h>

namespace tgfx::vulkan_detail {

    inline constexpr VkPipelineStageFlags image_shader_stages() {
        // Covers every shader stage supported by the queue, without requesting
        // optional tessellation/geometry/compute stage bits on unsupported queues.
        return VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;
    }

    inline bool image_needs_view(TextureUsage usage) {
        return has_flag(usage, TextureUsage::Sampled | TextureUsage::Storage |
                               TextureUsage::ColorAttachment | TextureUsage::DepthStencilAttachment);
    }

    inline VkImageLayout image_after_transfer_layout(const TextureDesc& desc, VkImageLayout previous) {
        // Sampled descriptors require this layout before entering a render pass.
        // For other usages preserve the previous state, or initialize a legal
        // state when this is the destination's first write.
        if (has_flag(desc.usage, TextureUsage::Sampled))
            return VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
        if (previous != VK_IMAGE_LAYOUT_UNDEFINED && previous != VK_IMAGE_LAYOUT_PREINITIALIZED)
            return previous;
        if (has_flag(desc.usage, TextureUsage::Storage))
            return VK_IMAGE_LAYOUT_GENERAL;
        if (has_flag(desc.usage, TextureUsage::ColorAttachment))
            return VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
        if (has_flag(desc.usage, TextureUsage::DepthStencilAttachment))
            return VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;
        return VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    }

    // A depth/stencil attachment may perform reads and writes in either fragment
    // test stage. Restricting a layout transition to only one of them leaves the
    // other stage outside the dependency scope and can expose stale depth data to
    // a following shader read on stricter drivers.
    inline constexpr VkPipelineStageFlags depth_stencil_attachment_stages() {
        return VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT | VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT;
    }

    inline constexpr VkAccessFlags color_attachment_accesses() {
        return VK_ACCESS_COLOR_ATTACHMENT_READ_BIT | VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    }

    inline constexpr VkAccessFlags depth_stencil_attachment_accesses() {
        return VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;
    }

} // namespace tgfx::vulkan_detail
