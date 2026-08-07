#include <termin/bootstrap/bootstrap.hpp>
#include <termin/bootstrap/bootstrap_c.h>
#include <termin/camera/camera_component.hpp>
#include <termin/engine/engine_core.hpp>
#include <termin/entity/entity.hpp>
#include <termin/framegraph_remote_target/target_service.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_graph_debugger.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/render/tc_pass.hpp>

#include <tgfx2/graphics_host.hpp>
#include <tgfx2/render_context.hpp>

extern "C" {
#include <core/tc_entity_pool_registry.h>
#include <core/tc_scene.h>
#include <render/tc_pipeline.h>
#include <render/tc_render_target.h>
}

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <thread>

#ifdef _WIN32
#include <process.h>
#else
#include <unistd.h>
#endif

using namespace std::chrono_literals;

namespace {

    constexpr int smoke_extent = 256;

    class SmokeClearPass final : public termin::CxxFramePass {
    public:
        SmokeClearPass() {
            pass_name_set("RemoteSmokeClear");
        }

        std::set<const char*> compute_writes() const override {
            return {"OUTPUT"};
        }

        void execute(termin::ExecuteContext& context) override {
            const auto output = context.tex2_writes.find("OUTPUT");
            if (!context.ctx2 || output == context.tex2_writes.end() || !output->second) {
                tc_log_error("remote framegraph smoke: OUTPUT texture is unavailable");
                return;
            }
            constexpr float clear[4] = {0.125F, 0.5F, 0.75F, 1.0F};
            context.ctx2->begin_pass(output->second, {}, clear, 1.0F, false);
            context.ctx2->end_pass();
        }
    };

    bool parse_port(const char* text, std::uint16_t& port) {
        char* end = nullptr;
        const unsigned long parsed = std::strtoul(text, &end, 10);
        if (!text[0] || !end || *end || parsed > 65535) {
            return false;
        }
        port = static_cast<std::uint16_t>(parsed);
        return true;
    }

    std::uint32_t process_id() {
#ifdef _WIN32
        return static_cast<std::uint32_t>(_getpid());
#else
        return static_cast<std::uint32_t>(getpid());
#endif
    }

    class RuntimeGuard {
    public:
        RuntimeGuard() {
            tc_init();
            termin::bootstrap::bootstrap_runtime(termin::bootstrap::RuntimeBootstrapProfile::Render);
        }

        ~RuntimeGuard() {
            tc_shutdown();
        }
    };

    class SmokeScene {
    public:
        explicit SmokeScene(termin::RenderingManager& manager)
            : manager_(manager) {
            scene_ = tc_scene_new();
            const tc_entity_pool_handle scene_pool = tc_entity_pool_registry_find(tc_scene_entity_pool(scene_));
            if (!tc_entity_pool_handle_valid(scene_pool)) {
                throw std::runtime_error("failed to resolve smoke scene pool");
            }
            camera_entity_ = termin::Entity::create(scene_pool, "RemoteSmokeCamera");
            camera_ = new termin::CameraComponent();
            camera_entity_.add_component(camera_);

            render_target_ = tc_render_target_new("RemoteSmokeTarget");
            tc_render_target_set_scene(render_target_, scene_);
            tc_render_target_set_camera(render_target_, camera_->tc_component_ptr());
            tc_render_target_set_width(render_target_, smoke_extent);
            tc_render_target_set_height(render_target_, smoke_extent);

            pipeline_handle_ = tc_pipeline_create("RemoteSmokePipeline");
            pipeline_.emplace(pipeline_handle_);
            pipeline_->add_pass((new SmokeClearPass())->tc_pass_ptr());
            tc_render_target_set_pipeline(render_target_, pipeline_handle_);
            manager_.register_managed_render_target(render_target_);
        }

        ~SmokeScene() {
            manager_.unregister_managed_render_target(render_target_);
            pipeline_.reset();
            tc_pipeline_destroy(pipeline_handle_);
            tc_render_target_free(render_target_);
            tc_entity_free(camera_entity_.handle());
            tc_scene_free(scene_);
        }

        void render_frame() {
            manager_.render_render_target_offscreen(render_target_);
        }

