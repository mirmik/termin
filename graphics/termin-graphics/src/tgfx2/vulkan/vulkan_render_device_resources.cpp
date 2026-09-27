#ifdef TGFX2_HAS_VULKAN

#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/vulkan/vulkan_type_conversions.hpp"

#include <vk_mem_alloc.h>

#include <tcbase/tc_log.hpp>

#include <algorithm>
#include <cmath>
#include <stdexcept>

extern "C" {
#include <tcbase/tc_log.h>
}

namespace tgfx {

    VkSampler VulkanRenderDevice::ensure_default_sampler() {
        if (default_sampler_)
            return default_sampler_;
        VkSamplerCreateInfo sci{};
        sci.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
        sci.magFilter = VK_FILTER_LINEAR;
        sci.minFilter = VK_FILTER_LINEAR;
        sci.mipmapMode = VK_SAMPLER_MIPMAP_MODE_LINEAR;
        sci.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
        sci.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
        sci.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
        sci.anisotropyEnable = VK_FALSE;
        sci.maxLod = VK_LOD_CLAMP_NONE;
        vkCreateSampler(device_, &sci, nullptr, &default_sampler_);
        return default_sampler_;
    }

    TextureHandle VulkanRenderDevice::ensure_default_sampled_texture() {
        if (default_sampled_texture_) {
            return default_sampled_texture_;
        }

        TextureDesc desc;
        desc.width = 1;
        desc.height = 1;
        desc.mip_levels = 1;
        desc.sample_count = 1;
        desc.format = PixelFormat::RGBA8_UNorm;
        desc.usage = TextureUsage::Sampled | TextureUsage::CopyDst;

        default_sampled_texture_ = create_texture(desc);
        const uint8_t white[] = {255, 255, 255, 255};
        upload_texture(default_sampled_texture_, std::span<const uint8_t>(white, sizeof(white)));
        return default_sampled_texture_;
    }

    // --- Capabilities ---

    BackendCapabilities VulkanRenderDevice::capabilities() const {
        return caps_;
    }
    void VulkanRenderDevice::wait_idle() {
        const auto result = device_ops_.device_wait_idle(device_);
        if (result != VK_SUCCESS) {
            device_failure_.fail("device idle wait", result);
        }
        // Only submitted requests are complete. Requests in the current
        // prelude still require a submit, even if the device is idle.
        for (auto& pending : pixel_readbacks_slots_)
            complete_pixel_readbacks(pending, result);
    }

    void VulkanRenderDevice::invalidate_descriptor_cache() {
        for (auto& cache : ring_descriptor_cache_) cache.clear();
        for (auto& cache : descriptor_cache_) {
            for (const auto& [_, handle] : cache) {
                resource_sets_.remove(handle.id);
            }
            cache.clear();
        }
    }

    void VulkanRenderDevice::invalidate_render_target_cache() {
        for (auto& [_, fb] : framebuffer_cache_) {
            if (fb != VK_NULL_HANDLE) {
                pending_destroy_current_.framebuffers.push_back(fb);
            }
        }
        framebuffer_cache_.clear();
        invalidate_descriptor_cache();
    }

    // --- Buffer ---

