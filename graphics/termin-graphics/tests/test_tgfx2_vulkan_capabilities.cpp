#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/backend_binding_plan.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>

using namespace tgfx;

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

static ShaderHandle shader(VulkanRenderDevice& device, ShaderStage stage, const char* source) {
    ShaderDesc desc;
    desc.stage = stage;
    desc.source = source;
    return device.create_shader(desc);
}

static void run() {
    VulkanRenderDevice device(VulkanDeviceCreateInfo{});
    const auto& caps = device.capabilities();
    VkPhysicalDeviceProperties properties{};
    VkPhysicalDeviceFeatures features{};
    vkGetPhysicalDeviceProperties(device.physical_device(), &properties);
    vkGetPhysicalDeviceFeatures(device.physical_device(), &features);
    require(!caps.supports_compute && !caps.supports_storage_textures, "unimplemented capabilities advertised");
    require(caps.max_texture_units == std::min(properties.limits.maxDescriptorSetSampledImages,
                                               properties.limits.maxDescriptorSetSamplers), "wrong texture limit");
    require(caps.max_fragment_texture_units == std::min(properties.limits.maxPerStageDescriptorSampledImages,
                                                        properties.limits.maxPerStageDescriptorSamplers),
            "wrong fragment texture limit");
    require(caps.supports_geometry_shaders == bool(features.geometryShader), "geometry capability mismatch");

    auto commands = device.create_command_list();
    commands->begin();
    bool rejected = false;
    try { commands->dispatch(1, 1, 1); } catch (const std::runtime_error&) { rejected = true; }
    require(rejected, "unsupported dispatch accepted");
    commands->end();
    commands.reset();
    for (float invalid : {0.0f, std::numeric_limits<float>::quiet_NaN(),
                           properties.limits.maxSamplerAnisotropy + 1.0f}) {
        SamplerDesc desc;
        desc.max_anisotropy = invalid;
        rejected = false;
        try { device.create_sampler(desc); } catch (const std::runtime_error&) { rejected = true; }
        require(rejected, "invalid anisotropy accepted");
    }

    const auto vertex = shader(device, ShaderStage::Vertex, R"(
#version 450
void main() {
    vec2 p[3]=vec2[](vec2(-1,-1),vec2(3,-1),vec2(-1,3));
    gl_Position=vec4(p[gl_VertexIndex],0,1);
})");
    const char* geometry_source = R"(
#version 450
layout(triangles) in;
layout(triangle_strip, max_vertices=3) out;
layout(binding=2) uniform GeometryOffset { vec4 offset; };
void main() {
    for(int i=0;i<3;i++) { gl_Position=gl_in[i].gl_Position+offset; EmitVertex(); }
    EndPrimitive();
})";
    ShaderHandle geometry;
    if (caps.supports_geometry_shaders) {
        geometry = shader(device, ShaderStage::Geometry, geometry_source);
    } else {
        rejected = false;
        try { shader(device, ShaderStage::Geometry, geometry_source); }
        catch (const std::runtime_error&) { rejected = true; }
        require(rejected, "disabled geometry accepted");
    }
    const auto fragment = shader(device, ShaderStage::Fragment, R"(
#version 450
layout(binding=0) uniform texture2D source_texture;
layout(binding=1) uniform sampler source_sampler;
layout(location=0) out vec4 color;
void main() { color=texture(sampler2D(source_texture,source_sampler),vec2(0.5)); }
)");
    PipelineDesc pipeline_desc;
    pipeline_desc.vertex_shader = vertex;
    pipeline_desc.geometry_shader = geometry;
    pipeline_desc.fragment_shader = fragment;
    pipeline_desc.color_formats = {PixelFormat::RGBA8_UNorm};
    pipeline_desc.depth_format = PixelFormat::Undefined;
    pipeline_desc.depth_stencil.depth_test = false;
    pipeline_desc.depth_stencil.depth_write = false;
    pipeline_desc.raster.cull = CullMode::None;
    // Exercise the enabled optional raster feature as part of a real draw.
    pipeline_desc.raster.depth_bias_clamp = features.depthBiasClamp ? 0.5f : 0.0f;
    pipeline_desc.raster.depth_bias_enabled = features.depthBiasClamp != VK_FALSE;
    const auto pipeline = device.create_pipeline(pipeline_desc);
    require(bool(pipeline), "sampled-image/geometry pipeline failed");

    TextureDesc texture_desc;
    texture_desc.usage = TextureUsage::Sampled | TextureUsage::CopyDst;
    const auto texture = device.create_texture(texture_desc);
    const uint8_t pixel[] = {51,153,204,255};
    device.upload_texture(texture, pixel);
    SamplerDesc sampler_desc;
    sampler_desc.max_anisotropy = features.samplerAnisotropy ? properties.limits.maxSamplerAnisotropy : 1.0f;
    const auto sampler = device.create_sampler(sampler_desc);
    BufferDesc buffer_desc;
    buffer_desc.size = 16;
    buffer_desc.usage = BufferUsage::Uniform | BufferUsage::CopyDst;
    const auto buffer = device.create_buffer(buffer_desc);
    const uint8_t zero[16]{};
    device.upload_buffer(buffer, zero);

    BoundResourceBinding bindings[3]{};
    for (uint32_t i=0; i<3; ++i) {
        bindings[i].slot.placement.kind = BackendPlacementKind::VulkanDescriptor;
        bindings[i].slot.placement.vulkan.binding = i;
    }
    bindings[0].slot.placement.vulkan.descriptor_kind = BackendDescriptorKind::SampledTexture;
    bindings[0].value.kind = BoundResourceKind::SampledTexture;
    bindings[0].value.texture = texture;
    bindings[1].slot.placement.vulkan.descriptor_kind = BackendDescriptorKind::Sampler;
    bindings[1].value.kind = BoundResourceKind::Sampler;
    bindings[1].value.sampler = sampler;
    bindings[2].slot.placement.vulkan.descriptor_kind = BackendDescriptorKind::UniformBuffer;
    bindings[2].value.kind = BoundResourceKind::UniformBuffer;
    bindings[2].value.buffer = buffer;
    bindings[2].value.range = 16;
    BoundResourceSetStorage storage;
    storage.set_resource_layout_token(device.pipeline_resource_layout_token(pipeline));
    storage.append_group(ShaderResourceScope::Material, true, bindings, geometry ? 3 : 2);
    const auto resources = device.create_bound_resource_set(storage.view());
    require(bool(resources), "separate texture/sampler resources failed");
    bindings[0].value.texture = {};
    bindings[1].value.sampler = {};
    BoundResourceSetStorage defaults_storage;
    defaults_storage.set_resource_layout_token(device.pipeline_resource_layout_token(pipeline));
    defaults_storage.append_group(ShaderResourceScope::Material, true, bindings, geometry ? 3 : 2);
    const auto defaults = device.create_bound_resource_set(defaults_storage.view());
    require(bool(defaults), "default separate texture/sampler resources failed");
    texture_desc.width = texture_desc.height = 8;
    texture_desc.usage = TextureUsage::ColorAttachment | TextureUsage::CopySrc;
    const auto target = device.create_texture(texture_desc);
    for (const auto set : {resources, defaults}) {
        commands = device.create_command_list();
        commands->begin();
        RenderPassDesc pass;
        ColorAttachmentDesc attachment;
        attachment.texture = target;
        attachment.load = LoadOp::Clear;
        pass.colors.push_back(attachment);
        commands->begin_render_pass(pass);
        commands->set_viewport(0,0,8,8);
        commands->bind_pipeline(pipeline);
        commands->bind_resource_set(set);
        commands->draw(3);
        commands->end_render_pass();
        commands->end();
        device.submit(*commands);
        float color[4]{};
        require(device.read_pixel_rgba8(target,4,4,color), "readback failed");
        if (set == resources) {
            require(std::abs(color[0]-0.2f)<0.01f && std::abs(color[1]-0.6f)<0.01f &&
                    std::abs(color[2]-0.8f)<0.01f, "separate texture/sampler pixel mismatch");
        } else {
            require(color[0]>0.99f && color[1]>0.99f && color[2]>0.99f, "default sampling pixel mismatch");
        }
        device.wait_idle();
        commands.reset();
    }

    const auto storage_fragment = shader(device, ShaderStage::Fragment, R"(
#version 450
layout(binding=0,rgba8) readonly uniform image2D source;
layout(location=0) out vec4 color;
void main() { color=imageLoad(source,ivec2(0)); }
)");
    pipeline_desc.fragment_shader = storage_fragment;
    require(!device.create_pipeline(pipeline_desc), "unsupported storage image pipeline accepted");
    TextureDesc storage_desc;
    storage_desc.usage = TextureUsage::Storage;
    require(!device.supports_texture(storage_desc), "unsupported storage texture advertised");
    rejected = false;
    try { device.create_texture(storage_desc); } catch (const std::runtime_error&) { rejected = true; }
    require(rejected, "unsupported storage texture created");
    device.destroy(resources);
    device.destroy(defaults);
    device.destroy(pipeline);
    device.destroy(vertex);
    device.destroy(fragment);
    if (geometry) device.destroy(geometry);
    device.destroy(storage_fragment);
    device.destroy(buffer);
    device.destroy(sampler);
    device.destroy(texture);
    device.destroy(target);
}

int main() {
    try { run(); }
    catch (const std::exception& error) {
        std::fprintf(stderr, "Vulkan capabilities regression: %s\n", error.what());
        return 1;
    }
    std::puts("Vulkan capabilities: limits, feature guards and separate sampling pixel passed");
}
