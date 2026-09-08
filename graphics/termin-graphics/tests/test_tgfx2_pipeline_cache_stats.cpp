#include "guard_main.h"

#include <memory>
#include <cstring>
#include <span>
#include <unordered_map>
#include <utility>
#include <vector>

#include <tgfx2/i_render_device.hpp>
#include <tgfx2/canvas2d_renderer.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/shader_artifact_resolver.hpp>
#include <tgfx2/texture_pool.hpp>

extern "C" {
#include <tgfx/resources/tc_shader.h>
#include <tgfx/resources/tc_shader_registry.h>
}

namespace {

    class RecordingCommandList final : public tgfx::ICommandList {
    public:
        void begin() override {
            ++begin_count;
        }
        void end() override {
            ++end_count;
        }
        void begin_render_pass(const tgfx::RenderPassDesc& pass) override {
            ++begin_render_pass_count;
            last_render_pass = pass;
        }
        void end_render_pass() override {
            ++end_render_pass_count;
        }
        void framebuffer_local_barrier() override {
            ++framebuffer_local_barrier_count;
        }
        void bind_pipeline(tgfx::PipelineHandle pipeline) override {
            current_pipeline = pipeline;
        }
        void
        bind_resource_set(tgfx::ResourceSetHandle, uint32_t = 0, const uint32_t* = nullptr, uint32_t = 0) override {}
        void set_push_constants(const void*, uint32_t) override {}
        void bind_vertex_buffer(uint32_t, tgfx::BufferHandle, uint64_t = 0) override {}
        void bind_index_buffer(tgfx::BufferHandle, tgfx::IndexType, uint64_t = 0) override {}
        void draw(uint32_t, uint32_t = 0) override {
            draw_pipelines.push_back(current_pipeline);
        }
        void draw_instanced(uint32_t, uint32_t, uint32_t = 0, uint32_t = 0) override {
            draw_pipelines.push_back(current_pipeline);
        }
        void draw_indexed(uint32_t, uint32_t = 0, int32_t = 0) override {
            draw_pipelines.push_back(current_pipeline);
        }
        void draw_indexed_instanced(uint32_t, uint32_t, uint32_t = 0, int32_t = 0, uint32_t = 0) override {
            draw_pipelines.push_back(current_pipeline);
        }
        void dispatch(uint32_t, uint32_t, uint32_t) override {}
        void copy_buffer(tgfx::BufferHandle, tgfx::BufferHandle, uint64_t, uint64_t = 0, uint64_t = 0) override {}
        void copy_texture(tgfx::TextureHandle, tgfx::TextureHandle) override {}
        void set_viewport(int, int, int, int) override {}
        void set_scissor(int, int, int, int) override {}

        uint32_t begin_count = 0;
        uint32_t end_count = 0;
        uint32_t begin_render_pass_count = 0;
        uint32_t end_render_pass_count = 0;
        uint32_t framebuffer_local_barrier_count = 0;
        tgfx::RenderPassDesc last_render_pass;
        tgfx::PipelineHandle current_pipeline;
        std::vector<tgfx::PipelineHandle> draw_pipelines;
    };

    class PipelineCacheStatsDevice final : public tgfx::IRenderDevice {
    public:
        tgfx::BackendType backend_type() const override {
            return tgfx::BackendType::OpenGL;
        }

        tgfx::BackendCapabilities capabilities() const override {
            return {};
        }

        void wait_idle() override {}

        tgfx::BufferHandle create_buffer(const tgfx::BufferDesc&) override {
            return tgfx::BufferHandle{next_buffer_id_++};
        }

        tgfx::TextureHandle create_texture(const tgfx::TextureDesc& desc) override {
            ++create_texture_count;
            if (texture_failures_remaining > 0) {
                --texture_failures_remaining;
                return {};
            }
            const tgfx::TextureHandle handle{next_texture_id_++};
            texture_descs_[handle.id] = desc;
            return handle;
        }

        tgfx::SamplerHandle create_sampler(const tgfx::SamplerDesc&) override {
            return tgfx::SamplerHandle{next_sampler_id_++};
        }

        tgfx::ShaderHandle create_shader(const tgfx::ShaderDesc&) override {
            return {};
        }

        tgfx::PipelineHandle create_pipeline(const tgfx::PipelineDesc& desc) override {
            ++create_pipeline_count;
            created_pipeline_descs.push_back(desc);
            if (pipeline_failures_remaining > 0) {
                --pipeline_failures_remaining;
                return {};
            }
            return tgfx::PipelineHandle{next_pipeline_id_++};
        }

        tgfx::ResourceSetHandle create_bound_resource_set(const tgfx::BoundResourceSetDesc&) override {
            return {};
        }

        void destroy(tgfx::BufferHandle) override {}
        void destroy(tgfx::TextureHandle handle) override {
            destroyed_textures.push_back(handle);
            texture_descs_.erase(handle.id);
        }
        void destroy(tgfx::SamplerHandle) override {}
        void destroy(tgfx::ShaderHandle) override {}
        void destroy(tgfx::PipelineHandle handle) override {
            destroyed_pipelines.push_back(handle);
        }
        void destroy(tgfx::ResourceSetHandle) override {}

