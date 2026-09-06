#include "tgfx2/vulkan/vulkan_render_device.hpp"

#include <array>
#include <cmath>
#include <cstdio>
#include <exception>

using namespace tgfx;

static void submit_empty(VulkanRenderDevice& device) {
    auto cmd = device.create_command_list();
    cmd->begin();
    cmd->end();
    device.submit(*cmd);
}

int main() {
    try {
        VulkanRenderDevice device(VulkanDeviceCreateInfo{});
        bool ok = true;
        std::array<uint8_t, 64> bytes{};
        for (size_t i = 0; i < bytes.size(); ++i)
            bytes[i] = static_cast<uint8_t>(i * 3 + 1);
        const auto gpu = device.create_buffer({bytes.size(), BufferUsage::CopySrc});
        const auto host = device.create_buffer({bytes.size(), BufferUsage::CopyDst, true});
        device.upload_buffer(gpu, bytes);
        auto copy = device.create_command_list();
        copy->begin();
        copy->copy_buffer(gpu, host, bytes.size());
        copy->end();
        device.submit(*copy);
        for (auto buffer : {gpu, host}) {
            std::array<uint8_t, 13> result{};
            // Completion is the responsibility of read_buffer, without caller wait_idle.
            device.read_buffer(buffer, result, 7);
            for (size_t i = 0; i < result.size(); ++i)
                ok &= result[i] == bytes[i + 7];
            const auto original = result;
            device.read_buffer(buffer, result, bytes.size() - 2);
            ok &= result == original;
        }

        TextureDesc desc;
        desc.width = desc.height = 2;
        desc.usage = TextureUsage::ColorAttachment | TextureUsage::CopySrc | TextureUsage::CopyDst;
        const auto color = device.create_texture(desc);
        desc.format = PixelFormat::D32F;
        desc.usage = TextureUsage::DepthStencilAttachment | TextureUsage::CopySrc | TextureUsage::CopyDst;
        const auto depth = device.create_texture(desc);
        const std::array<uint8_t, 16> rgba{11, 22, 33, 255, 44, 55, 66, 255,
                                           77, 88, 99, 255, 111, 122, 133, 255};
        const std::array<float, 4> depths{0.125f, 0.25f, 0.5f, 0.75f};
        device.upload_texture(color, rgba);
        device.upload_texture(depth, {reinterpret_cast<const uint8_t*>(depths.data()), sizeof(depths)});
        submit_empty(device);
        std::array<float, 16> colors{};
        std::array<float, 4> depth_output{};
        ok &= device.read_texture_rgba_float(color, colors.data());
        ok &= device.read_texture_depth_float(depth, depth_output.data());
        for (size_t i = 0; i < rgba.size(); ++i)
            ok &= std::fabs(colors[i] - rgba[i] / 255.0f) < 0.001f;
        ok &= depth_output == depths;
        float pixel[4]{};
        float pixel_depth = -1;
        ok &= device.read_pixel_rgba8(color, 1, 0, pixel);
        ok &= device.read_pixel_depth_float(depth, 0, 1, &pixel_depth);
        ok &= std::fabs(pixel[0] - 44 / 255.0f) < 0.001f && pixel_depth == 0.5f;

        // Wrong format and bounds must preserve outputs and issue no invalid native copy.
        const float saved = pixel_depth;
        ok &= !device.read_pixel_depth_float(depth, 2, 0, &pixel_depth) && pixel_depth == saved;
        const std::array<float, 4> saved_color{pixel[0], pixel[1], pixel[2], pixel[3]};
        ok &= !device.read_pixel_rgba8(depth, 0, 0, pixel);
        for (size_t i = 0; i < saved_color.size(); ++i) ok &= pixel[i] == saved_color[i];
        ok &= device.request_pixel_rgba8(depth, 0, 0) == 0;

        auto color_request = device.request_pixel_rgba8(color, 1, 1);
        auto depth_request = device.request_pixel_depth_float(depth, 1, 0);
        ok &= color_request != 0 && depth_request != 0;
        // Idle before submission cannot complete a merely recorded request.
        device.wait_idle();
        ok &= !device.poll_pixel_rgba8(color_request, pixel);
        ok &= !device.poll_pixel_depth_float(depth_request, &pixel_depth);
        submit_empty(device);
        device.wait_idle();
        ok &= device.poll_pixel_rgba8(color_request, pixel);
        ok &= device.poll_pixel_depth_float(depth_request, &pixel_depth);
        ok &= std::fabs(pixel[0] - 111 / 255.0f) < 0.001f && pixel_depth == 0.25f;
        ok &= !device.poll_pixel_rgba8(color_request, pixel);

        // GPU attachment writes, then async completion through frame-slot fences.
        auto render = device.create_command_list();
        render->begin();
        RenderPassDesc pass;
        ColorAttachmentDesc attachment;
        attachment.texture = color;
        attachment.load = LoadOp::Clear;
        attachment.clear_color = {0.6f, 0.4f, 0.2f, 1.0f};
        pass.colors.push_back(attachment);
        pass.has_depth = true;
        pass.depth.texture = depth;
        pass.depth.load = LoadOp::Clear;
        pass.depth.clear_depth = 0.375f;
        render->begin_render_pass(pass);
        render->end_render_pass();
        render->end();
        device.submit(*render);
        color_request = device.request_pixel_rgba8(color, 0, 0);
        depth_request = device.request_pixel_depth_float(depth, 0, 0);
        for (unsigned i = 0; i < 7; ++i) submit_empty(device);
        ok &= device.poll_pixel_rgba8(color_request, pixel);
        ok &= device.poll_pixel_depth_float(depth_request, &pixel_depth);
        ok &= std::fabs(pixel[0] - 0.6f) < 0.01f && pixel_depth == 0.375f;
        device.wait_idle();
        copy.reset();
        render.reset();
        device.destroy(color);
        device.destroy(depth);
        device.destroy(gpu);
        device.destroy(host);
        if (!ok) {
            std::fprintf(stderr, "Readback native: bytes/pixels/completion contract failed\n");
            return 1;
        }
        std::puts("Readback native: buffer offsets, color/depth sync and async completion passed");
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Readback native: %s\n", error.what());
        return 1;
    }
    return 0;
}
