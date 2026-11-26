#include "render_execution_recording_device.hpp"

#include <termin/bootstrap/bootstrap.hpp>
#include <termin/camera/camera_component.hpp>
#include <termin/engine/engine_core.hpp>
#include <termin/platform/offscreen_render_surface.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/render_engine.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx/resources/tc_texture.h>
#include <tgfx2/graphics_host.hpp>
#include <tgfx2/render_context.hpp>

#include <cstdio>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {
    bool check(bool result, const char* message) {
        if (!result)
            std::fprintf(stderr, "offscreen frame: %s\n", message);
        return result;
    }

    class Device final : public termin::test::ExecutionRecordingDevice {
    public:
        bool fail_submit = false;
        unsigned recorded_blits = 0;

        tgfx::TextureHandle ensure_tc_texture(tc_texture* source) override {
            auto& handle = textures_[source->header.pool_index];
            if (!handle) {
                tgfx::TextureDesc desc;
                desc.width = source->width;
                desc.height = source->height;
                if (source->format == TC_TEXTURE_DEPTH32F || source->format == TC_TEXTURE_DEPTH24) {
                    desc.format = tgfx::PixelFormat::D32F;
                    desc.usage = tgfx::TextureUsage::DepthStencilAttachment;
                } else {
                    desc.format = tgfx::PixelFormat::RGBA8_UNorm;
                    desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::ColorAttachment |
                                 tgfx::TextureUsage::CopySrc | tgfx::TextureUsage::CopyDst;
                }
                handle = create_texture(desc);
            }
            return handle;
        }

        void clear_texture(tgfx::TextureHandle, termin::LinearColor, termin::Bounds2i) override {}
        void blit_to_texture(tgfx::TextureHandle, tgfx::TextureHandle,
                             termin::Bounds2i, termin::Bounds2i) override {}
        void record_blit_to_texture(tgfx::ICommandList&, tgfx::TextureHandle, tgfx::TextureHandle,
                                    termin::Bounds2i, termin::Bounds2i) override {
            ++recorded_blits;
        }

        void submit(tgfx::ICommandList& commands) override {
            if (std::exchange(fail_submit, false))
                throw std::runtime_error("test submit failure");
            ExecutionRecordingDevice::submit(commands);
        }

    private:
        std::unordered_map<uint32_t, tgfx::TextureHandle> textures_;
    };

    class Pass final : public termin::CxxFramePass {
    public:
        Pass(const char* name, std::vector<std::string>& executed, bool uses_feed)
            : executed_(executed), uses_feed_(uses_feed) { pass_name_set(name); }

        std::set<const char*> compute_reads() const override {
            return uses_feed_ ? std::set{"feed"} : std::set<const char*>{};
        }
        std::set<const char*> compute_writes() const override { return {"RT_COLOR"}; }
        void execute(termin::ExecuteContext& context) override {
            executed_.push_back(pass_name_get());
            if (uses_feed_)
                context.ctx2->blit(context.tex2_reads.at("feed"), context.tex2_writes.at("RT_COLOR"));
        }

    private:
        std::vector<std::string>& executed_;
        bool uses_feed_;
    };

    bool verify() {
        auto storage = std::make_unique<Device>();
        auto& device = *storage;
        auto host = tgfx::GraphicsHost::adopt_isolated_device(std::move(storage));
        termin::RenderEngine renderer;
        renderer.set_graphics_host(*host);
        termin::EngineCore core;
        auto& manager = core.rendering_manager;
        manager.set_render_engine(&renderer);

        const auto make_camera = [&](const char* name) {
            auto scene = core.scene_manager.create_scene(termin::SceneKey(name, termin::SceneRole::Authoring));
            core.scene_manager.set_mode(scene, TC_SCENE_MODE_STOP);
            auto entity = termin::TcSceneRef(scene).create_entity("Camera");
            auto* camera = new termin::CameraComponent();
            entity.add_component(camera);
            return std::pair{scene, camera->tc_component_ptr()};
        };
        auto [scene, camera] = make_camera("Scene");
        auto [other_scene, other_camera] = make_camera("Other scene");
        std::vector<std::string> executed;
        const auto make_target = [&](const char* name, tc_scene_handle owner, tc_component* view, bool uses_feed) {
            termin::RenderPipeline pipeline(name);
            pipeline.add_pass((new Pass(name, executed, uses_feed))->tc_pass_ptr());
            auto rt = tc_render_target_new(name);
            tc_render_target_set_scene(rt, owner);
            tc_render_target_set_camera(rt, view);
            tc_render_target_set_pipeline(rt, pipeline.handle());
            tc_render_target_set_width(rt, 16);
            tc_render_target_set_height(rt, 16);
            manager.register_managed_render_target(rt);
            return rt;
        };
        auto producer = make_target("Producer", scene, camera, false);
        auto consumer = make_target("Consumer", scene, camera, true);
        auto independent = make_target("Independent", other_scene, other_camera, false);
        tc_value params = tc_value_dict_new();
        tc_value_dict_set(&params, "feed", tc_value_string("Producer"));
        tc_render_target_set_pipeline_params(consumer, &params);
        tc_value_free(&params);

        const auto show = [&](tc_render_target_handle target) {
            auto display = termin::create_offscreen_display(&device, 16, 16, "Display");
            auto viewport = tc_viewport_new("Viewport", tc_render_target_get_scene(target));
            tc_viewport_set_render_target(viewport, target);
            tc_viewport_set_rect(viewport, 0.f, 0.f, 1.f, 1.f);
            tc_display_add_viewport(display, viewport);
            manager.add_display(display);
            return std::pair{display, viewport};
        };
        auto first = show(consumer);
        auto second = show(independent);

        manager.render_pending(false);
        bool ok = check(executed == std::vector<std::string>{"Producer", "Consumer", "Independent"},
                        "producer must record before its consumer across a batch with two displays");
        ok &= check(device.state.command_lists == 1 && device.state.submits == 1,
                    "all three jobs must share one command list and submit");
        ok &= check(device.state.texture_copies.size() == 1, "consumer must record a copy from its producer");
        executed.clear();
        manager.render_pending(false);
        ok &= check(executed.empty() && device.state.command_lists == 1 && device.state.submits == 1,
                    "clean frame must not create a command list or submit");

        auto* context = renderer.tgfx2_ctx();
        context->begin_frame();
        manager.render_pending(true);
        ok &= check(context->in_frame() && !context->in_pass() && device.state.command_lists == 2 &&
                        device.state.submits == 1 && device.recorded_blits == 2,
                    "an open host frame owns the submit and receives ordered display composition");
        context->end_frame();
        ok &= check(device.state.submits == 2, "host must be able to submit its borrowed frame");

        tc_render_target_request_render(producer);
        device.fail_submit = true;
        try {
            manager.render_pending(false);
            ok &= check(false, "submit failure must reach the caller");
        } catch (const std::runtime_error&) {
            ok &= check(!context->in_frame(), "failed submit must release the command list");
        }
        executed.clear();
        manager.render_pending(false);
        ok &= check(executed.size() == 3 && device.state.submits == 3,
                    "failed submit must invalidate provisional outputs so the next frame can retry");

        for (const auto& [display, viewport] : {first, second}) {
            manager.remove_display(display);
            tc_display_remove_viewport(display, viewport);
            tc_viewport_free(viewport);
            tc_display_free(display);
        }
        for (auto target : {consumer, producer, independent}) {
            manager.unregister_managed_render_target(target);
            termin::RenderPipeline(tc_render_target_get_pipeline(target)).destroy();
            tc_render_target_free(target);
        }
        return ok;
    }
}

int main() {
    termin::bootstrap::bootstrap_runtime();
    const bool ok = verify();
    termin::bootstrap::shutdown_runtime();
    return ok ? 0 : 1;
}
