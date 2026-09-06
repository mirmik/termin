#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/backend_binding_plan.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>

using namespace tgfx;

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

static void run() {
    VulkanRenderDevice device(VulkanDeviceCreateInfo{});
    VkPhysicalDeviceProperties properties{};
    vkGetPhysicalDeviceProperties(device.physical_device(), &properties);
    const uint32_t stride = static_cast<uint32_t>(std::max<VkDeviceSize>(16, properties.limits.minUniformBufferOffsetAlignment));
    const float colors[3][4] = {{0.8f,0.2f,0.6f,0.9f}, {0.3f,0.7f,0.1f,0.4f}, {0.6f,0.4f,0.9f,0.2f}};
    std::vector<uint8_t> bytes(2 * stride + 16);
    for (size_t i = 0; i < 3; ++i) std::memcpy(bytes.data() + i * stride, colors[i], 16);
    BufferDesc buffer_desc;
    buffer_desc.size = bytes.size();
    buffer_desc.usage = BufferUsage::Uniform | BufferUsage::CopyDst;
    const auto buffer = device.create_buffer(buffer_desc);
    device.upload_buffer(buffer, bytes);

    ShaderDesc shader;
    shader.stage = ShaderStage::Vertex;
    shader.source = R"(
#version 450
void main() {
    vec2 p[3]=vec2[](vec2(-1,-1),vec2(3,-1),vec2(-1,3));
    gl_Position=vec4(p[gl_VertexIndex],0,1);
})";
    const auto vertex = device.create_shader(shader);
    shader.stage = ShaderStage::Fragment;
    shader.source = R"(
#version 450
layout(binding=0) uniform ColorBlock { vec4 value; };
layout(location=0) out vec4 first;
layout(location=1) out vec4 second;
void main() { first=value; second=vec4(1)-value; }
)";
    const auto fragment = device.create_shader(shader);
    PipelineDesc pipeline_desc;
    pipeline_desc.vertex_shader = vertex;
    pipeline_desc.fragment_shader = fragment;
    pipeline_desc.color_formats = {PixelFormat::RGBA8_UNorm, PixelFormat::RGBA8_UNorm};
    pipeline_desc.depth_format = PixelFormat::Undefined;
    pipeline_desc.depth_stencil.depth_test = false;
    pipeline_desc.depth_stencil.depth_write = false;
    pipeline_desc.raster.cull = CullMode::None;

    TextureDesc texture_desc;
    texture_desc.width = texture_desc.height = 8;
    texture_desc.usage = TextureUsage::ColorAttachment | TextureUsage::CopySrc;
    const std::array<TextureHandle,2> targets{device.create_texture(texture_desc), device.create_texture(texture_desc)};
    const float initial[4] = {0.15f,0.25f,0.35f,0.45f};
    const ColorMask masks[] = {{true,true,true,true}, {true,false,false,false}, {true,true,true,false},
                               {false,false,false,true}, {false,false,false,false}, {false,true,true,false}};
    for (const auto mask : masks) {
        pipeline_desc.color_mask = mask;
        const auto pipeline = device.create_pipeline(pipeline_desc);
        require(bool(pipeline), "MRT pipeline creation failed");
        const auto create_set = [&](uint64_t offset, uint64_t range = 16) {
            BoundResourceBinding binding{};
            binding.slot.placement.kind = BackendPlacementKind::VulkanDescriptor;
            binding.slot.placement.vulkan.binding = 0;
            binding.slot.placement.vulkan.descriptor_kind = BackendDescriptorKind::UniformBuffer;
            binding.value.kind = BoundResourceKind::UniformBuffer;
            binding.value.buffer = buffer;
            binding.value.offset = offset;
            binding.value.range = range;
            BoundResourceSetStorage storage;
            storage.set_resource_layout_token(device.pipeline_resource_layout_token(pipeline));
            storage.append_group(ShaderResourceScope::Material, true, &binding, 1);
            return device.create_bound_resource_set(storage.view());
        };
        const auto first = create_set(0);
        const auto second = create_set(stride);
        const auto first_again = create_set(0);
        require(first && second && first == first_again && first != second, "UBO descriptor cache aliases base offsets");
        const auto remaining = create_set(2 * stride, 0);
        require(remaining && remaining == create_set(2 * stride, 16), "implicit UBO range lost base offset");
        require(!create_set(bytes.size()) && !create_set(stride, bytes.size()), "out-of-bounds UBO accepted");
        if (properties.limits.minUniformBufferOffsetAlignment > 1)
            require(!create_set(1), "misaligned UBO accepted");
        const std::array<ResourceSetHandle,5> sets{first,second,first_again,second,remaining};
        const unsigned indices[] = {0,1,0,2,2};
        for (unsigned draw = 0; draw < sets.size(); ++draw) {
            auto commands = device.create_command_list();
            commands->begin();
            RenderPassDesc pass;
            for (auto target : targets) {
                ColorAttachmentDesc attachment;
                attachment.texture = target;
                attachment.load = LoadOp::Clear;
                attachment.clear_color = {initial[0],initial[1],initial[2],initial[3]};
                pass.colors.push_back(attachment);
            }
            commands->begin_render_pass(pass);
            commands->set_viewport(0,0,8,8);
            commands->bind_pipeline(pipeline);
            // An explicit dynamic offset is additive to the descriptor base.
            if (draw == 3) commands->bind_resource_set(sets[draw], 0, &stride, 1);
            else commands->bind_resource_set(sets[draw]);
            commands->draw(3);
            commands->end_render_pass();
            commands->end();
            device.submit(*commands);
            const bool enabled[] = {mask.r,mask.g,mask.b,mask.a};
            for (unsigned attachment = 0; attachment < targets.size(); ++attachment) {
                float pixel[4]{};
                require(device.read_pixel_rgba8(targets[attachment],4,4,pixel), "MRT readback failed");
                for (unsigned channel = 0; channel < 4; ++channel) {
                    const float output = attachment == 0 ? colors[indices[draw]][channel] : 1.0f-colors[indices[draw]][channel];
                    const float expected = enabled[channel] ? output : initial[channel];
                    if (std::abs(pixel[channel]-expected) > 0.01f) {
                        std::fprintf(stderr,"draw=%u attachment=%u channel=%u got=%g expected=%g\n",
                                     draw,attachment,channel,pixel[channel],expected);
                        throw std::runtime_error("UBO offset/color mask pixel mismatch");
                    }
                }
            }
            device.wait_idle();
        }
        device.destroy(first);
        device.destroy(second);
        device.destroy(remaining);
        device.destroy(pipeline);
    }
    device.destroy(buffer);
    device.destroy(vertex);
    device.destroy(fragment);
    for (auto target : targets) device.destroy(target);
}

int main() {
    try { run(); }
    catch (const std::exception& error) {
        std::fprintf(stderr,"Vulkan pipeline contracts: %s\n",error.what());
        return 1;
    }
    std::puts("Vulkan UBO offsets/cache/dynamic addition and MRT color masks passed");
}
