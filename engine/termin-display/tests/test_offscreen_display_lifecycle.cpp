#include "termin/platform/offscreen_render_surface.hpp"

#include <algorithm>
#include <array>
#include <cassert>
#include <limits>
#include <memory>
#include <span>
#include <vector>

#include "render/tc_display.h"
#include "tgfx/tgfx2_interop.h"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"

namespace {

    class TestRenderDevice final : public tgfx::IRenderDevice {
    public:
        explicit TestRenderDevice(tgfx::BackendType backend = tgfx::BackendType::D3D11)
            : backend_(backend) {}

        tgfx::BackendType backend_type() const override {
            return backend_;
        }
        tgfx::BackendCapabilities capabilities() const override {
            return {};
        }
        void wait_idle() override {}

        tgfx::BufferHandle create_buffer(const tgfx::BufferDesc&) override {
            return {};
        }
        tgfx::TextureHandle create_texture(const tgfx::TextureDesc& desc) override {
            // A display surface must work without depth-format support. Depth
            // belongs to pipeline render targets, not the compositing output.
            if (reject_allocation || tgfx::has_flag(desc.usage, tgfx::TextureUsage::DepthStencilAttachment)) {
                return {};
            }
            created.push_back(desc);
            return tgfx::TextureHandle{next_texture_id++};
        }
        tgfx::SamplerHandle create_sampler(const tgfx::SamplerDesc&) override {
            return {};
        }
        tgfx::ShaderHandle create_shader(const tgfx::ShaderDesc&) override {
            return {};
        }
        tgfx::PipelineHandle create_pipeline(const tgfx::PipelineDesc&) override {
            return {};
        }
        tgfx::ResourceSetHandle create_bound_resource_set(const tgfx::BoundResourceSetDesc&) override {
            return {};
        }

        void destroy(tgfx::BufferHandle) override {}
        void destroy(tgfx::TextureHandle texture) override {
            destroyed.push_back(texture);
        }
        void destroy(tgfx::SamplerHandle) override {}
        void destroy(tgfx::ShaderHandle) override {}
        void destroy(tgfx::PipelineHandle) override {}
        void destroy(tgfx::ResourceSetHandle) override {}

        void upload_buffer(tgfx::BufferHandle, std::span<const uint8_t>, uint64_t = 0) override {}
        void upload_texture(tgfx::TextureHandle, std::span<const uint8_t>, uint32_t = 0) override {}
        void upload_texture_region(tgfx::TextureHandle,
                                   uint32_t,
                                   uint32_t,
                                   uint32_t,
                                   uint32_t,
                                   std::span<const uint8_t>,
                                   uint32_t = 0) override {}
        void read_buffer(tgfx::BufferHandle, std::span<uint8_t>, uint64_t = 0) override {}
        bool read_texture_rgba_float(tgfx::TextureHandle texture, float* destination) override {
            ++read_calls;
            if (texture.id != next_texture_id - 1)
                return false;
            std::copy(pixels.begin(), pixels.end(), destination);
            return true;
        }
        tgfx::TextureDesc texture_desc(tgfx::TextureHandle) const override {
            return {};
        }
        std::unique_ptr<tgfx::ICommandList> create_command_list(tgfx::QueueType = tgfx::QueueType::Graphics) override {
            return {};
        }
        void submit(tgfx::ICommandList&) override {}
        void present() override {}

        std::vector<tgfx::TextureDesc> created;
        std::vector<tgfx::TextureHandle> destroyed;
        std::array<float, 16> pixels{};
        int read_calls = 0;
        bool reject_allocation = false;

    private:
        tgfx::BackendType backend_;
        uint32_t next_texture_id = 1;
    };

