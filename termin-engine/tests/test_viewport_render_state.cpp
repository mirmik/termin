#include "guard_main.h"

#include <memory>
#include <span>
#include <vector>

#include <termin/render/viewport_render_state.hpp>

namespace {

class ViewportTestDevice final : public tgfx::IRenderDevice {
public:
    tgfx::BackendType backend_type() const override { return tgfx::BackendType::Null; }
    tgfx::BackendCapabilities capabilities() const override { return {}; }
    void wait_idle() override {}

    tgfx::BufferHandle create_buffer(const tgfx::BufferDesc&) override { return {}; }
    tgfx::TextureHandle create_texture(const tgfx::TextureDesc& desc) override {
        created_descriptions.push_back(desc);
        return tgfx::TextureHandle{next_texture_id_++};
    }
    tgfx::SamplerHandle create_sampler(const tgfx::SamplerDesc&) override { return {}; }
    tgfx::ShaderHandle create_shader(const tgfx::ShaderDesc&) override { return {}; }
    tgfx::PipelineHandle create_pipeline(const tgfx::PipelineDesc&) override { return {}; }
    tgfx::ResourceSetHandle create_bound_resource_set(const tgfx::BoundResourceSetDesc&) override { return {}; }

    void destroy(tgfx::BufferHandle) override {}
    void destroy(tgfx::TextureHandle texture) override { destroyed_textures.push_back(texture); }
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

    std::vector<tgfx::TextureDesc> created_descriptions;
    std::vector<tgfx::TextureHandle> destroyed_textures;

private:
    uint32_t next_texture_id_ = 1;
};

} // namespace

TEST_CASE("ViewportRenderState recreates and releases its textures exactly once") {
    ViewportTestDevice first_device;
    ViewportTestDevice second_device;

    termin::ViewportRenderState state;
    state.ensure_output_textures(first_device, 640, 480);
    REQUIRE(state.has_output());
    REQUIRE_EQ(first_device.created_descriptions.size(), 2u);
    CHECK_EQ(first_device.created_descriptions[0].width, 640u);
    CHECK_EQ(first_device.created_descriptions[1].height, 480u);

    state.ensure_output_textures(first_device, 640, 480);
    CHECK_EQ(first_device.created_descriptions.size(), 2u);

    state.ensure_output_textures(first_device, 800, 600);
    REQUIRE_EQ(first_device.destroyed_textures.size(), 2u);
    REQUIRE_EQ(first_device.created_descriptions.size(), 4u);

    termin::ViewportRenderState moved = std::move(state);
    CHECK_FALSE(state.has_output());
    moved.ensure_output_textures(second_device, 800, 600);
    CHECK_EQ(first_device.destroyed_textures.size(), 4u);
    CHECK_EQ(second_device.created_descriptions.size(), 2u);

    moved.clear_all();
    CHECK_EQ(second_device.destroyed_textures.size(), 2u);
    CHECK_FALSE(moved.has_output());
}

TEST_CASE("ViewportRenderState safely transitions from a zero-sized output") {
    ViewportTestDevice device;

    {
        termin::ViewportRenderState state;
        state.ensure_output_textures(device, 0, 0);
        REQUIRE(state.has_output());
        REQUIRE_EQ(device.created_descriptions.size(), 2u);
        CHECK_EQ(device.created_descriptions[0].width, 0u);
        CHECK_EQ(device.created_descriptions[1].height, 0u);

        state.ensure_output_textures(device, 320, 240);
        CHECK_EQ(device.destroyed_textures.size(), 2u);
    }

    CHECK_EQ(device.destroyed_textures.size(), 4u);
}

GUARD_TEST_MAIN();