    BufferHandle VulkanRenderDevice::create_buffer(const BufferDesc& desc) {
        VkBufferResource res;
        res.desc = desc;

        VkBufferCreateInfo ci{};
        ci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
        ci.size = desc.size;
        ci.usage = vk::to_vk_buffer_usage(desc.usage);
        ci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

        // Uniform buffers are effectively always per-frame data (camera
        // matrices, material params, bones, ...) — uploaded every frame
        // and read once. Placing them in HOST_VISIBLE|DEVICE_LOCAL memory
        // (CPU_TO_GPU) lets upload_buffer go through a plain map+memcpy,
        // skipping the staging buffer + execute_immediate + vkQueueWaitIdle
        // path entirely. Without this, a frame with ~30 UBO uploads would
        // do ~30 full GPU stalls — the dominant Vulkan perf regression vs
        // OpenGL on shadow/color passes.
        //
        // The caller-set `cpu_visible` still forces HOST_VISIBLE for other
        // use cases (e.g. readback staging mirrors). Vertex/index buffers
        // and large static textures stay GPU_ONLY as intended.
        const bool want_host_visible =
            desc.cpu_visible || (static_cast<uint32_t>(desc.usage & BufferUsage::Uniform) != 0);
        res.desc.cpu_visible = want_host_visible;

        VmaAllocationCreateInfo alloc_ci{};
        alloc_ci.usage = want_host_visible ? VMA_MEMORY_USAGE_CPU_TO_GPU : VMA_MEMORY_USAGE_GPU_ONLY;
        // Persistently-mapped host-visible buffers: VMA keeps a pointer on
        // `VmaAllocationInfo::pMappedData`, so upload_buffer skips
        // vmaMapMemory/vmaUnmapMemory and does a plain memcpy.
        if (want_host_visible) {
            alloc_ci.flags |= VMA_ALLOCATION_CREATE_MAPPED_BIT;
            // Vulkan guarantees a HOST_VISIBLE|HOST_COHERENT memory type. Small,
            // frequently-updated UBOs benefit much more from direct visibility
            // than from a cached non-coherent type whose flush may enter a costly
            // driver cache-maintenance ioctl on older mobile GPUs.
            alloc_ci.requiredFlags = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
        }

        VmaAllocationInfo alloc_info{};
        if (vmaCreateBuffer(allocator_, &ci, &alloc_ci, &res.buffer, &res.allocation, &alloc_info) != VK_SUCCESS) {
            throw std::runtime_error("Failed to create Vulkan buffer");
        }
        res.mapped_ptr = alloc_info.pMappedData; // NULL for GPU-only buffers
        if (res.mapped_ptr) {
            res.host_coherent = (memory_properties_.memoryTypes[alloc_info.memoryType].propertyFlags &
                                 VK_MEMORY_PROPERTY_HOST_COHERENT_BIT) != 0;
        }

        return {buffers_.add(std::move(res))};
    }

    // --- Texture ---

    bool VulkanRenderDevice::supports_texture(const TextureDesc& desc) const {
        if (has_flag(desc.usage, TextureUsage::Storage) && !caps_.supports_storage_textures)
            return false;
        const VkFormat format = vk::to_vk_format(desc.format);
        const VkImageUsageFlags usage = vk::to_vk_image_usage(desc.usage);
        if (format == VK_FORMAT_UNDEFINED || usage == 0 || desc.width == 0 || desc.height == 0 ||
            desc.array_layers == 0 || desc.mip_levels == 0 || desc.sample_count == 0 ||
            desc.sample_count > 64 || (desc.sample_count & (desc.sample_count - 1)) != 0 ||
            (desc.sample_count > 1 && desc.mip_levels != 1)) {
            return false;
        }
        uint32_t max_mip_levels = 1;
        for (uint32_t extent = std::max(desc.width, desc.height); extent > 1; extent >>= 1)
            ++max_mip_levels;
        if (desc.mip_levels > max_mip_levels)
            return false;

        VkImageFormatProperties properties{};
        const VkResult result = vkGetPhysicalDeviceImageFormatProperties(physical_device_, format,
            VK_IMAGE_TYPE_2D, VK_IMAGE_TILING_OPTIMAL, usage, 0, &properties);
        if (result == VK_ERROR_FORMAT_NOT_SUPPORTED)
            return false;
        if (result != VK_SUCCESS) {
            tc::Log::error("VulkanRenderDevice::supports_texture: format query failed (VkResult=%d)",
                           static_cast<int>(result));
            throw std::runtime_error("Vulkan image format support query failed");
        }
        return (properties.sampleCounts & desc.sample_count) != 0 &&
               desc.width <= properties.maxExtent.width && desc.height <= properties.maxExtent.height &&
               desc.array_layers <= properties.maxArrayLayers && desc.mip_levels <= properties.maxMipLevels;
    }