        void upload_buffer(tgfx::BufferHandle, std::span<const uint8_t> bytes, uint64_t = 0) override {
            uniform_uploads.emplace_back(bytes.begin(), bytes.end());
        }
        std::vector<std::vector<uint8_t>> uniform_uploads;
        void upload_texture(tgfx::TextureHandle, std::span<const uint8_t>, uint32_t = 0) override {}
        void upload_texture_region(tgfx::TextureHandle,
                                   uint32_t,
                                   uint32_t,
                                   uint32_t,
                                   uint32_t,
                                   std::span<const uint8_t>,
                                   uint32_t = 0) override {}
        void read_buffer(tgfx::BufferHandle, std::span<uint8_t>, uint64_t = 0) override {}

        tgfx::TextureDesc texture_desc(tgfx::TextureHandle handle) const override {
            const auto it = texture_descs_.find(handle.id);
            return it == texture_descs_.end() ? tgfx::TextureDesc{} : it->second;
        }

        std::unique_ptr<tgfx::ICommandList> create_command_list(tgfx::QueueType = tgfx::QueueType::Graphics) override {
            auto command_list = std::make_unique<RecordingCommandList>();
            last_command_list = command_list.get();
            return command_list;
        }

        void submit(tgfx::ICommandList& commands) override {
            auto* recording = dynamic_cast<RecordingCommandList*>(&commands);
            if (!recording)
                return;
            submitted_pipelines.insert(submitted_pipelines.end(),
                                       recording->draw_pipelines.begin(),
                                       recording->draw_pipelines.end());
        }
        void present() override {}

        bool ensure_tc_shader(tc_shader* shader,
                              tgfx::ShaderHandle* out_vertex,
                              tgfx::ShaderHandle* out_fragment) override {
            if (!shader || !out_fragment)
                return false;
            const uint64_t artifact_revision = shader_artifact_revision();
            auto cached = shader_cache_.find(shader->pool_index);
            if (cached == shader_cache_.end() || cached->second.source_version != shader->version ||
                cached->second.artifact_revision != artifact_revision) {
                if (cached != shader_cache_.end()) {
                    notify_shader_handles_replaced();
                    shader_cache_.erase(cached);
                }
                CachedShader replacement;
                replacement.source_version = shader->version;
                replacement.artifact_revision = artifact_revision;
                if (shader->vertex_source && shader->vertex_source[0] != '\0')
                    replacement.vertex = tgfx::ShaderHandle{next_shader_id_++};
                replacement.fragment = tgfx::ShaderHandle{next_shader_id_++};
                cached = shader_cache_.emplace(shader->pool_index, replacement).first;
            }
            if (out_vertex)
                *out_vertex = cached->second.vertex;
            *out_fragment = cached->second.fragment;
            return true;
        }

        int texture_failures_remaining = 0;
        int pipeline_failures_remaining = 0;
        uint32_t create_texture_count = 0;
        uint32_t create_pipeline_count = 0;
        std::vector<tgfx::PipelineDesc> created_pipeline_descs;
        std::vector<tgfx::TextureHandle> destroyed_textures;
        std::vector<tgfx::PipelineHandle> destroyed_pipelines;
        std::vector<tgfx::PipelineHandle> submitted_pipelines;
        RecordingCommandList* last_command_list = nullptr;

    private:
        struct CachedShader {
            tgfx::ShaderHandle vertex;
            tgfx::ShaderHandle fragment;
            uint32_t source_version = 0;
            uint64_t artifact_revision = 0;
        };

        uint32_t next_buffer_id_ = 1;
        uint32_t next_sampler_id_ = 1;
        uint32_t next_shader_id_ = 100;
        uint32_t next_texture_id_ = 1;
        uint32_t next_pipeline_id_ = 1;
        std::unordered_map<uint32_t, tgfx::TextureDesc> texture_descs_;
        std::unordered_map<uint32_t, CachedShader> shader_cache_;
    };

    tgfx::VertexLayoutDesc make_layout(uint32_t stride, const char* semantic) {
        tgfx::VertexBufferLayout layout;
        layout.stride = stride;
        layout.attributes.push_back({
            0,
            tgfx::VertexFormat::Float3,
            0,
            semantic,
        });
        return tgfx::make_vertex_layout_desc(layout);
    }

} // namespace