    void test_readback() {
        int owner = 0;
        TestRenderDevice device;
        assert(!tc_display_handle_valid(tc_display_new_offscreen_current(2, 2, nullptr)));
        assert(tgfx2_interop_claim_device(&device, &owner) == 1);
        assert(!tc_display_handle_valid(tc_display_new_offscreen_current(0, 2, nullptr)));
        const auto display = tc_display_new_offscreen_current(2, 2, "readback");
        assert(tc_display_handle_valid(display));

        // Two asymmetric rows with fractional linear values and varied alpha.
        device.pixels = {
            1.0f, 0.0f, 0.0f, 0.25f, 0.0f, 0.18f, 0.0f, 0.0f,
            0.0f, 0.0f, 1.0f, 0.75f, 0.0031308f, 0.5f, 1.0f, 0.0f,
        };
        constexpr size_t stride = 12;
        constexpr size_t pixel_bytes = stride + 8;
        constexpr uint8_t padding = 0xD7;
        std::array<uint8_t, 24> buffer;
        buffer.fill(padding);

        assert(!tc_display_read_offscreen_bgra_current(display, 2, 1, buffer.data(), stride, pixel_bytes));
        assert(!tc_display_read_offscreen_bgra_current(display, 2, 2, nullptr, stride, pixel_bytes));
        assert(!tc_display_read_offscreen_bgra_current(display, 2, 2, buffer.data(), 7, pixel_bytes));
        assert(!tc_display_read_offscreen_bgra_current(display, 2, 2, buffer.data(), stride, pixel_bytes - 1));
        assert(!tc_display_read_offscreen_bgra_current(
            display, 2, 2, buffer.data(), std::numeric_limits<size_t>::max(), pixel_bytes));
        assert(device.read_calls == 0);
        assert(std::all_of(buffer.begin(), buffer.end(), [&](uint8_t byte) { return byte == padding; }));

        assert(tgfx2_interop_release_device(&device, &owner) == 1);
        TestRenderDevice other;
        assert(tgfx2_interop_claim_device(&other, &owner) == 1);
        assert(!tc_display_read_offscreen_bgra_current(display, 2, 2, buffer.data(), stride, pixel_bytes));
        assert(other.read_calls == 0);
        assert(tgfx2_interop_release_device(&other, &owner) == 1);
        assert(tgfx2_interop_claim_device(&device, &owner) == 1);

        assert(tc_display_read_offscreen_bgra_current(display, 2, 2, buffer.data(), stride, pixel_bytes));
        constexpr std::array<uint8_t, 24> expected = {
            0, 0, 255, 255, 0, 118, 0, 255, padding, padding, padding, padding,
            255, 0, 0, 255, 255, 188, 10, 255, padding, padding, padding, padding,
        };
        assert(buffer == expected);
        assert(device.read_calls == 1);

        device.reject_allocation = true;
        assert(!tc_display_resize(display, 3, 2));
        assert(device.destroyed.empty());
        assert(tc_display_read_offscreen_bgra_current(display, 2, 2, buffer.data(), stride, pixel_bytes));
        device.reject_allocation = false;
        assert(tc_display_resize(display, 3, 2));
        assert(!tc_display_read_offscreen_bgra_current(display, 2, 2, buffer.data(), stride, pixel_bytes));
        assert(tc_display_free(display));
        const auto next = tc_display_new_offscreen_current(2, 2, "reused slot");
        assert(tc_display_handle_valid(next));
        assert(!tc_display_read_offscreen_bgra_current(display, 2, 2, buffer.data(), stride, pixel_bytes));
        assert(tc_display_free(next));
        assert(tgfx2_interop_release_device(&device, &owner) == 1);

        TestRenderDevice vulkan(tgfx::BackendType::Vulkan);
        assert(tgfx2_interop_claim_device(&vulkan, &owner) == 1);
        assert(!tc_display_handle_valid(tc_display_new_d3d11_offscreen_current(2, 2, nullptr)));
        const auto vulkan_display = tc_display_new_offscreen_current(2, 2, "Vulkan");
        assert(tc_display_handle_valid(vulkan_display));
        assert(tc_display_free(vulkan_display));
        assert(tgfx2_interop_release_device(&vulkan, &owner) == 1);
    }

} // namespace

int main() {
    tc_display_pool_init();
    TestRenderDevice device;
    tc_display_handle display = termin::create_offscreen_display(&device, 320, 200, "offscreen-lifecycle");
    assert(tc_display_handle_valid(display));
    assert(device.created.size() == 1u);
    assert(device.created[0].format == tgfx::PixelFormat::RGBA16F);
    assert(device.created[0].width == 320u);
    assert(device.created[0].height == 200u);
    assert(tc_display_get_color_texture_id(display) != 0u);
    assert(tc_display_get_graphics_domain_key(display) == reinterpret_cast<uintptr_t>(&device));

    assert(tc_display_resize(display, 640, 360));
    assert(device.created.size() == 2u);
    assert(device.created[1].format == tgfx::PixelFormat::RGBA16F);
    assert(device.created[1].width == 640u);
    assert(device.created[1].height == 360u);
    assert(device.destroyed.size() == 1u);

    // Explicit display destruction releases the current GPU texture while the
    // device is still alive, then frees surface storage.
    assert(tc_display_free(display));
    assert(device.destroyed.size() == 2u);
    assert(!tc_display_free(display));
    assert(device.destroyed.size() == 2u);

    // The public host-facing constructor resolves the application-owned
    // interop device without exposing a raw device pointer across the ABI.
    int owner = 0;
    assert(tgfx2_interop_claim_device(&device, &owner) == 1);
    tc_display_handle current_display = tc_display_new_d3d11_offscreen_current(128, 96, "current-device");
    assert(tc_display_handle_valid(current_display));
    assert(tc_display_get_graphics_domain_key(current_display) == reinterpret_cast<uintptr_t>(&device));
    assert(tc_display_free(current_display));
    assert(tgfx2_interop_release_device(&device, &owner) == 1);

    test_readback();
    tc_display_pool_shutdown();
    return 0;
}