    TextureHandle VulkanRenderDevice::create_texture(const TextureDesc& desc) {
        if (!supports_texture(desc)) {
            tc::Log::error("VulkanRenderDevice::create_texture: unsupported descriptor "
                           "(format=%u, usage=0x%x, extent=%ux%u, layers=%u, mips=%u, samples=%u)",
                           static_cast<unsigned>(desc.format), static_cast<unsigned>(desc.usage),
                           desc.width, desc.height, desc.array_layers, desc.mip_levels, desc.sample_count);
            throw std::runtime_error("VulkanRenderDevice::create_texture: unsupported texture descriptor");
        }
        VkTextureResource res;
        res.desc = desc;

        VkImageCreateInfo ci{};
        ci.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
        ci.imageType = VK_IMAGE_TYPE_2D;
        ci.format = vk::to_vk_format(desc.format);
        ci.extent = {desc.width, desc.height, 1};
        ci.mipLevels = desc.mip_levels;
        ci.arrayLayers = desc.array_layers;
        ci.samples = static_cast<VkSampleCountFlagBits>(desc.sample_count);
        ci.tiling = VK_IMAGE_TILING_OPTIMAL;
        ci.usage = vk::to_vk_image_usage(desc.usage);
        ci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
        ci.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;

        VmaAllocationCreateInfo alloc_ci{};
        alloc_ci.usage = VMA_MEMORY_USAGE_GPU_ONLY;

        if (vmaCreateImage(allocator_, &ci, &alloc_ci, &res.image, &res.allocation, nullptr) != VK_SUCCESS) {
            tc::Log::error("VulkanRenderDevice::create_texture: image allocation failed");
            throw std::runtime_error("Failed to create Vulkan image");
        }

        try {
            create_texture_views(res);
        } catch (...) {
            vmaDestroyImage(allocator_, res.image, res.allocation);
            throw;
        }

        res.current_layout = VK_IMAGE_LAYOUT_UNDEFINED;

        // If the caller flagged this as a sampled texture, pre-transition to
        // SHADER_READ_ONLY_OPTIMAL so a bind that happens before any
        // upload / blit / render-pass write doesn't see UNDEFINED at submit
        // time. Contents are undefined until something writes in — that's
        // the caller's concern — but the layout matches the descriptor the
        // pipeline expects. begin_render_pass will transition out to
        // COLOR/DEPTH attachment if the texture is used as an attachment
        // first. Cheap (one immediate barrier, no allocation).
        bool is_sampled = (static_cast<uint32_t>(desc.usage) & static_cast<uint32_t>(TextureUsage::Sampled)) != 0;
        if (is_sampled) {
            VkImage image = res.image;
            VkImageAspectFlags aspect = vk::format_image_aspect_flags(desc.format);
            execute_immediate([&](VkCommandBuffer cb) {
                transition_image_layout(cb,
                                        image,
                                        VK_IMAGE_LAYOUT_UNDEFINED,
                                        VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
                                        aspect,
                                        desc.array_layers);
            });
            res.current_layout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
        }

        return {textures_.add(std::move(res))};
    }

    TextureHandle VulkanRenderDevice::register_external_texture(uintptr_t native_handle, const TextureDesc& desc) {
        VkImage image = reinterpret_cast<VkImage>(native_handle);
        if (image == VK_NULL_HANDLE) {
            throw std::runtime_error("VulkanRenderDevice::register_external_texture: null VkImage");
        }
        if (desc.array_layers == 0) {
            throw std::runtime_error("VulkanRenderDevice::register_external_texture: array_layers must be positive");
        }

        VkTextureResource res;
        res.image = image;
        res.desc = desc;
        res.external = true;
        res.current_layout = VK_IMAGE_LAYOUT_UNDEFINED;

        create_texture_views(res);
        return {textures_.add(std::move(res))};
    }

    void VulkanRenderDevice::create_texture_views(VkTextureResource& res) {
        const auto& desc = res.desc;
        VkImageViewCreateInfo view_ci{};
        view_ci.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
        view_ci.image = res.image;
        view_ci.viewType = desc.array_layers > 1 ? VK_IMAGE_VIEW_TYPE_2D_ARRAY : VK_IMAGE_VIEW_TYPE_2D;
        view_ci.format = vk::to_vk_format(desc.format);
        view_ci.subresourceRange.aspectMask = vk::format_image_aspect_flags(desc.format);
        view_ci.subresourceRange.baseMipLevel = 0;
        view_ci.subresourceRange.levelCount = desc.mip_levels;
        view_ci.subresourceRange.baseArrayLayer = 0;
        view_ci.subresourceRange.layerCount = desc.array_layers;

        const auto create = [&](VkImageView& view) {
            if (vkCreateImageView(device_, &view_ci, nullptr, &view) != VK_SUCCESS) {
                if (res.view) vkDestroyImageView(device_, res.view, nullptr);
                res.view = VK_NULL_HANDLE;
                tc::Log::error("VulkanRenderDevice::create_texture_views: vkCreateImageView failed");
                throw std::runtime_error("Failed to create Vulkan texture view");
            }
        };
        if (has_flag(desc.usage, TextureUsage::Sampled) || has_flag(desc.usage, TextureUsage::Storage)) {
            // A sampled depth/stencil image exposes depth, not both aspects.
            if (view_ci.subresourceRange.aspectMask & VK_IMAGE_ASPECT_DEPTH_BIT)
                view_ci.subresourceRange.aspectMask = VK_IMAGE_ASPECT_DEPTH_BIT;
            create(res.view);
        }
        if (has_flag(desc.usage, TextureUsage::ColorAttachment) ||
            has_flag(desc.usage, TextureUsage::DepthStencilAttachment)) {
            view_ci.subresourceRange.aspectMask = vk::format_image_aspect_flags(desc.format);
            view_ci.subresourceRange.levelCount = 1;
            create(res.attachment_view);
        }
    }