TEST_CASE("PipelineCache exposes backend-neutral hit miss and layout stats") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};
    std::vector<tgfx::VertexLayoutDesc> position_layouts = {
        make_layout(12, "position"),
    };
    key.vertex_layouts = position_layouts;
    key.vertex_layouts_hash = 0x1111;

    tgfx::PipelineHandle first = cache.get(key);
    CHECK(first.id == 1u);

    tgfx::PipelineCacheStats stats = cache.stats();
    CHECK(stats.hit_count == 0u);
    CHECK(stats.miss_count == 1u);
    CHECK(stats.create_pipeline_count == 1u);
    CHECK(stats.cached_pipeline_count == 1u);
    CHECK(stats.unique_vertex_layout_signature_count == 1u);
    REQUIRE(stats.vertex_layout_signature_hashes.size() == 1u);
    CHECK(stats.vertex_layout_signature_hashes[0] == 0x1111u);

    tgfx::PipelineHandle second = cache.get(key);
    CHECK(second == first);

    stats = cache.stats();
    CHECK(stats.hit_count == 1u);
    CHECK(stats.miss_count == 1u);
    CHECK(stats.create_pipeline_count == 1u);
    CHECK(stats.cached_pipeline_count == 1u);

    key.depth_stencil.depth_test = false;
    tgfx::PipelineHandle third = cache.get(key);
    CHECK(third.id == 2u);

    stats = cache.stats();
    CHECK(stats.hit_count == 1u);
    CHECK(stats.miss_count == 2u);
    CHECK(stats.create_pipeline_count == 2u);
    CHECK(stats.cached_pipeline_count == 2u);
    CHECK(stats.unique_vertex_layout_signature_count == 1u);

    std::vector<tgfx::VertexLayoutDesc> normal_layouts = {
        make_layout(24, "normal"),
    };
    key.vertex_layouts = normal_layouts;
    key.vertex_layouts_hash = 0x2222;
    tgfx::PipelineHandle fourth = cache.get(key);
    CHECK(fourth.id == 3u);

    stats = cache.stats();
    CHECK(stats.miss_count == 3u);
    CHECK(stats.create_pipeline_count == 3u);
    CHECK(stats.cached_pipeline_count == 3u);
    CHECK(stats.unique_vertex_layout_signature_count == 2u);
    REQUIRE(stats.vertex_layout_signature_hashes.size() == 2u);
    CHECK(stats.vertex_layout_signature_hashes[0] == 0x1111u);
    CHECK(stats.vertex_layout_signature_hashes[1] == 0x2222u);
}

TEST_CASE("PipelineCache retries a failed creation instead of caching an invalid handle") {
    PipelineCacheStatsDevice device;
    device.pipeline_failures_remaining = 1;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};
    std::vector<tgfx::VertexLayoutDesc> position_layouts = {
        make_layout(12, "position"),
    };
    key.vertex_layouts = position_layouts;
    key.vertex_layouts_hash = 0x3333;

    CHECK_FALSE(cache.get(key));
    CHECK(cache.size() == 0u);
    CHECK(device.create_pipeline_count == 1u);

    const tgfx::PipelineHandle recovered = cache.get(key);
    CHECK(recovered.id == 1u);
    CHECK(cache.size() == 1u);
    CHECK(device.create_pipeline_count == 2u);
    CHECK(cache.get(key) == recovered);
    CHECK(device.create_pipeline_count == 2u);
}

TEST_CASE("PipelineCache treats color resolve topology as Vulkan-compatible identity") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};
    key.color_format_count = 1;
    key.color_formats[0] = tgfx::PixelFormat::RGBA16F;
    key.sample_count = 4;

    const tgfx::PipelineHandle without_resolve = cache.get(key);
    key.color_resolve_mask = 1;
    const tgfx::PipelineHandle with_resolve = cache.get(key);

    CHECK(without_resolve);
    CHECK(with_resolve);
    CHECK(without_resolve != with_resolve);
    REQUIRE(device.created_pipeline_descs.size() == 2u);
    CHECK(device.created_pipeline_descs[0].color_resolve_mask == 0u);
    CHECK(device.created_pipeline_descs[1].color_resolve_mask == 1u);
}

TEST_CASE("PipelineCache keeps indexed strip formats in pipeline identity") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};
    key.topology = tgfx::PrimitiveTopology::TriangleStrip;

    key.strip_index_format = tgfx::StripIndexFormat::Uint16;
    const tgfx::PipelineHandle uint16_pipeline = cache.get(key);
    key.strip_index_format = tgfx::StripIndexFormat::Uint32;
    const tgfx::PipelineHandle uint32_pipeline = cache.get(key);
    key.strip_index_format = tgfx::StripIndexFormat::Undefined;
    const tgfx::PipelineHandle nonindexed_pipeline = cache.get(key);

    CHECK(uint16_pipeline);
    CHECK(uint32_pipeline);
    CHECK(nonindexed_pipeline);
    CHECK(uint16_pipeline != uint32_pipeline);
    CHECK(uint16_pipeline != nonindexed_pipeline);
    CHECK(uint32_pipeline != nonindexed_pipeline);
    REQUIRE(device.created_pipeline_descs.size() == 3u);
    CHECK(device.created_pipeline_descs[0].strip_index_format == tgfx::StripIndexFormat::Uint16);
    CHECK(device.created_pipeline_descs[1].strip_index_format == tgfx::StripIndexFormat::Uint32);
    CHECK(device.created_pipeline_descs[2].strip_index_format == tgfx::StripIndexFormat::Undefined);
}

