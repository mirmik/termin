#include "tgfx2/backend_binding_plan.hpp"
#include "tgfx2/vulkan/vulkan_command_list.hpp"
#include "tgfx/resources/tc_shader.h"

#include <array>
#include <cmath>
#include <cstdio>
#include <exception>
#include <vector>

using namespace tgfx;

template <class T> static std::span<const uint8_t> bytes(const T& value) {
    return {reinterpret_cast<const uint8_t*>(&value), sizeof(value)};
}

// The fixture owns its download barriers so failures in the separate image /
// host-readback contracts do not obscure buffer synchronization regressions.
static void capture(VulkanRenderDevice& device, ICommandList& commands, TextureHandle image, BufferHandle output) {
    auto* texture = device.get_texture(image);
    const VkCommandBuffer cmd = static_cast<VulkanCommandList&>(commands).command_buffer();
    VkImageMemoryBarrier image_barrier{};
    image_barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    image_barrier.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    image_barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
    image_barrier.oldLayout = texture->current_layout;
    image_barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    image_barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    image_barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    image_barrier.image = texture->image;
    image_barrier.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &image_barrier);
    texture->current_layout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    const auto buffer = device.get_buffer(output)->buffer;
    VkBufferImageCopy copy{};
    copy.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
    copy.imageOffset = {8, 8, 0};
    copy.imageExtent = {1, 1, 1};
    vkCmdCopyImageToBuffer(cmd, texture->image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, buffer, 1, &copy);
    VkBufferMemoryBarrier host_barrier{};
    host_barrier.sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER;
    host_barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    host_barrier.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
    host_barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    host_barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    host_barrier.buffer = buffer;
    host_barrier.size = 4;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                         0, 0, nullptr, 1, &host_barrier, 0, nullptr);
}