    namespace {

        VkImageLayout external_texture_layout(ExternalTextureState state) {
            switch (state) {
            case ExternalTextureState::Undefined:
                return VK_IMAGE_LAYOUT_UNDEFINED;
            case ExternalTextureState::ColorAttachment:
                return VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
            case ExternalTextureState::ShaderRead:
                return VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
            }
            return VK_IMAGE_LAYOUT_UNDEFINED;
        }

    } // namespace

    bool VulkanRenderDevice::begin_external_texture_access(TextureHandle handle,
                                                           const ExternalTextureAccessDesc& access) {
        VkTextureResource* texture = textures_.get(handle.id);
        if (!texture || !texture->external) {
            tc::Log::error("VulkanRenderDevice::begin_external_texture_access: handle is not external");
            return false;
        }
        texture->current_layout = external_texture_layout(access.state_after_wait);
        texture->required_before_release = access.required_before_release;
        return true;
    }

    bool VulkanRenderDevice::end_external_texture_access(TextureHandle handle) {
        VkTextureResource* texture = textures_.get(handle.id);
        if (!texture || !texture->external) {
            tc::Log::error("VulkanRenderDevice::end_external_texture_access: handle is not external");
            return false;
        }
        const VkImageLayout required = external_texture_layout(texture->required_before_release);
        if (texture->current_layout != required) {
            tc::Log::error("VulkanRenderDevice::end_external_texture_access: layout %d, required %d",
                           static_cast<int>(texture->current_layout),
                           static_cast<int>(required));
            return false;
        }
        return true;
    }

    // --- Sampler ---

    SamplerHandle VulkanRenderDevice::create_sampler(const SamplerDesc& desc) {
        VkPhysicalDeviceProperties properties{};
        vkGetPhysicalDeviceProperties(physical_device_, &properties);
        if (!std::isfinite(desc.max_anisotropy) || desc.max_anisotropy < 1.0f ||
            (desc.max_anisotropy > 1.0f &&
             (!enabled_features_.samplerAnisotropy ||
              desc.max_anisotropy > properties.limits.maxSamplerAnisotropy))) {
            tc_log_error("VulkanRenderDevice: unsupported sampler anisotropy=%g (enabled=%d max=%g)",
                         desc.max_anisotropy, enabled_features_.samplerAnisotropy,
                         properties.limits.maxSamplerAnisotropy);
            throw std::runtime_error("Unsupported Vulkan sampler anisotropy");
        }
        VkSamplerResource res;

        VkSamplerCreateInfo ci{};
        ci.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
        ci.magFilter = vk::to_vk_filter(desc.mag_filter);
        ci.minFilter = vk::to_vk_filter(desc.min_filter);
        ci.mipmapMode = vk::to_vk_mipmap_mode(desc.mip_filter);
        ci.addressModeU = vk::to_vk_address_mode(desc.address_u);
        ci.addressModeV = vk::to_vk_address_mode(desc.address_v);
        ci.addressModeW = vk::to_vk_address_mode(desc.address_w);
        ci.maxAnisotropy = desc.max_anisotropy;
        ci.anisotropyEnable = desc.max_anisotropy > 1.0f ? VK_TRUE : VK_FALSE;
        ci.compareEnable = desc.compare_enable ? VK_TRUE : VK_FALSE;
        ci.compareOp = vk::to_vk_compare(desc.compare_op);
        ci.maxLod = VK_LOD_CLAMP_NONE;

        if (vkCreateSampler(device_, &ci, nullptr, &res.sampler) != VK_SUCCESS) {
            throw std::runtime_error("Failed to create sampler");
        }

        return {samplers_.add(std::move(res))};
    }

    // --- Destroy ---

    TextureDesc VulkanRenderDevice::texture_desc(TextureHandle handle) const {
        auto* self = const_cast<VulkanRenderDevice*>(this);
        if (auto* r = self->textures_.get(handle.id)) {
            return r->desc;
        }
        return {};
    }

    uintptr_t VulkanRenderDevice::pipeline_resource_layout_token(PipelineHandle pipeline) const {
        auto* self = const_cast<VulkanRenderDevice*>(this);
        if (auto* p = self->pipelines_.get(pipeline.id)) {
            return reinterpret_cast<uintptr_t>(p->descriptor_set_layout);
        }
        tc_log(TC_LOG_ERROR, "VulkanRenderDevice: pipeline_resource_layout_token pipeline=%u NOT FOUND", pipeline.id);
        return 0;
    }