TEST_CASE("live Canvas2D renderers reacquire shaders and retire pipelines after shader reloads") {
    {
        PipelineCacheStatsDevice device;
        tgfx::PipelineCache cache(device);
        tgfx::RenderContext2 context(device, cache);
        tgfx::Canvas2DRenderer first;
        tgfx::Canvas2DRenderer second;

        tgfx::TextureDesc color_desc;
        color_desc.width = 32;
        color_desc.height = 32;
        color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        color_desc.usage = tgfx::TextureUsage::ColorAttachment;
        const tgfx::TextureHandle color = device.create_texture(color_desc);

        const auto render_both = [&]() {
            tgfx::RenderPassDesc pass;
            pass.colors.resize(1);
            pass.colors[0].texture = color;
            context.begin_frame();
            REQUIRE(context.begin_pass(pass));
            first.begin(context, 32, 32);
            first.draw_rect(1.0f, 1.0f, 8.0f, 8.0f, tgfx::CanvasSrgbColor::white());
            first.end();
            second.begin(context, 32, 32);
            second.draw_rect(12.0f, 1.0f, 8.0f, 8.0f, tgfx::CanvasSrgbColor::white());
            second.end();
            context.end_pass();
            context.end_frame();
        };

        render_both();
        REQUIRE(device.submitted_pipelines.size() == 2u);
        const tgfx::PipelineHandle initial_pipeline = device.submitted_pipelines[0];
        CHECK(device.submitted_pipelines[1] == initial_pipeline);
        REQUIRE(device.created_pipeline_descs.size() == 1u);
        const tgfx::ShaderHandle initial_vertex = device.created_pipeline_descs[0].vertex_shader;
        const tgfx::ShaderHandle initial_fragment = device.created_pipeline_descs[0].fragment_shader;

        termin::ShaderArtifactResolver replacement_resolver;
        device.configure_shader_artifacts(replacement_resolver);
        device.submitted_pipelines.clear();
        render_both();

        REQUIRE(device.submitted_pipelines.size() == 2u);
        const tgfx::PipelineHandle replacement_pipeline = device.submitted_pipelines[0];
        CHECK(replacement_pipeline != initial_pipeline);
        CHECK(device.submitted_pipelines[1] == replacement_pipeline);
        REQUIRE(device.created_pipeline_descs.size() == 2u);
        CHECK(device.created_pipeline_descs[1].vertex_shader != initial_vertex);
        CHECK(device.created_pipeline_descs[1].fragment_shader != initial_fragment);
        REQUIRE(device.destroyed_pipelines.size() == 1u);
        CHECK(device.destroyed_pipelines[0] == initial_pipeline);
        CHECK(cache.size() == 1u);

        const tc_shader_handle solid_handle = tc_shader_find("termin-engine-canvas2d-solid");
        tc_shader* solid_shader = tc_shader_get(solid_handle);
        REQUIRE(solid_shader != nullptr);
        struct ShaderVersionRestore {
            tc_shader* shader;
            uint32_t version;
            ~ShaderVersionRestore() {
                shader->version = version;
            }
        } restore_version{solid_shader, solid_shader->version};
        ++solid_shader->version;

        device.submitted_pipelines.clear();
        render_both();
        REQUIRE(device.submitted_pipelines.size() == 2u);
        const tgfx::PipelineHandle source_reload_pipeline = device.submitted_pipelines[0];
        CHECK(source_reload_pipeline != replacement_pipeline);
        CHECK(device.submitted_pipelines[1] == source_reload_pipeline);
        REQUIRE(device.created_pipeline_descs.size() == 3u);
        CHECK(device.created_pipeline_descs[2].vertex_shader != device.created_pipeline_descs[1].vertex_shader);
        CHECK(device.created_pipeline_descs[2].fragment_shader != device.created_pipeline_descs[1].fragment_shader);
        REQUIRE(device.destroyed_pipelines.size() == 2u);
        CHECK(device.destroyed_pipelines[1] == replacement_pipeline);
        CHECK(cache.size() == 1u);
    }
}

TEST_CASE("PipelineCache identity includes complete raster state") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};
    const tgfx::RasterState baseline = key.raster;

    const tgfx::PipelineHandle initial = cache.get(key);
    REQUIRE(initial);
    CHECK(cache.get(key) == initial);

    key.raster.polygon_mode = tgfx::PolygonMode::Line;
    CHECK(cache.get(key) != initial);

    key.raster = baseline;
    key.raster.depth_bias_enabled = true;
    const tgfx::PipelineHandle enabled = cache.get(key);
    CHECK(enabled);

    key.raster.depth_bias_constant = 2.0f;
    const tgfx::PipelineHandle constant = cache.get(key);
    CHECK(constant);
    CHECK(constant != enabled);

    key.raster.depth_bias_slope = 1.5f;
    const tgfx::PipelineHandle slope = cache.get(key);
    CHECK(slope);
    CHECK(slope != constant);

    key.raster.depth_bias_clamp = 0.25f;
    const tgfx::PipelineHandle clamp = cache.get(key);
    CHECK(clamp);
    CHECK(clamp != slope);

    CHECK(device.create_pipeline_count == 6u);
    CHECK(cache.size() == 6u);
    CHECK(cache.get(key) == clamp);
    CHECK(device.create_pipeline_count == 6u);
}

