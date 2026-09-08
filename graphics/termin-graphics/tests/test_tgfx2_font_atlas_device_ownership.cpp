#include "guard_main.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <span>
#include <type_traits>
#include <vector>

#include <tgfx2/font_atlas.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>

#ifndef TGFX2_TEST_FONT_PATH
#error "TGFX2_TEST_FONT_PATH must point at a deterministic test TTF"
#endif

namespace {

    struct TextureEvent {
        tgfx::TextureHandle handle;
        std::size_t byte_count = 0;
    };

    struct DeviceRecords {
        std::vector<tgfx::TextureDesc> created;
        std::vector<TextureEvent> uploaded;
        std::vector<tgfx::TextureHandle> destroyed;
    };

    class RecordingDevice final : public tgfx::IRenderDevice {
    public:
        explicit RecordingDevice(DeviceRecords& records)
            : records_(records) {}

        tgfx::BackendType backend_type() const override {
            return tgfx::BackendType::Null;
        }
        tgfx::BackendCapabilities capabilities() const override {
            return {};
        }
        void wait_idle() override {}

        tgfx::BufferHandle create_buffer(const tgfx::BufferDesc&) override {
            return {};
        }
        tgfx::TextureHandle create_texture(const tgfx::TextureDesc& desc) override {
            records_.created.push_back(desc);
            return tgfx::TextureHandle{next_texture_id_++};
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
        void destroy(tgfx::TextureHandle handle) override {
            records_.destroyed.push_back(handle);
        }
        void destroy(tgfx::SamplerHandle) override {}
        void destroy(tgfx::ShaderHandle) override {}
        void destroy(tgfx::PipelineHandle) override {}
        void destroy(tgfx::ResourceSetHandle) override {}

        void upload_buffer(tgfx::BufferHandle, std::span<const uint8_t>, uint64_t = 0) override {}
        void upload_texture(tgfx::TextureHandle dst, std::span<const uint8_t> data, uint32_t = 0) override {
            records_.uploaded.push_back({dst, data.size()});
        }
        void upload_texture_region(tgfx::TextureHandle,
                                   uint32_t,
                                   uint32_t,
                                   uint32_t,
                                   uint32_t,
                                   std::span<const uint8_t>,
                                   uint32_t = 0) override {}
        void read_buffer(tgfx::BufferHandle, std::span<uint8_t>, uint64_t = 0) override {}

        tgfx::TextureDesc texture_desc(tgfx::TextureHandle) const override {
            return {};
        }
        std::unique_ptr<tgfx::ICommandList> create_command_list(tgfx::QueueType = tgfx::QueueType::Graphics) override {
            return {};
        }
        void submit(tgfx::ICommandList&) override {}
        void present() override {}

    private:
        DeviceRecords& records_;
        uint32_t next_texture_id_ = 1;
    };