    private:
        termin::RenderingManager& manager_;
        tc_scene_handle scene_ = TC_SCENE_HANDLE_INVALID;
        termin::Entity camera_entity_;
        termin::CameraComponent* camera_ = nullptr;
        tc_render_target_handle render_target_ = TC_RENDER_TARGET_HANDLE_INVALID;
        tc_pipeline_handle pipeline_handle_ = TC_PIPELINE_HANDLE_INVALID;
        std::optional<termin::RenderPipeline> pipeline_;
    };

    int run_target(std::uint16_t port, const std::string& token) {
        RuntimeGuard runtime;
        std::unique_ptr<tgfx::GraphicsHost> graphics_host;
        try {
            graphics_host = tgfx::GraphicsHost::create_application(tgfx::BackendType::Vulkan);
        } catch (const std::exception& error) {
            std::cerr << "Failed to create Vulkan graphics host: " << error.what() << '\n';
            return 1;
        }
        if (!graphics_host || graphics_host->is_closed()) {
            std::cerr << "Failed to create Vulkan graphics host\n";
            return 1;
        }

        termin::EngineCore engine;
        engine.rendering_manager.render_engine()->set_graphics_host(*graphics_host);
        SmokeScene scene(engine.rendering_manager);
        termin::FrameGraphDebugger debugger(engine.rendering_manager);

        termin::framegraph_remote_target::TargetServiceConfig config;
        config.port = port;
        config.authentication_token = token;
        config.platform = "desktop-smoke";
        config.abi = "host";
        config.build_type = "test";
        config.build_id = "framegraph-reciprocal-smoke";
        config.process_id = process_id();
        config.outbound_queue_capacity = 8;
        termin::framegraph_remote_target::RemoteFrameGraphTarget target(debugger, std::move(config));
        if (!target.start()) {
            std::cerr << "Failed to start remote framegraph target\n";
            return 1;
        }

        std::cout << "READY port=" << target.status().listening_port << '\n' << std::flush;

        const auto deadline = std::chrono::steady_clock::now() + 60s;
        bool saw_client = false;
        std::uint64_t highest_session = 0;
        while (std::chrono::steady_clock::now() < deadline) {
            target.pump_render_thread();
            scene.render_frame();
            target.pump_render_thread();

            const auto status = target.status();
            saw_client |= status.client_connected;
            highest_session = std::max(highest_session, status.session_id);
            if (saw_client && highest_session >= 2 && !status.client_connected && status.completed_captures >= 5 &&
                status.preview_captures >= 2 && status.burst_captures >= 3) {
                std::cout << "COMPLETE captures=" << status.completed_captures << " preview=" << status.preview_captures
                          << " burst=" << status.burst_captures << " bytes=" << status.transmitted_bytes
                          << " outbound_drops=" << status.dropped_outbound_messages
                          << " capture_drops=" << status.dropped_captures
                          << " capture_ms=" << static_cast<double>(status.capture_time_ns) / 1'000'000.0
                          << " readback_ms=" << static_cast<double>(status.readback_time_ns) / 1'000'000.0
                          << " conversion_ms=" << static_cast<double>(status.conversion_time_ns) / 1'000'000.0
                          << " encode_ms=" << static_cast<double>(status.transfer_encode_time_ns) / 1'000'000.0
                          << " effective_preview_fps="
                          << static_cast<double>(status.effective_preview_millifps) / 1000.0 << '\n';
                target.stop();
                return 0;
            }
            std::this_thread::sleep_for(8ms);
        }

        const auto status = target.status();
        std::cerr << "Remote framegraph target timed out: session=" << highest_session
                  << " connected=" << status.client_connected << " captures=" << status.completed_captures
                  << " preview=" << status.preview_captures << " burst=" << status.burst_captures
                  << " outbound_drops=" << status.dropped_outbound_messages
                  << " capture_drops=" << status.dropped_captures << '\n';
        target.stop();
        return 1;
    }

} // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " PORT TOKEN\n";
        return 2;
    }
    std::uint16_t port = 0;
    if (!parse_port(argv[1], port) || !argv[2][0]) {
        std::cerr << "PORT must be in 0..65535 and TOKEN must be non-empty\n";
        return 2;
    }
    try {
        return run_target(port, argv[2]);
    } catch (const std::exception& error) {
        std::cerr << "Remote framegraph target failed: " << error.what() << '\n';
        return 1;
    }
}