TEST_CASE("PipelineCache rejects missing required shaders before backend creation") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    CHECK_FALSE(cache.get(key));

    key.vertex_shader = {};
    key.fragment_shader = tgfx::ShaderHandle{2};
    CHECK_FALSE(cache.get(key));

    CHECK(device.create_pipeline_count == 0u);
    CHECK(cache.size() == 0u);
    const tgfx::PipelineCacheStats stats = cache.stats();
    CHECK(stats.hit_count == 0u);
    CHECK(stats.miss_count == 0u);
    CHECK(stats.create_pipeline_count == 0u);
}

TEST_CASE("PipelineCache owns layouts after a lookup view expires") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};
    key.vertex_layouts_hash = 0x4444;
    {
        std::vector<tgfx::VertexLayoutDesc> transient_layouts = {
            make_layout(12, "position"),
        };
        key.vertex_layouts = transient_layouts;
        CHECK(cache.get(key).id == 1u);
    }

    std::vector<tgfx::VertexLayoutDesc> equivalent_layouts = {
        make_layout(12, "position"),
    };
    key.vertex_layouts = equivalent_layouts;
    CHECK(cache.get(key).id == 1u);
    CHECK(device.create_pipeline_count == 1u);
}

TEST_CASE("PipelineCache compares complete layouts when lookup hashes collide") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};
    key.vertex_layouts_hash = 0x5555;

    std::vector<tgfx::VertexLayoutDesc> position_layouts = {
        make_layout(12, "position"),
    };
    key.vertex_layouts = position_layouts;
    const tgfx::PipelineHandle position_pipeline = cache.get(key);
    CHECK(position_pipeline.id == 1u);

    std::vector<tgfx::VertexLayoutDesc> normal_layouts = {
        make_layout(24, "normal"),
    };
    key.vertex_layouts = normal_layouts;
    const tgfx::PipelineHandle normal_pipeline = cache.get(key);
    CHECK(normal_pipeline.id == 2u);
    CHECK(cache.get(key) == normal_pipeline);
    CHECK(device.create_pipeline_count == 2u);
    CHECK(cache.size() == 2u);
}

TEST_CASE("PipelineCache identity preserves ordered MRT color formats") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};
    key.color_format_count = 3;
    key.color_formats[0] = tgfx::PixelFormat::RGBA16F;
    key.color_formats[1] = tgfx::PixelFormat::RG16F;
    key.color_formats[2] = tgfx::PixelFormat::RGBA8_UNorm;

    const tgfx::PipelineHandle first = cache.get(key);
    REQUIRE(first);
    REQUIRE(device.created_pipeline_descs.size() == 1u);
    const std::vector<tgfx::PixelFormat> expected_formats = {
        tgfx::PixelFormat::RGBA16F,
        tgfx::PixelFormat::RG16F,
        tgfx::PixelFormat::RGBA8_UNorm,
    };
    CHECK(device.created_pipeline_descs[0].color_formats == expected_formats);

    CHECK(cache.get(key) == first);
    CHECK(device.create_pipeline_count == 1u);

    std::swap(key.color_formats[0], key.color_formats[1]);
    const tgfx::PipelineHandle reordered = cache.get(key);
    CHECK(reordered);
    CHECK(reordered != first);
    CHECK(device.create_pipeline_count == 2u);

    key.color_formats[3] = tgfx::PixelFormat::R32F;
    CHECK(cache.get(key) == reordered);
    CHECK(device.create_pipeline_count == 2u);

    key.color_format_count = 2;
    CHECK(cache.get(key));
    CHECK(device.create_pipeline_count == 3u);
}

TEST_CASE("PipelineCache keeps mono and multiview render-pass identities distinct") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};

    const tgfx::PipelineHandle mono = cache.get(key);
    REQUIRE(mono);
    REQUIRE(device.created_pipeline_descs.size() == 1u);
    CHECK(device.created_pipeline_descs[0].view_count == 1u);

    key.view_count = 2;
    const tgfx::PipelineHandle stereo = cache.get(key);
    REQUIRE(stereo);
    CHECK(stereo != mono);
    REQUIRE(device.created_pipeline_descs.size() == 2u);
    CHECK(device.created_pipeline_descs[1].view_count == 2u);

    CHECK(cache.get(key) == stereo);
    CHECK(device.create_pipeline_count == 2u);
}

TEST_CASE("PipelineCache rejects invalid MRT color format identity") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);

    tgfx::PipelineCacheLookupKey key;
    key.vertex_shader = tgfx::ShaderHandle{1};
    key.fragment_shader = tgfx::ShaderHandle{2};

    key.color_format_count = tgfx::TGFX2_MAX_COLOR_ATTACHMENTS + 1;
    CHECK_FALSE(cache.get(key));
    CHECK(device.create_pipeline_count == 0u);

    key.color_format_count = 1;
    key.color_formats[0] = tgfx::PixelFormat::Undefined;
    CHECK_FALSE(cache.get(key));
    CHECK(device.create_pipeline_count == 0u);
}