    uintptr_t VulkanRenderDevice::pipeline_descriptor_set_layout(PipelineHandle pipeline) const {
        return pipeline_resource_layout_token(pipeline);
    }

    // All `destroy(*Handle)` calls queue the handle into
    // `pending_destroy_current_`; actual Vk releases happen after the
    // current frame's fence signals (see `submit()`). Caller's handle is
    // invalid to use after this returns — the pool entry stays reserved
    // until drain time.

    void VulkanRenderDevice::destroy(BufferHandle h) {
        if (h.id == 0)
            return;
        // The ring UBO handle aliases a device-owned buffer; its real lifetime
        // is tied to the device, and destroying it mid-frame would wipe the
        // UBO store for every pending dynamic-offset binding.
        if (ring_ubo_handle_.id != 0 && h.id == ring_ubo_handle_.id)
            return;
        if (transient_vb_handle_.id != 0 && h.id == transient_vb_handle_.id)
            return;
        invalidate_descriptor_cache();
        pending_destroy_current_.buffers.push_back(h);
    }

    void VulkanRenderDevice::destroy(TextureHandle h) {
        if (h.id != 0) {
            invalidate_descriptor_cache();
            pending_destroy_current_.textures.push_back(h);
        }
    }

    void VulkanRenderDevice::destroy(SamplerHandle h) {
        if (h.id != 0) {
            invalidate_descriptor_cache();
            pending_destroy_current_.samplers.push_back(h);
        }
    }

    void VulkanRenderDevice::destroy(ShaderHandle h) {
        if (h.id != 0)
            pending_destroy_current_.shaders.push_back(h);
    }

    void VulkanRenderDevice::destroy(PipelineHandle h) {
        if (h.id != 0)
            pending_destroy_current_.pipelines.push_back(h);
    }

    void VulkanRenderDevice::destroy(ResourceSetHandle h) {
        if (h.id != 0)
            pending_destroy_current_.resource_sets.push_back(h);
    }

    void VulkanRenderDevice::drain_pending_destroy(PendingDestroyQueue& q) {
        for (auto h : q.buffers) {
            if (auto* r = buffers_.get(h.id)) {
                if (r->buffer)
                    vmaDestroyBuffer(allocator_, r->buffer, r->allocation);
                buffers_.remove(h.id);
            }
        }
        for (auto h : q.textures) {
            if (auto* r = textures_.get(h.id)) {
                if (r->attachment_view)
                    vkDestroyImageView(device_, r->attachment_view, nullptr);
                if (r->view)
                    vkDestroyImageView(device_, r->view, nullptr);
                if (r->image && !r->external)
                    vmaDestroyImage(allocator_, r->image, r->allocation);
                textures_.remove(h.id);
            }
        }
        for (auto h : q.samplers) {
            if (auto* r = samplers_.get(h.id)) {
                if (r->sampler)
                    vkDestroySampler(device_, r->sampler, nullptr);
                samplers_.remove(h.id);
            }
        }
        for (auto h : q.shaders) {
            if (auto* r = shaders_.get(h.id)) {
                if (r->module)
                    vkDestroyShaderModule(device_, r->module, nullptr);
                shaders_.remove(h.id);
            }
        }
        for (auto h : q.pipelines) {
            if (auto* r = pipelines_.get(h.id)) {
                if (r->pipeline)
                    vkDestroyPipeline(device_, r->pipeline, nullptr);
                pipelines_.remove(h.id);
            }
        }
        // Cached resource-set handles are owned by the per-pool descriptor cache
        // and are removed together with the VkDescriptorSet when the pool is reset.
        // Uncached sets, such as dynamic-ring UBO bindings, still allocate wrapper
        // metadata in resource_sets_ and must be released once the submitted command
        // buffer can no longer reference their dynamic offsets.
        for (auto h : q.resource_sets) {
            if (auto* r = resource_sets_.get(h.id)) {
                if (!r->descriptor_cache_owned) {
                    resource_sets_.remove(h.id);
                }
            }
        }
        for (auto fb : q.framebuffers) {
            if (fb != VK_NULL_HANDLE) {
                vkDestroyFramebuffer(device_, fb, nullptr);
            }
        }
        for (auto cb : q.cmd_buffers) {
            vkFreeCommandBuffers(device_, command_pool_, 1, &cb);
        }
        for (auto& [buf, alloc] : q.vma_buffers) {
            vmaDestroyBuffer(allocator_, buf, alloc);
        }
        q = {};
    }

} // namespace tgfx

#endif // TGFX2_HAS_VULKAN