int main() {
    try {
        VulkanRenderDevice device(VulkanDeviceCreateInfo{});
        ShaderDesc shader;
        shader.stage = ShaderStage::Vertex;
        shader.source = R"(
#version 450
layout(location=0) in vec2 position;
layout(location=1) in vec3 tint;
layout(location=0) out vec3 color;
void main() { gl_Position=vec4(position,0,1); color=tint; }
)";
        const auto vs = device.create_shader(shader);
        shader.stage = ShaderStage::Fragment;
        shader.source = R"(
#version 450
layout(location=0) in vec3 color;
layout(binding=0) uniform ColorBlock { vec4 multiplier; };
layout(location=0) out vec4 result;
void main() { result=vec4(color,1)*multiplier; }
)";
        const auto fs = device.create_shader(shader);
        PipelineDesc pipeline_desc;
        pipeline_desc.vertex_shader = vs;
        pipeline_desc.fragment_shader = fs;
        pipeline_desc.depth_stencil.depth_test = false;
        pipeline_desc.depth_stencil.depth_write = false;
        pipeline_desc.depth_format = PixelFormat::Undefined;
        pipeline_desc.raster.cull = CullMode::None;
        pipeline_desc.color_formats = {PixelFormat::RGBA8_UNorm};
        VertexBufferLayout layout;
        layout.stride = 5 * sizeof(float);
        layout.attributes = {{0, VertexFormat::Float2, 0}, {1, VertexFormat::Float3, 2 * sizeof(float)}};
        pipeline_desc.vertex_layouts.push_back(make_vertex_layout_desc(layout));
        const auto pipeline = device.create_pipeline(pipeline_desc);
        const auto vb = device.create_buffer({6 * layout.stride, BufferUsage::Vertex});
        const auto ib = device.create_buffer({3 * sizeof(uint32_t), BufferUsage::Index});
        const auto ub = device.create_buffer({4 * sizeof(float), BufferUsage::Uniform});
        std::vector<BufferHandle> sources;
        std::vector<BufferHandle> outputs;
        std::vector<TextureHandle> targets;
        std::vector<std::array<float, 4>> expected;

        BackendBindingPlanEntry entry;
        entry.resource.name = "ColorBlock";
        entry.resource.kind = ShaderResourceKind::ConstantBuffer;
        entry.resource.scope = ShaderResourceScope::Material;
        entry.stage_mask = TC_SHADER_STAGE_FRAGMENT;
        entry.size = 4 * sizeof(float);
        entry.placement.kind = BackendPlacementKind::VulkanDescriptor;
        entry.placement.vulkan.descriptor_kind = BackendDescriptorKind::UniformBuffer;
        BoundResourceValue value;
        value.kind = BoundResourceKind::UniformBuffer;
        value.buffer = ub;
        value.range = entry.size;
        const BoundResourceBinding binding{bound_resource_slot_from_plan_entry(entry), value};

        // Three submissions, two draws each: upload -> draw -> copy overwrite ->
        // draw, then another upload over the previous submission's GPU readers.
        // There is no CPU wait/idle between submissions or between draws.
        for (unsigned frame = 0; frame < 3; ++frame) {
            auto commands = device.create_command_list();
            commands->begin();
            BoundResourceSetStorage storage;
            storage.set_resource_layout_token(device.pipeline_resource_layout_token(pipeline));
            storage.append_group(ShaderResourceScope::Material, true, &binding, 1);
            const auto resources = device.create_bound_resource_set(storage.view());
            for (unsigned step = 0; step < 2; ++step) {
                const unsigned n = frame * 2 + step;
                const float tint = 0.2f + 0.1f * static_cast<float>(n);
                const std::array<float, 4> multiplier{0.8f, 0.25f + 0.1f * static_cast<float>(n), 0.6f, 1.0f};
                std::array<float, 30> vertices{};
                constexpr float positions[] = {-1, -1, 3, -1, -1, 3};
                const unsigned selected = n % 2;
                for (unsigned i = 0; i < 6; ++i) {
                    vertices[i * 5] = positions[(i % 3) * 2];
                    vertices[i * 5 + 1] = positions[(i % 3) * 2 + 1];
                    vertices[i * 5 + 2] = i / 3 == selected ? tint : 0.0f;
                    vertices[i * 5 + 3] = i / 3 == selected ? 1.0f : 0.0f;
                    vertices[i * 5 + 4] = i / 3 == selected ? 0.5f : 0.0f;
                }
                const std::array<uint32_t, 3> indices{selected * 3, selected * 3 + 1, selected * 3 + 2};
                auto copy_upload = [&](BufferHandle destination, std::span<const uint8_t> data) {
                    // Nonzero source offset exercises byte-range dependencies.
                    const auto source = device.create_buffer({data.size() + 16, BufferUsage::CopySrc});
                    sources.push_back(source);
                    device.upload_buffer(source, data, 16);
                    commands->copy_buffer(source, destination, data.size(), 16, 0);
                };
                if (step == 0) {
                    device.upload_buffer(vb, bytes(vertices));
                    device.upload_buffer(ib, bytes(indices));
                } else {
                    copy_upload(vb, bytes(vertices));
                    copy_upload(ib, bytes(indices));
                }
                // UBOs are mapped by default; use GPU copies to exercise
                // transfer -> uniform visibility and prior uniform reads.
                copy_upload(ub, bytes(multiplier));
                TextureDesc target_desc;
                target_desc.width = target_desc.height = 16;
                target_desc.usage = TextureUsage::ColorAttachment | TextureUsage::CopySrc;
                const auto target = device.create_texture(target_desc);
                targets.push_back(target);
                const auto output = device.create_buffer({4, BufferUsage::CopyDst, true});
                outputs.push_back(output);
                if (!device.get_buffer(output)->host_coherent) {
                    std::fprintf(stderr, "Buffer sync fixture requires coherent capture memory\n");
                    return 1;
                }
                RenderPassDesc pass;
                ColorAttachmentDesc attachment;
                attachment.texture = target;
                attachment.load = LoadOp::Clear;
                pass.colors.push_back(attachment);
                commands->begin_render_pass(pass);
                commands->set_viewport(0, 0, 16, 16);
                commands->bind_pipeline(pipeline);
                commands->bind_resource_set(resources);
                commands->bind_vertex_buffer(0, vb);
                commands->bind_index_buffer(ib, IndexType::Uint32);
                commands->draw_indexed(3);
                commands->end_render_pass();
                capture(device, *commands, target, output);
                expected.push_back({tint * multiplier[0], multiplier[1], 0.5f * multiplier[2], 1.0f});
            }
            commands->end();
            device.submit(*commands);
            device.destroy(resources);
        }
        device.wait_idle();
        bool ok = true;
        for (size_t i = 0; i < outputs.size(); ++i) {
            const auto* actual = static_cast<const uint8_t*>(device.get_buffer(outputs[i])->mapped_ptr);
            for (unsigned channel = 0; channel < 4; ++channel) {
                if (std::fabs(static_cast<float>(actual[channel]) / 255.0f - expected[i][channel]) > 0.01f) {
                    std::fprintf(stderr, "Buffer sync pixel %zu channel %u: got %u expected %.3f\n",
                                 i, channel, actual[channel], expected[i][channel]);
                    ok = false;
                }
            }
        }
        for (auto buffer : sources) device.destroy(buffer);
        for (auto buffer : outputs) device.destroy(buffer);
        for (auto texture : targets) device.destroy(texture);
        device.destroy(vb);
        device.destroy(ib);
        device.destroy(ub);
        device.destroy(pipeline);
        device.destroy(vs);
        device.destroy(fs);
        if (!ok) return 1;
        std::puts("Buffer sync: six indexed pixels passed without inter-frame idle");
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Buffer sync regression: %s\n", error.what());
        return 1;
    }
    return 0;
}