TEST_CASE("RenderContext2 forwards a validated ordered MRT attachment set") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);
    tgfx::RenderContext2 context(device, cache);

    tgfx::TextureDesc color_desc;
    color_desc.width = 64;
    color_desc.height = 32;
    color_desc.usage = tgfx::TextureUsage::ColorAttachment;

    color_desc.format = tgfx::PixelFormat::RGBA16F;
    const tgfx::TextureHandle color0 = device.create_texture(color_desc);
    color_desc.format = tgfx::PixelFormat::RG16F;
    const tgfx::TextureHandle color1 = device.create_texture(color_desc);
    color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
    const tgfx::TextureHandle color2 = device.create_texture(color_desc);

    tgfx::TextureDesc depth_desc;
    depth_desc.width = 64;
    depth_desc.height = 32;
    depth_desc.format = tgfx::PixelFormat::D32F;
    depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment;
    const tgfx::TextureHandle depth = device.create_texture(depth_desc);

    tgfx::RenderPassDesc pass;
    pass.colors.resize(3);
    pass.colors[0].texture = color0;
    pass.colors[1].texture = color1;
    pass.colors[2].texture = color2;
    pass.depth.texture = depth;
    pass.has_depth = true;

    context.begin_frame();
    REQUIRE(device.last_command_list != nullptr);
    CHECK(context.begin_pass(pass));
    REQUIRE(device.last_command_list->begin_render_pass_count == 1u);
    REQUIRE(device.last_command_list->last_render_pass.colors.size() == 3u);
    CHECK(device.last_command_list->last_render_pass.colors[0].texture == color0);
    CHECK(device.last_command_list->last_render_pass.colors[1].texture == color1);
    CHECK(device.last_command_list->last_render_pass.colors[2].texture == color2);
    CHECK(device.last_command_list->last_render_pass.depth.texture == depth);
    context.end_pass();
    context.end_frame();
}

TEST_CASE("RenderContext2 rejects incompatible MRT attachments before backend recording") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);
    tgfx::RenderContext2 context(device, cache);

    tgfx::TextureDesc desc;
    desc.width = 64;
    desc.height = 32;
    desc.format = tgfx::PixelFormat::RGBA16F;
    desc.usage = tgfx::TextureUsage::ColorAttachment;
    const tgfx::TextureHandle color0 = device.create_texture(desc);
    desc.width = 32;
    const tgfx::TextureHandle wrong_extent = device.create_texture(desc);

    tgfx::RenderPassDesc pass;
    pass.colors.resize(2);
    pass.colors[0].texture = color0;
    pass.colors[1].texture = wrong_extent;

    context.begin_frame();
    REQUIRE(device.last_command_list != nullptr);
    CHECK_FALSE(context.begin_pass(pass));
    CHECK(device.last_command_list->begin_render_pass_count == 0u);

    pass.colors[1].texture = color0;
    CHECK_FALSE(context.begin_pass(pass));
    CHECK(device.last_command_list->begin_render_pass_count == 0u);

    pass.colors.resize(device.capabilities().max_color_attachments + 1);
    for (tgfx::ColorAttachmentDesc& color : pass.colors) {
        color.texture = color0;
    }
    CHECK_FALSE(context.begin_pass(pass));
    CHECK(device.last_command_list->begin_render_pass_count == 0u);
    context.end_frame();
}

TEST_CASE("RenderContext2 validates and forwards single-sample color resolves") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);
    tgfx::RenderContext2 context(device, cache);

    tgfx::TextureDesc source_desc;
    source_desc.width = 64;
    source_desc.height = 32;
    source_desc.sample_count = 4;
    source_desc.format = tgfx::PixelFormat::RGBA16F;
    source_desc.usage = tgfx::TextureUsage::ColorAttachment;
    const tgfx::TextureHandle source = device.create_texture(source_desc);

    tgfx::TextureDesc resolve_desc = source_desc;
    resolve_desc.sample_count = 1;
    const tgfx::TextureHandle resolve = device.create_texture(resolve_desc);

    tgfx::RenderPassDesc pass;
    pass.colors.resize(1);
    pass.colors[0].texture = source;
    pass.colors[0].resolve_texture = resolve;

    context.begin_frame();
    REQUIRE(context.begin_pass(pass));
    REQUIRE(device.last_command_list->begin_render_pass_count == 1u);
    CHECK(device.last_command_list->last_render_pass.colors[0].resolve_texture == resolve);
    context.begin_logical_pass();
    CHECK(device.last_command_list->begin_render_pass_count == 1u);
    CHECK(device.last_command_list->end_render_pass_count == 0u);
    context.end_pass();

    resolve_desc.sample_count = 4;
    const tgfx::TextureHandle multisampled_destination = device.create_texture(resolve_desc);
    pass.colors[0].resolve_texture = multisampled_destination;
    CHECK_FALSE(context.begin_pass(pass));
    CHECK(device.last_command_list->begin_render_pass_count == 1u);
    context.end_frame();
}

