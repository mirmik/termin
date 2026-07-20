#include "termin/platform/offscreen_render_surface.hpp"

#include <cassert>
#include <memory>
#include <span>
#include <vector>

#include "render/tc_display.h"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"

namespace {

class TestRenderDevice final : public tgfx::IRenderDevice {
public:
    tgfx::BackendType backend_type() const override { return tgfx::BackendType::Null; }
    tgfx::BackendCapabilities capabilities() const override { return {}; }
    void wait_idle() override {}

    tgfx::BufferHandle create_buffer(const tgfx::BufferDesc&) override { return {}; }
    tgfx::TextureHandle create_texture(const tgfx::TextureDesc& desc) override {
        created.push_back(desc);
        return tgfx::TextureHandle{next_texture_id++};
    }
    tgfx::SamplerHandle create_sampler(const tgfx::SamplerDesc&) override { return {}; }
    tgfx::ShaderHandle create_shader(const tgfx::ShaderDesc&) override { return {}; }
    tgfx::PipelineHandle create_pipeline(const tgfx::PipelineDesc&) override { return {}; }
    tgfx::ResourceSetHandle create_bound_resource_set(
        const tgfx::BoundResourceSetDesc&) override { return {}; }

    void destroy(tgfx::BufferHandle) override {}
    void destroy(tgfx::TextureHandle texture) override { destroyed.push_back(texture); }
    void destroy(tgfx::SamplerHandle) override {}
    void destroy(tgfx::ShaderHandle) override {}
    void destroy(tgfx::PipelineHandle) override {}
    void destroy(tgfx::ResourceSetHandle) override {}

    void upload_buffer(tgfx::BufferHandle, std::span<const uint8_t>, uint64_t = 0) override {}
    void upload_texture(tgfx::TextureHandle, std::span<const uint8_t>, uint32_t = 0) override {}
    void upload_texture_region(
        tgfx::TextureHandle, uint32_t, uint32_t, uint32_t, uint32_t,
        std::span<const uint8_t>, uint32_t = 0) override {}
    void read_buffer(tgfx::BufferHandle, std::span<uint8_t>, uint64_t = 0) override {}
    tgfx::TextureDesc texture_desc(tgfx::TextureHandle) const override { return {}; }
    std::unique_ptr<tgfx::ICommandList> create_command_list(
        tgfx::QueueType = tgfx::QueueType::Graphics) override { return {}; }
    void submit(tgfx::ICommandList&) override {}
    void present() override {}

    std::vector<tgfx::TextureDesc> created;
    std::vector<tgfx::TextureHandle> destroyed;

private:
    uint32_t next_texture_id = 1;
};

} // namespace

int main() {
    tc_display_pool_init();
    TestRenderDevice device;
    tc_display_handle display = termin::create_offscreen_display(
        &device, 320, 200, "offscreen-lifecycle");
    assert(tc_display_handle_valid(display));
    assert(device.created.size() == 2u);
    assert(tc_display_get_color_texture_id(display) != 0u);
    assert(tc_display_get_graphics_domain_key(display) ==
           reinterpret_cast<uintptr_t>(&device));

    assert(tc_display_resize(display, 640, 360));
    assert(device.created.size() == 4u);
    assert(device.destroyed.size() == 2u);

    // Explicit display destruction semantically releases both current GPU
    // textures while the device is still alive, then frees surface storage.
    assert(tc_display_free(display));
    assert(device.destroyed.size() == 4u);
    assert(!tc_display_free(display));
    assert(device.destroyed.size() == 4u);
    tc_display_pool_shutdown();
    return 0;
}
