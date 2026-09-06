#pragma once

#include <tgfx2/i_render_device.hpp>

#include <memory>
#include <span>
#include <unordered_map>
#include <utility>
#include <vector>

// Records framegraph orchestration without selecting a native GPU backend.
// Pixel correctness belongs to the separate backend integration tests.
namespace termin::test {

    struct RecordedRenderScope {
        tgfx::RenderPassDesc pass;
        uint32_t view_count = 1;
    };

    struct ExecutionRecordingState {
        std::vector<RecordedRenderScope> scopes;
        std::vector<std::pair<tgfx::TextureHandle, tgfx::TextureDesc>> created_textures;
        std::vector<std::pair<tgfx::TextureHandle, tgfx::TextureHandle>> texture_copies;
        uint32_t framebuffer_local_barriers = 0;
    };

    class ExecutionRecordingCommandList final : public tgfx::ICommandList {
    public:
        explicit ExecutionRecordingCommandList(ExecutionRecordingState& state)
            : state_(state) {}

        void begin() override {}
        void end() override {}
        void begin_render_pass(const tgfx::RenderPassDesc& pass) override {
            state_.scopes.push_back({pass, 1});
        }
        void begin_multiview_render_pass(const tgfx::MultiviewRenderPassDesc& pass) override {
            tgfx::RenderPassDesc base;
            base.colors = pass.colors;
            base.depth = pass.depth;
            base.has_depth = pass.has_depth;
            state_.scopes.push_back({std::move(base), pass.view_count});
        }
        void end_render_pass() override {}
        void framebuffer_local_barrier() override {
            ++state_.framebuffer_local_barriers;
        }
        void bind_pipeline(tgfx::PipelineHandle) override {}
        void bind_resource_set(tgfx::ResourceSetHandle,
                               uint32_t = 0,
                               const uint32_t* = nullptr,
                               uint32_t = 0) override {}
        void set_push_constants(const void*, uint32_t) override {}
        void bind_vertex_buffer(uint32_t, tgfx::BufferHandle, uint64_t = 0) override {}
        void bind_index_buffer(tgfx::BufferHandle, tgfx::IndexType, uint64_t = 0) override {}
        void draw(uint32_t, uint32_t = 0) override {}
        void draw_instanced(uint32_t, uint32_t, uint32_t = 0, uint32_t = 0) override {}
        void draw_indexed(uint32_t, uint32_t = 0, int32_t = 0) override {}
        void draw_indexed_instanced(uint32_t, uint32_t, uint32_t = 0, int32_t = 0, uint32_t = 0) override {}
        void dispatch(uint32_t, uint32_t, uint32_t) override {}
        void copy_buffer(tgfx::BufferHandle, tgfx::BufferHandle, uint64_t, uint64_t = 0, uint64_t = 0) override {}
        void copy_texture(tgfx::TextureHandle src, tgfx::TextureHandle dst) override {
            state_.texture_copies.emplace_back(src, dst);
        }
        void set_viewport(int, int, int, int) override {}
        void set_scissor(int, int, int, int) override {}

    private:
        ExecutionRecordingState& state_;
    };

    class ExecutionRecordingDevice final : public tgfx::IRenderDevice {
    public:
        ExecutionRecordingState state;

        tgfx::BackendType backend_type() const override {
            return tgfx::BackendType::Vulkan;
        }
        tgfx::BackendCapabilities capabilities() const override {
            tgfx::BackendCapabilities caps;
            caps.backend = tgfx::BackendType::Vulkan;
            caps.supports_multiview = true;
            caps.supports_multisample_resolve = true;
            return caps;
        }
        void wait_idle() override {}
        tgfx::BufferHandle create_buffer(const tgfx::BufferDesc&) override {
            return tgfx::BufferHandle{next_buffer_id_++};
        }
        tgfx::TextureHandle create_texture(const tgfx::TextureDesc& desc) override {
            const tgfx::TextureHandle handle{next_texture_id_++};
            texture_descs_[handle.id] = desc;
            state.created_textures.emplace_back(handle, desc);
            return handle;
        }
        tgfx::SamplerHandle create_sampler(const tgfx::SamplerDesc&) override {
            return tgfx::SamplerHandle{1};
        }
        tgfx::ShaderHandle create_shader(const tgfx::ShaderDesc&) override {
            return tgfx::ShaderHandle{1};
        }
        tgfx::PipelineHandle create_pipeline(const tgfx::PipelineDesc&) override {
            return tgfx::PipelineHandle{1};
        }
        tgfx::ResourceSetHandle create_bound_resource_set(const tgfx::BoundResourceSetDesc&) override {
            return tgfx::ResourceSetHandle{1};
        }
        void destroy(tgfx::BufferHandle) override {}
        void destroy(tgfx::TextureHandle handle) override {
            texture_descs_.erase(handle.id);
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
        tgfx::TextureDesc texture_desc(tgfx::TextureHandle handle) const override {
            const auto it = texture_descs_.find(handle.id);
            return it == texture_descs_.end() ? tgfx::TextureDesc{} : it->second;
        }
        std::unique_ptr<tgfx::ICommandList> create_command_list(tgfx::QueueType = tgfx::QueueType::Graphics) override {
            return std::make_unique<ExecutionRecordingCommandList>(state);
        }
        void submit(tgfx::ICommandList&) override {}
        void present() override {}

    private:
        uint32_t next_buffer_id_ = 1;
        uint32_t next_texture_id_ = 1;
        std::unordered_map<uint32_t, tgfx::TextureDesc> texture_descs_;
    };

} // namespace termin::test