TEST_CASE("RenderContext2 forwards framebuffer-local barriers inside an active pass") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);
    tgfx::RenderContext2 context(device, cache);

    tgfx::TextureDesc desc;
    desc.width = 64;
    desc.height = 32;
    desc.format = tgfx::PixelFormat::RGBA16F;
    desc.usage = tgfx::TextureUsage::ColorAttachment;
    const tgfx::TextureHandle color = device.create_texture(desc);

    tgfx::RenderPassDesc pass;
    pass.colors.resize(1);
    pass.colors[0].texture = color;

    context.begin_frame();
    REQUIRE(device.last_command_list != nullptr);
    REQUIRE(context.begin_pass(pass));
    context.framebuffer_local_barrier();
    CHECK(device.last_command_list->framebuffer_local_barrier_count == 1u);
    context.end_pass();
    context.end_frame();
}

TEST_CASE("texture pools retry failed allocations using the same key and descriptor") {
    PipelineCacheStatsDevice device;
    tgfx::TextureDesc texture_desc;
    texture_desc.width = 32;
    texture_desc.height = 16;
    texture_desc.usage = tgfx::TextureUsage::Sampled;

    tgfx::TexturePool textures;
    device.texture_failures_remaining = 1;
    CHECK_FALSE(textures.ensure(device, "color", texture_desc));
    CHECK_FALSE(textures.get("color"));
    CHECK(textures.ensure(device, "color", texture_desc));
    CHECK(textures.get("color"));
    CHECK(device.create_texture_count == 2u);

    tgfx::RenderTargetPool targets;
    tgfx::RenderTargetPoolDesc target_desc;
    target_desc.width = 32;
    target_desc.height = 16;
    target_desc.has_depth = true;
    device.texture_failures_remaining = 1;
    CHECK_FALSE(targets.ensure(device, "main", target_desc));
    CHECK_FALSE(targets.color("main"));
    CHECK(targets.ensure(device, "main", target_desc));
    CHECK(targets.color("main"));
    CHECK(targets.depth("main"));
    CHECK(device.create_texture_count == 5u);
}

TEST_CASE("render target pool borrows an external color while owning depth") {
    PipelineCacheStatsDevice device;
    tgfx::TextureDesc color_desc;
    color_desc.width = 32;
    color_desc.height = 16;
    color_desc.format = tgfx::PixelFormat::RGBA16F;
    color_desc.usage = tgfx::TextureUsage::ColorAttachment;
    const tgfx::TextureHandle external_color = device.create_texture(color_desc);

    tgfx::RenderTargetPoolDesc target_desc;
    target_desc.width = 32;
    target_desc.height = 16;
    target_desc.color_format = tgfx::PixelFormat::RGBA16F;
    target_desc.has_depth = true;

    tgfx::RenderTargetPool targets;
    REQUIRE(targets.ensure(device, "main", target_desc, external_color));
    CHECK(targets.color("main") == external_color);
    REQUIRE(targets.depth("main"));
    CHECK(device.create_texture_count == 2u);

    const tgfx::TextureHandle owned_depth = targets.depth("main");
    const tgfx::TextureHandle next_external_color = device.create_texture(color_desc);
    REQUIRE(targets.ensure(device, "main", target_desc, next_external_color));
    CHECK(targets.color("main") == next_external_color);
    CHECK(targets.depth("main") == owned_depth);
    CHECK(device.create_texture_count == 3u);

    targets.clear();
    CHECK(device.texture_desc(external_color).format == tgfx::PixelFormat::RGBA16F);
    CHECK(device.texture_desc(next_external_color).format == tgfx::PixelFormat::RGBA16F);
    REQUIRE(device.destroyed_textures.size() == 1u);
    CHECK(device.destroyed_textures[0] == owned_depth);
}

TEST_CASE("render target pool allocates only requested attachments") {
    PipelineCacheStatsDevice device;
    tgfx::RenderTargetPool targets;

    tgfx::RenderTargetPoolDesc color_only;
    color_only.width = 32;
    color_only.height = 16;
    color_only.has_depth = false;
    REQUIRE(targets.ensure(device, "color-only", color_only));
    CHECK(targets.color("color-only"));
    CHECK_FALSE(targets.depth("color-only"));
    CHECK(device.create_texture_count == 1u);

    tgfx::RenderTargetPoolDesc depth_only;
    depth_only.width = 32;
    depth_only.height = 16;
    depth_only.has_color = false;
    REQUIRE(targets.ensure(device, "depth-only", depth_only));
    CHECK_FALSE(targets.color("depth-only"));
    CHECK(targets.depth("depth-only"));
    CHECK(device.create_texture_count == 2u);

    tgfx::RenderTargetPoolDesc empty;
    empty.width = 32;
    empty.height = 16;
    empty.has_color = false;
    empty.has_depth = false;
    CHECK_FALSE(targets.ensure(device, "empty", empty));
    CHECK(device.create_texture_count == 2u);
}

