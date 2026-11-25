#include <cstddef>
#include <cstdint>
#include <exception>

#include <geom/tc_color.h>
#include <render/tc_display.h>
#include <tcbase/tc_log.h>
#include <termin/platform/offscreen_render_surface.hpp>
#include <tgfx/tgfx2_interop.h>
#include <tgfx2/i_command_list.hpp>
#include <tgfx2/i_render_device.hpp>

#if defined(_WIN32)
#define POSITIONER_PROBE_EXPORT extern "C" __declspec(dllexport)
#else
#define POSITIONER_PROBE_EXPORT extern "C" __attribute__((visibility("default")))
#endif

namespace {
    int read_error(const char* message) {
        tc_log_error("positioner_read_bgra: %s", message);
        return 0;
    }

    std::uint8_t encode_byte(float srgb) {
        if (!(srgb > 0.0f))
            return 0;
        if (srgb >= 1.0f)
            return 255;
        return static_cast<std::uint8_t>(srgb * 255.0f + 0.5f);
    }
} // namespace

POSITIONER_PROBE_EXPORT tc_display_handle positioner_create_offscreen_display(int width, int height) noexcept {
    try {
        return termin::create_offscreen_display(tgfx::get_tgfx2_device(), width, height, "Avalonia positioner");
    } catch (const std::exception& error) {
        tc_log_error("positioner_create_offscreen_display: %s", error.what());
    } catch (...) {
        tc_log_error("positioner_create_offscreen_display: unexpected exception");
    }
    return TC_DISPLAY_HANDLE_INVALID;
}

// Call on the render thread. Scratch RGBA is caller-owned and tightly packed.
// Avalonia receives opaque sRGB BGRA in top-left row order with its own stride.
POSITIONER_PROBE_EXPORT int positioner_read_bgra(tc_display_handle display,
                                                 int width,
                                                 int height,
                                                 float* rgba,
                                                 std::size_t rgba_count,
                                                 std::uint8_t* bgra,
                                                 std::size_t bgra_bytes,
                                                 std::size_t bgra_stride) noexcept {
    if (width <= 0 || height <= 0 || !rgba || !bgra)
        return read_error("positive dimensions and valid buffers are required");

    constexpr std::size_t max_bytes = SIZE_MAX;
    const auto columns = static_cast<std::size_t>(width);
    const auto rows = static_cast<std::size_t>(height);
    if (columns > max_bytes / 4)
        return read_error("row size overflows");
    const std::size_t row_components = columns * 4;
    if (rows > max_bytes / sizeof(float) / row_components || rgba_count < rows * row_components)
        return read_error("RGBA scratch buffer is too small");
    if (bgra_stride < row_components || rows - 1 > (max_bytes - row_components) / bgra_stride ||
        bgra_bytes < (rows - 1) * bgra_stride + row_components)
        return read_error("BGRA frame buffer is too small");

    try {
        auto* device = tgfx::get_tgfx2_device();
        if (!device)
            return read_error("no graphics device is active");
        tgfx::TextureHandle texture{};
        if (!tc_display_validate_output(display, reinterpret_cast<std::uintptr_t>(device), &texture.id))
            return read_error("display has no output in the active graphics domain");
        const auto desc = device->texture_desc(texture);
        if (desc.width != columns || desc.height != rows || desc.format != tgfx::PixelFormat::RGBA16F ||
            desc.sample_count != 1 || desc.array_layers != 1)
            return read_error("offscreen texture must match the requested size and use single-sample RGBA16F");
        if (device->backend_type() == tgfx::BackendType::Vulkan) {
            // The display composite records a transfer after the scene's draw submission.
            // Submit it before the synchronous readback uses its own command buffer.
            auto commands = device->create_command_list();
            if (!commands)
                return read_error("could not create the Vulkan display submission");
            commands->begin();
            commands->end();
            device->submit(*commands);
        }
        if (!device->read_texture_rgba_float(texture, rgba))
            return read_error("graphics device could not read the display texture");

        for (std::size_t y = 0; y < rows; ++y) {
            const float* source = rgba + y * row_components;
            std::uint8_t* dest = bgra + y * bgra_stride;
            for (std::size_t x = 0; x < columns; ++x, source += 4, dest += 4) {
                const tc_srgb_color srgb = tc_linear_to_srgb({source[0], source[1], source[2], 1.0f});
                dest[0] = encode_byte(srgb.b);
                dest[1] = encode_byte(srgb.g);
                dest[2] = encode_byte(srgb.r);
                dest[3] = 255;
            }
        }
        return 1;
    } catch (const std::exception& error) {
        return read_error(error.what());
    } catch (...) {
        return read_error("unexpected exception");
    }
}
