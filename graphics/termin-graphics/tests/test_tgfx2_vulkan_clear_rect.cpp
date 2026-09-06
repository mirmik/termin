#include "tgfx2/vulkan/vulkan_render_device.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>
#include <vector>

using namespace tgfx;

static void run(uint32_t samples) {
    VulkanRenderDevice device(VulkanDeviceCreateInfo{});
    TextureDesc desc;
    desc.width = 9;
    desc.height = 5;
    desc.mip_levels = samples == 1 ? 3 : 1;
    desc.sample_count = samples;
    // Clear must work without CopyDst, including on mipmapped attachments.
    desc.usage = TextureUsage::ColorAttachment | TextureUsage::Sampled | TextureUsage::CopySrc;
    const auto texture = device.create_texture(desc);
    if (!texture) throw std::runtime_error("texture creation failed");
    auto resolve_desc = desc;
    resolve_desc.sample_count = 1;
    resolve_desc.mip_levels = 1;
    const auto resolved = samples > 1 ? device.create_texture(resolve_desc) : TextureHandle{};
    const termin::LinearColor background{0.2f, 0.4f, 0.6f, 0.8f};
    const termin::LinearColor foreground{0.9f, 0.7f, 0.3f, 0.1f};
    const termin::Bounds2i rects[] = {
        {2, 1, 7, 3}, {0, 0, 9, 5}, {-4, -2, 3, 2}, {7, 3, 14, 9},
        {3, 2, 3, 4}, {7, 4, 2, 1}, {20, 20, 30, 30},
        {std::numeric_limits<int>::min(), std::numeric_limits<int>::min(),
         std::numeric_limits<int>::max(), std::numeric_limits<int>::max()}
    };
    auto commands = device.create_command_list();
    for (const auto rect : rects) {
        device.clear_texture(texture, background, {0, 0, 9, 5});
        device.clear_texture(texture, foreground, rect);
        commands->begin();
        if (resolved) {
            RenderPassDesc pass;
            ColorAttachmentDesc attachment;
            attachment.texture = texture;
            attachment.resolve_texture = resolved;
            attachment.load = LoadOp::Load;
            pass.colors.push_back(attachment);
            commands->begin_render_pass(pass);
            commands->end_render_pass();
        }
        commands->end();
        device.submit(*commands);
        std::vector<float> pixels(desc.width * desc.height * 4);
        if (!device.read_texture_rgba_float(resolved ? resolved : texture, pixels.data()))
            throw std::runtime_error("clear rect readback failed");
        for (int y = 0; y < 5; ++y) {
            for (int x = 0; x < 9; ++x) {
                const auto expected = x >= rect.x0 && x < rect.x1 && y >= rect.y0 && y < rect.y1
                    ? foreground : background;
                const float channels[] = {expected.r, expected.g, expected.b, expected.a};
                for (unsigned channel = 0; channel < 4; ++channel) {
                    if (std::abs(pixels[(y * 9 + x) * 4 + channel] - channels[channel]) > 0.01f) {
                        std::fprintf(stderr, "clear rect (%d,%d,%d,%d) pixel (%d,%d) channel %u\n",
                                     rect.x0, rect.y0, rect.x1, rect.y1, x, y, channel);
                        throw std::runtime_error("clear rect pixel mismatch");
                    }
                }
            }
        }
        device.wait_idle();
    }
    commands.reset();
    if (resolved) device.destroy(resolved);
    device.destroy(texture);
}

int main() {
    try { run(1); run(4); }
    catch (const std::exception& error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
    return 0;
}