TEST_CASE("texture pool moves release displaced ownership exactly once") {
    PipelineCacheStatsDevice first_device;
    PipelineCacheStatsDevice second_device;
    tgfx::TextureDesc desc;
    desc.width = 4;
    desc.height = 4;
    {
        tgfx::TexturePool destination;
        REQUIRE(destination.ensure(first_device, "old", desc));
        const auto displaced = destination.get("old");
        {
            tgfx::TexturePool source;
            REQUIRE(source.ensure(second_device, "new", desc));
            const auto moved = source.get("new");
            destination = std::move(source);
            REQUIRE(first_device.destroyed_textures.size() == 1u);
            CHECK(first_device.destroyed_textures[0] == displaced);
            CHECK(second_device.destroyed_textures.empty());
            CHECK(destination.get("new") == moved);
            CHECK_FALSE(source.get("new"));
            auto& same = destination;
            destination = std::move(same);
            CHECK(destination.get("new") == moved);
            CHECK(second_device.destroyed_textures.empty());
        }
        CHECK(second_device.destroyed_textures.empty());
        tgfx::TexturePool moved_again(std::move(destination));
        CHECK_FALSE(destination.get("new"));
        REQUIRE(moved_again.get("new"));
    }
    CHECK(first_device.destroyed_textures.size() == 1u);
    CHECK(second_device.destroyed_textures.size() == 1u);
}

TEST_CASE("render target pool moves preserve borrowed color and owned depth") {
    PipelineCacheStatsDevice device;
    tgfx::TextureDesc color_desc;
    color_desc.width = 4;
    color_desc.height = 4;
    const auto external = device.create_texture(color_desc);
    tgfx::RenderTargetPoolDesc desc;
    desc.width = 4;
    desc.height = 4;
    {
        tgfx::RenderTargetPool destination;
        REQUIRE(destination.ensure(device, "old", desc));
        {
            tgfx::RenderTargetPool source;
            REQUIRE(source.ensure(device, "new", desc, external));
            const auto depth = source.depth("new");
            destination = std::move(source);
            CHECK(device.destroyed_textures.size() == 2u);
            CHECK(destination.color("new") == external);
            CHECK(destination.depth("new") == depth);
            CHECK_FALSE(source.depth("new"));
            auto& same = destination;
            destination = std::move(same);
            CHECK(destination.depth("new") == depth);
            CHECK(device.destroyed_textures.size() == 2u);
        }
        tgfx::RenderTargetPool moved_again(std::move(destination));
        CHECK_FALSE(destination.depth("new"));
        tgfx::RenderTargetPool empty;
        moved_again = std::move(empty);
        CHECK(device.destroyed_textures.size() == 3u);
    }
    REQUIRE(device.destroyed_textures.size() == 3u);
    for (const auto destroyed : device.destroyed_textures)
        CHECK(destroyed != external);
    device.destroy(external);
    CHECK(device.destroyed_textures.size() == device.create_texture_count);
}

TEST_CASE("RenderContext2 reuses immutable uniform bytes only inside a frame") {
    PipelineCacheStatsDevice device;
    tgfx::PipelineCache cache(device);
    tgfx::RenderContext2 context(device, cache);
    tc_shader_resource_binding rb{};
    std::strcpy(rb.name, "material");
    rb.kind = TC_SHADER_RESOURCE_CONSTANT_BUFFER;
    rb.scope = TC_SHADER_RESOURCE_SCOPE_MATERIAL;
    rb.stage_mask = TC_SHADER_STAGE_FRAGMENT;
    rb.size = 16;
    tc_shader shader{};
    shader.has_resource_layout = 1;
    shader.resource_bindings = &rb;
    shader.resource_binding_count = 1;
    std::array<float, 4> data{1, 2, 3, 4};
    context.begin_frame();
    context.use_shader_resource_layout(&shader);
    context.bind_uniform_data(&rb, data.data(), sizeof(data));
    REQUIRE(device.uniform_uploads.size() == 1);
    const auto copy = data;
    context.bind_uniform_data(&rb, copy.data(), sizeof(copy));
    CHECK(device.uniform_uploads.size() == 1);
    data[0] = 7;
    context.bind_uniform_data(&rb, data.data(), sizeof(data));
    REQUIRE(device.uniform_uploads.size() == 2);
    CHECK(device.uniform_uploads[0] != device.uniform_uploads[1]);
    context.bind_uniform_data(&rb, copy.data(), sizeof(copy));
    CHECK(device.uniform_uploads.size() == 2);
    context.end_frame();
    context.begin_frame();
    context.use_shader_resource_layout(&shader);
    context.bind_uniform_data(&rb, copy.data(), sizeof(copy));
    CHECK(device.uniform_uploads.size() == 3);
    // Per-draw traffic is intentionally not retained in the content cache.
    rb.scope = TC_SHADER_RESOURCE_SCOPE_DRAW;
    context.use_shader_resource_layout(&shader);
    context.bind_uniform_data(&rb, copy.data(), sizeof(copy));
    context.bind_uniform_data(&rb, copy.data(), sizeof(copy));
    CHECK(device.uniform_uploads.size() == 5);
    context.end_frame();
}