    static_assert(!std::is_copy_constructible_v<RecordingDevice>);
    static_assert(!std::is_move_constructible_v<RecordingDevice>);

} // namespace

TEST_CASE("FontAtlas invalidates both representations before switching isolated devices") {
    DeviceRecords first_records;
    DeviceRecords second_records;
    RecordingDevice first(first_records);
    RecordingDevice second(second_records);
    tgfx::PipelineCache first_cache(first);
    tgfx::PipelineCache second_cache(second);
    tgfx::RenderContext2 first_context(first, first_cache);
    tgfx::RenderContext2 second_context(second, second_cache);
    tgfx::FontAtlas font(TGFX2_TEST_FONT_PATH, 14, 512, 512);

    const tgfx::TextureHandle first_bitmap = font.ensure_texture(&first_context);
    REQUIRE_EQ(first_bitmap.id, 1u);
    REQUIRE_EQ(first_records.uploaded.size(), 1u);
    CHECK_EQ(first_records.uploaded[0].handle.id, 1u);
    CHECK_EQ(first_records.uploaded[0].byte_count, 512u * 512u);

    const tgfx::TextureHandle second_sdf = font.sdf_atlas_texture(&second_context);
    REQUIRE_EQ(second_sdf.id, 1u);
    REQUIRE_EQ(first_records.destroyed.size(), 1u);
    CHECK_EQ(first_records.destroyed[0].id, 1u);
    REQUIRE_EQ(second_records.uploaded.size(), 1u);
    CHECK_EQ(second_records.uploaded[0].handle.id, 1u);
    CHECK_EQ(second_records.uploaded[0].byte_count,
             static_cast<std::size_t>(tgfx::FontAtlas::kSdfAtlasDim) * tgfx::FontAtlas::kSdfAtlasDim);

    // This path used to upload the stale bitmap handle (also numeric id 1)
    // through the second device before ensure_texture performed an owner check.
    font.ensure_glyphs("\xD0\x96", 14.0f, &first_context); // Cyrillic capital Zhe, not preloaded.
    REQUIRE(font.get_glyph(0x0416u, 14.0f).has_value());
    CHECK_EQ(first_records.uploaded.size(), 1u);
    REQUIRE_EQ(second_records.destroyed.size(), 1u);
    CHECK_EQ(second_records.destroyed[0].id, 1u);

    const tgfx::TextureHandle replacement_bitmap = font.ensure_texture(&first_context);
    REQUIRE_EQ(replacement_bitmap.id, 2u);
    REQUIRE_EQ(first_records.uploaded.size(), 2u);
    CHECK_EQ(first_records.uploaded[1].handle.id, 2u);
    CHECK_EQ(first_records.uploaded[1].byte_count, 512u * 512u);
    CHECK_EQ(second_records.uploaded.size(), 1u);

    font.release_gpu();
    REQUIRE_EQ(first_records.destroyed.size(), 2u);
    CHECK_EQ(first_records.destroyed[1].id, 2u);
}

TEST_CASE("FontAtlas release destroys bitmap and SDF textures on a live isolated device") {
    DeviceRecords records;
    RecordingDevice device(records);
    tgfx::PipelineCache cache(device);
    tgfx::RenderContext2 context(device, cache);
    tgfx::FontAtlas font(TGFX2_TEST_FONT_PATH, 14, 512, 512);

    REQUIRE_EQ(font.ensure_texture(&context).id, 1u);
    REQUIRE_EQ(font.sdf_atlas_texture(&context).id, 2u);
    REQUIRE_EQ(records.uploaded.size(), 2u);

    font.release_gpu();
    REQUIRE_EQ(records.destroyed.size(), 2u);
    CHECK_EQ(records.destroyed[0].id, 1u);
    CHECK_EQ(records.destroyed[1].id, 2u);
}

TEST_CASE("FontAtlas drops stale handles after an isolated device is destroyed") {
    DeviceRecords dead_records;
    tgfx::FontAtlas font(TGFX2_TEST_FONT_PATH, 14, 512, 512);

    {
        auto device = std::make_unique<RecordingDevice>(dead_records);
        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 context(*device, cache);
        REQUIRE_EQ(font.ensure_texture(&context).id, 1u);
    }

    font.release_gpu();
    CHECK(dead_records.destroyed.empty());

    DeviceRecords replacement_records;
    RecordingDevice replacement(replacement_records);
    tgfx::PipelineCache replacement_cache(replacement);
    tgfx::RenderContext2 replacement_context(replacement, replacement_cache);
    REQUIRE_EQ(font.ensure_texture(&replacement_context).id, 1u);
    REQUIRE_EQ(replacement_records.uploaded.size(), 1u);
    CHECK_EQ(replacement_records.uploaded[0].handle.id, 1u);

    font.release_gpu();
    REQUIRE_EQ(replacement_records.destroyed.size(), 1u);
    CHECK_EQ(replacement_records.destroyed[0].id, 1u);
}
