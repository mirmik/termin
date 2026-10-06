#include <termin/bootstrap/bootstrap.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/id_pass.hpp>
#include <termin/render/render_item_culling.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/static_mesh_batch.hpp>
#include <components/mesh_component.hpp>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <termin/render/line_renderer.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/scene_render_services.hpp>
#include <termin/render/world_text_component.hpp>
#include <termin/tc_scene.hpp>

#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <core/tc_scene_pool.h>
#include <tc_picking.h>
}

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <memory>
#include <string>
#include <system_error>
#include <vector>

namespace {

    constexpr uint32_t kWidth = 64;
    constexpr uint32_t kHeight = 64;

    bool matches_clear_color(const float pixel[4]) {
        return pixel[0] >= 0.00f && pixel[0] < 0.04f && pixel[1] >= 0.00f && pixel[1] < 0.04f && pixel[2] >= 0.00f &&
               pixel[2] < 0.04f && pixel[3] >= 0.00f && pixel[3] < 0.04f;
    }

    bool matches_pick_color(uint32_t pick_id, const float pixel[4]) {
        int r = 0;
        int g = 0;
        int b = 0;
        tc_picking_id_to_rgb(pick_id, &r, &g, &b);
        const float expected[3] = {
            static_cast<float>(r) / 255.0f,
            static_cast<float>(g) / 255.0f,
            static_cast<float>(b) / 255.0f,
        };
        constexpr float kTolerance = 2.0f / 255.0f;
        return std::abs(pixel[0] - expected[0]) <= kTolerance && std::abs(pixel[1] - expected[1]) <= kTolerance &&
               std::abs(pixel[2] - expected[2]) <= kTolerance && pixel[3] >= 0.95f;
    }

    void print_pixel(const char* label, const float pixel[4]) {
        std::printf("%s: (%.3f %.3f %.3f %.3f)\n", label, pixel[0], pixel[1], pixel[2], pixel[3]);
    }

    bool existing_file(const std::filesystem::path& path) {
        std::error_code ec;
        return std::filesystem::is_regular_file(path, ec);
    }

    std::vector<std::filesystem::path> shaderc_candidates(const char* argv0) {
        std::vector<std::filesystem::path> candidates;

        if (const char* configured = std::getenv("TERMIN_SHADERC")) {
            if (configured[0] != '\0') {
                candidates.emplace_back(configured);
            }
        }

        if (argv0 && argv0[0] != '\0') {
            std::error_code ec;
            const std::filesystem::path exe_dir = std::filesystem::absolute(argv0, ec).parent_path();
            if (!ec && !exe_dir.empty()) {
                candidates.push_back(exe_dir / "termin_shaderc");
#ifdef _WIN32
                candidates.push_back(exe_dir / "termin_shaderc.exe");
#endif
            }
        }

        if (const char* sdk = std::getenv("TERMIN_SDK")) {
            if (sdk[0] != '\0') {
                candidates.push_back(std::filesystem::path(sdk) / "bin" / "termin_shaderc");
#ifdef _WIN32
                candidates.push_back(std::filesystem::path(sdk) / "bin" / "termin_shaderc.exe");
#endif
            }
        }

        candidates.push_back(std::filesystem::current_path() / "sdk" / "bin" / "termin_shaderc");
#ifdef _WIN32
        candidates.push_back(std::filesystem::current_path() / "sdk" / "bin" / "termin_shaderc.exe");
#endif
        return candidates;
    }

    void configure_shader_artifacts(const char* argv0, const std::filesystem::path& root) {
        for (const std::filesystem::path& candidate : shaderc_candidates(argv0)) {
            if (existing_file(candidate)) {
                termin::tgfx2_set_shader_compiler_path(candidate.string().c_str());
                break;
            }
        }

        termin::tgfx2_set_shader_artifact_root(root.string().c_str());
        termin::tgfx2_set_shader_cache_root((root / ".cache").string().c_str());
        termin::tgfx2_set_shader_dev_compile_enabled(true);
    }

    struct ScopedTempDirectory {
        std::filesystem::path path;

        ~ScopedTempDirectory() {
            std::filesystem::remove_all(path);
        }
    };

    termin::TcMaterial create_line_material() {
        termin::TcMaterial material =
            termin::TcMaterial::create("IdPassLinePixelSmokeMaterial", "id-pass-line-pixel-smoke-mat");
        if (!material.is_valid()) {
            return {};
        }

        tc_material_phase* phase = material.add_phase(tc_shader_handle_invalid(), "opaque", 0);
        if (!phase) {
            return {};
        }
        phase->state = tc_render_state_opaque();
        phase->state.cull = 0;
        phase->state.depth_test = 0;
        phase->state.depth_write = 0;
        return material;
    }

    termin::TcSceneRef create_scene(const termin::TcMaterial& material, uint32_t& out_pick_id) {
        termin::LineRenderer::register_type();

        termin::TcSceneRef scene = termin::TcSceneRef::create("id-pass-line-pixel-smoke");
        termin::Entity entity = scene.create_entity("PickableLine");
        if (!entity.valid()) {
            return {};
        }
        entity.set_pickable(true);
        out_pick_id = entity.pick_id();

        auto* renderer = new termin::LineRenderer();
        renderer->set_material(material);
        renderer->set_width(0.2f);
        // Identity projection uses Vulkan's [0, 1] clip-depth range. Keep the
        // entire tube in front of the near plane instead of bisecting it at z=0.
        renderer->set_points({tc_vec3{-0.75f, 0.0f, 0.5f}, tc_vec3{0.75f, 0.0f, 0.5f}});
        entity.add_component(renderer);

        return scene;
    }

    termin::TcSceneRef create_world_text_scene(uint32_t& out_pick_id) {
        termin::WorldTextComponent::register_type();

        termin::TcSceneRef scene = termin::TcSceneRef::create("id-pass-world-text-pixel-smoke");
        termin::Entity entity = scene.create_entity("PickableWorldText");
        if (!entity.valid()) {
            return {};
        }
        entity.set_pickable(true);
        out_pick_id = entity.pick_id();

        auto* text = new termin::WorldTextComponent();
        text->set_text("Text");
        text->set_font_path(TERMIN_RENDER_PASSES_TEST_FONT_PATH);
        text->set_phase_mark("transparent");
        text->set_orientation(termin::WorldTextOrientation::Fixed);
        text->set_plane_normal(termin::Vec3{0.0, 0.0, 1.0});
        text->set_text_up(termin::Vec3{0.0, 1.0, 0.0});
        text->set_local_offset(termin::Vec3{-0.45, -0.25, 0.0});
        text->set_size(0.5f);
        entity.add_component(text);
        return scene;
    }

    int run_smoke(const char* argv0) {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        const ScopedTempDirectory artifact_root{
            std::filesystem::temp_directory_path() /
            ("termin-render-passes-id-pass-line-pixel-smoke-" + std::to_string(unique))};
        std::filesystem::remove_all(artifact_root.path);
        configure_shader_artifacts(argv0, artifact_root.path);

        termin::TcMaterial material = create_line_material();
        if (!material.is_valid()) {
            std::fprintf(stderr, "Failed to create IdPass line smoke material\n");
            return 1;
        }

        uint32_t pick_id = 0;
        termin::TcSceneRef scene = create_scene(material, pick_id);
        if (!scene.valid()) {
            std::fprintf(stderr, "Failed to create IdPass line smoke scene\n");
            return 1;
        }
        if (pick_id == 0) {
            std::fprintf(stderr, "Failed to create pickable line entity\n");
            return 1;
        }

        std::unique_ptr<tgfx::IRenderDevice> device;
        try {
            device = tgfx::create_device(tgfx::BackendType::Vulkan);
        } catch (const std::exception& e) {
            std::fprintf(stderr, "Failed to create Vulkan device: %s\n", e.what());
            return 1;
        }

        tgfx::TextureDesc color_desc;
        color_desc.width = kWidth;
        color_desc.height = kHeight;
        color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        color_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        tgfx::TextureHandle color = device->create_texture(color_desc);
        if (!color) {
            std::fprintf(stderr, "Failed to create id color texture\n");
            return 1;
        }

        tgfx::TextureDesc depth_desc;
        depth_desc.width = kWidth;
        depth_desc.height = kHeight;
        depth_desc.format = tgfx::PixelFormat::D32F;
        depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment;
        tgfx::TextureHandle depth = device->create_texture(depth_desc);
        if (!depth) {
            std::fprintf(stderr, "Failed to create id depth texture\n");
            device->destroy(color);
            return 1;
        }

        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 render_ctx(*device, cache);
        termin::IdPass pass("empty", "id", "IdPassLinePixelSmoke");

        termin::RenderItemSnapshot render_item_snapshot;
        termin::TcSceneRenderItemSource item_source(scene.handle());
        if (!item_source.publish(render_item_snapshot, {})) {
            return false;
        }
        termin::ExecuteContext exec_ctx;
        exec_ctx.render_item_snapshot = &render_item_snapshot;
        exec_ctx.ctx2 = &render_ctx;
        exec_ctx.tex2_writes.emplace("id", color);
        exec_ctx.tex2_depth_writes.emplace("id", depth);
        exec_ctx.render_rect = {0, 0, static_cast<int>(kWidth), static_cast<int>(kHeight)};
        const termin::SceneRenderServices scene_services(scene);
        termin::RenderExecutionCapabilities capabilities;
        capabilities.add(scene_services);
        exec_ctx.capabilities = &capabilities;

        render_ctx.begin_frame();
        pass.execute_with_data_tgfx2(exec_ctx,
                                     exec_ctx.render_rect,
                                     scene.handle(),
                                     termin::Mat44f::identity(),
                                     termin::Mat44f::identity(),
                                     termin::Vec3{0.0, -1.0, 0.0},
                                     UINT64_MAX);
        render_ctx.end_frame();
        device->wait_idle();

        float center[4] = {};
        float corner[4] = {};
        const bool read_ok =
            device->read_pixel_rgba8(color, static_cast<int>(kWidth / 2), static_cast<int>(kHeight / 2), center) &&
            device->read_pixel_rgba8(color, 0, 0, corner);

        print_pixel("center", center);
        print_pixel("top-left", corner);

        const bool entity_seen = pass.entity_names.size() == 1 && pass.entity_names[0] == "PickableLine";
        const bool pass_ok = read_ok && matches_pick_color(pick_id, center) && matches_clear_color(corner) &&
                             cache.size() >= 1 && entity_seen;

        pass.destroy();
        device->destroy(depth);
        device->destroy(color);

        if (!pass_ok) {
            std::fprintf(stderr,
                         "IdPass line pixel smoke failed: read_ok=%s cache_size=%zu entity_seen=%s pick_id=%u\n",
                         read_ok ? "true" : "false",
                         cache.size(),
                         entity_seen ? "true" : "false",
                         pick_id);
            return 1;
        }

        return 0;
    }

    int run_world_text_smoke(const char* argv0) {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        const ScopedTempDirectory artifact_root{
            std::filesystem::temp_directory_path() /
            ("termin-render-passes-id-pass-world-text-pixel-smoke-" + std::to_string(unique))};
        std::filesystem::remove_all(artifact_root.path);
        configure_shader_artifacts(argv0, artifact_root.path);

        uint32_t pick_id = 0;
        termin::TcSceneRef scene = create_world_text_scene(pick_id);
        if (!scene.valid() || pick_id == 0) {
            std::fprintf(stderr, "Failed to create pickable WorldText scene\n");
            return 1;
        }

        std::unique_ptr<tgfx::IRenderDevice> device;
        try {
            device = tgfx::create_device(tgfx::BackendType::Vulkan);
        } catch (const std::exception& e) {
            std::fprintf(stderr, "Failed to create Vulkan device: %s\n", e.what());
            return 1;
        }

        tgfx::TextureDesc color_desc;
        color_desc.width = kWidth;
        color_desc.height = kHeight;
        color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        color_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        const tgfx::TextureHandle color = device->create_texture(color_desc);
        tgfx::TextureDesc depth_desc;
        depth_desc.width = kWidth;
        depth_desc.height = kHeight;
        depth_desc.format = tgfx::PixelFormat::D32F;
        depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment;
        const tgfx::TextureHandle depth = device->create_texture(depth_desc);
        if (!color || !depth) {
            std::fprintf(stderr, "Failed to create WorldText IdPass targets\n");
            if (depth)
                device->destroy(depth);
            if (color)
                device->destroy(color);
            return 1;
        }

        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 render_ctx(*device, cache);
        termin::IdPass pass("empty", "id", "IdPassWorldTextPixelSmoke");
        termin::RenderItemSnapshot render_item_snapshot;
        termin::TcSceneRenderItemSource item_source(scene.handle());
        if (!item_source.publish(render_item_snapshot, {})) {
            return false;
        }
        termin::ExecuteContext exec_ctx;
        exec_ctx.render_item_snapshot = &render_item_snapshot;
        exec_ctx.ctx2 = &render_ctx;
        exec_ctx.tex2_writes.emplace("id", color);
        exec_ctx.tex2_depth_writes.emplace("id", depth);
        exec_ctx.render_rect = {0, 0, static_cast<int>(kWidth), static_cast<int>(kHeight)};
        const termin::SceneRenderServices scene_services(scene);
        termin::RenderExecutionCapabilities capabilities;
        capabilities.add(scene_services);
        exec_ctx.capabilities = &capabilities;

        render_ctx.begin_frame();
        pass.execute_with_data_tgfx2(exec_ctx,
                                     exec_ctx.render_rect,
                                     scene.handle(),
                                     termin::Mat44f::identity(),
                                     termin::Mat44f::identity(),
                                     termin::Vec3{0.0, -1.0, 0.0},
                                     UINT64_MAX);
        render_ctx.end_frame();
        device->wait_idle();

        bool saw_pick_color = false;
        bool read_ok = true;
        for (uint32_t y = 0; y < kHeight; ++y) {
            for (uint32_t x = 0; x < kWidth; ++x) {
                float pixel[4] = {};
                read_ok = device->read_pixel_rgba8(color, static_cast<int>(x), static_cast<int>(y), pixel) && read_ok;
                saw_pick_color = matches_pick_color(pick_id, pixel) || saw_pick_color;
            }
        }

        const bool entity_seen = pass.entity_names.size() == 1 && pass.entity_names[0] == "PickableWorldText";
        const bool pass_ok = read_ok && saw_pick_color && entity_seen && cache.size() >= 1;
        pass.destroy();
        device->destroy(depth);
        device->destroy(color);
        if (!pass_ok) {
            std::fprintf(
                stderr,
                "IdPass WorldText pixel smoke failed: read_ok=%s saw_pick_color=%s entity_seen=%s cache_size=%zu\n",
                read_ok ? "true" : "false",
                saw_pick_color ? "true" : "false",
                entity_seen ? "true" : "false",
                cache.size());
            return 1;
        }
        return 0;
    }


    int run_batched_mesh_smoke(const char* argv0) {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        const ScopedTempDirectory artifact_root{std::filesystem::temp_directory_path() /
                                                ("termin-id-batched-smoke-" + std::to_string(unique))};
        configure_shader_artifacts(argv0, artifact_root.path);
        termin::MeshComponent::register_type();
        termin::MeshRenderer::register_type();
        auto material = termin::TcMaterial::create("BatchedPickMaterial", "batched-pick-material");
        auto* phase = material.add_phase(tc_shader_handle_invalid(), "opaque", 0);
        if (!phase) return 1;
        phase->state = tc_render_state_opaque();
        phase->state.cull = 0;
        auto scene = termin::TcSceneRef::create("batched-pick-scene");
        uint32_t ids[2]{};
        for (uint32_t member = 0; member < 2; ++member) {
            const float x = member == 0 ? 0.1f : 0.55f;
            const float vertices[] = {
                x, 0.1f, 0.5f, 0, 0, 1, 0, 0,
                x + 0.3f, 0.1f, 0.5f, 0, 0, 1, 1, 0,
                x + 0.3f, 0.6f, 0.5f, 0, 0, 1, 1, 1,
                x, 0.6f, 0.5f, 0, 0, 1, 0, 1,
            };
            // IdPass enforces back-face culling; use the engine's front-facing winding.
            const uint32_t indices[] = {0, 2, 1, 0, 3, 2};
            auto layout = tc_vertex_layout_pos_normal_uv();
            termin::TcMeshCreateInfo info;
            info.data = termin::TcMeshInterleavedDataView{vertices, 4, indices, 6, &layout};
            const std::string name = "BatchedPick" + std::to_string(member);
            info.name = name;
            info.uuid_hint = name;
            auto mesh = termin::TcMesh::from_interleaved(info);
            if (!mesh.is_valid()) return 1;
            auto entity = scene.create_entity(name);
            entity.set_pickable(true);
            ids[member] = entity.pick_id();
            auto* mesh_component = new termin::MeshComponent();
            mesh_component->set_mesh(mesh);
            entity.add_component(mesh_component);
            auto* renderer = new termin::MeshRenderer();
            renderer->static_batching = true;
            renderer->set_material(material);
            entity.add_component(renderer);
        }
        termin::RenderItemSnapshot control_snapshot;
        termin::TcSceneRenderItemSource control_source(scene.handle());
        if (!control_source.publish(control_snapshot, {})) return 1;
        termin::StaticMeshBatchCache batches;
        termin::RenderItemSnapshot snapshot;
        termin::TcSceneRenderItemSource source(scene.handle(), nullptr, TC_SCENE_FILTER_NONE, &batches);
        if (!source.publish(snapshot, {})) return 1;
        bool saw_batch = false;
        for (const auto& item : snapshot.items()) {
            if (item.flags & TC_RENDER_ITEM_FLAG_BATCHED_GEOMETRY) saw_batch = true;
        }
        if (!saw_batch) {
            std::fprintf(stderr, "IdPass batch smoke: merger did not produce batched geometry\n");
            return 1;
        }
        auto device = tgfx::create_device(tgfx::BackendType::Vulkan);
        tgfx::TextureDesc color_desc;
        color_desc.width = kWidth;
        color_desc.height = kHeight;
        color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        color_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        auto color = device->create_texture(color_desc);
        auto depth_desc = color_desc;
        depth_desc.format = tgfx::PixelFormat::D32F;
        depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment;
        auto depth = device->create_texture(depth_desc);
        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 render_ctx(*device, cache);
        termin::IdPass pass("empty", "id", "IdPassBatchedSmoke");
        termin::ExecuteContext exec_ctx;
        exec_ctx.ctx2 = &render_ctx;
        exec_ctx.render_item_snapshot = &snapshot;
        exec_ctx.tex2_writes.emplace("id", color);
        exec_ctx.tex2_depth_writes.emplace("id", depth);
        exec_ctx.render_rect = {0, 0, int(kWidth), int(kHeight)};
        const termin::SceneRenderServices services(scene);
        termin::RenderExecutionCapabilities capabilities;
        capabilities.add(services);
        exec_ctx.capabilities = &capabilities;
        bool all_ok = true;
        termin::clear_render_item_culling_diagnostics();
        // Reuse each immutable snapshot in independent views. The batch pivot is
        // outside the camera after translation, but its geometry crosses the edge.
        for (bool batched : {false, true}) {
            exec_ctx.render_item_snapshot = batched ? &snapshot : &control_snapshot;
            for (float camera_shift : {0.0f, -1.25f, 0.5f, 0.75f, 2.0f, 0.0f}) {
                auto view = termin::Mat44f::identity();
                view.data[12] = camera_shift;
                exec_ctx.render_target_name = camera_shift == 0 ? "origin-view" : "moved-view";
                int baseline_ids[12]{};
                bool ok = true;
                for (bool enabled : {false, true}) {
                    termin::set_render_item_culling_enabled(enabled);
                    render_ctx.begin_frame();
                    pass.execute_with_data_tgfx2(exec_ctx, exec_ctx.render_rect, scene.handle(), view,
                                                termin::Mat44f::identity(), termin::Vec3{0, 0, 0}, UINT64_MAX);
                    render_ctx.end_frame();
                    device->wait_idle();
                    bool found[2]{};
                    int sample = 0;
                    // Both native image origins are covered. The last samples
                    // exercise the few pixels retained at the right camera edge.
                    for (int x : {2, 12, 40, 54, 56, 62}) {
                        for (int y : {20, 44}) {
                            float pixel[4]{};
                            ok = device->read_pixel_rgba8(color, x, y, pixel) && ok;
                            const int decoded = tc_picking_rgb_to_id(int(std::lround(pixel[0] * 255)),
                                                                    int(std::lround(pixel[1] * 255)),
                                                                    int(std::lround(pixel[2] * 255)));
                            found[0] = found[0] || decoded == int(ids[0]);
                            found[1] = found[1] || decoded == int(ids[1]);
                            if (!enabled) baseline_ids[sample] = decoded;
                            else ok = ok && decoded == baseline_ids[sample];
                            ++sample;
                        }
                    }
                    ok = ok && found[0] == (camera_shift < 2) && found[1] == (camera_shift <= 0);
                    const size_t visible_draws = camera_shift >= 2 ? 0 : (batched || camera_shift > 0 ? 1 : 2);
                    ok = ok && pass.entity_names.size() == (enabled ? visible_draws : (batched ? 1u : 2u));
                    bool found_counters = false;
                    for (const auto& diagnostic : termin::get_render_item_culling_diagnostics()) {
                        if (diagnostic.target != exec_ctx.render_target_name || diagnostic.pass != pass.get_pass_name())
                            continue;
                        found_counters = true;
                        const uint64_t candidates = batched ? 1 : 2;
                        const uint64_t culled = candidates - visible_draws;
                        ok = ok && diagnostic.counters.candidates == candidates &&
                             diagnostic.counters.tested == (enabled ? candidates : 0) &&
                             diagnostic.counters.culled == (enabled ? culled : 0) &&
                             diagnostic.counters.mesh_draws == (enabled ? visible_draws : candidates);
                    }
                    ok = ok && found_counters;
                }
                if (!ok)
                    std::fprintf(stderr, "IdPass culling %s failed: camera shift %.2f, source IDs %u/%u\n",
                                 batched ? "batch" : "ordinary", camera_shift, ids[0], ids[1]);
                all_ok = all_ok && ok;
            }
        }
        termin::set_render_item_culling_enabled(true);
        // Returning to origin did not overwrite the independent moved view's counters.
        for (const auto& diagnostic : termin::get_render_item_culling_diagnostics()) {
            if (diagnostic.pass != pass.get_pass_name()) continue;
            all_ok = all_ok && diagnostic.counters.culled == (diagnostic.target == "origin-view" ? 0u : 1u);
        }
        // Many equal shader keys exercise std::sort's partitioning. Removing
        // offscreen items must preserve coplanar survivors and their pick winner.
        {
            auto coplanar_scene = termin::TcSceneRef::create("coplanar-culling-order");
            uint32_t coplanar_ids[2]{};
            for (int member = 0; member < 40; ++member) {
                const float x = member < 2 ? 0.1f : 3.0f;
                const float vertices[] = {
                    x, 0.1f, 0.5f, 0, 0, 1, 0, 0,
                    x + 0.3f, 0.1f, 0.5f, 0, 0, 1, 1, 0,
                    x + 0.3f, 0.6f, 0.5f, 0, 0, 1, 1, 1,
                    x, 0.6f, 0.5f, 0, 0, 1, 0, 1,
                };
                const uint32_t indices[] = {0, 2, 1, 0, 3, 2};
                auto layout = tc_vertex_layout_pos_normal_uv();
                termin::TcMeshCreateInfo info;
                info.data = {vertices, 4, indices, 6, &layout};
                const std::string name = (member < 2 ? "Coplanar" : "Offscreen") + std::to_string(member);
                info.name = name;
                info.uuid_hint = name;
                auto mesh = termin::TcMesh::from_interleaved(info);
                if (!mesh.is_valid()) return 1;
                auto entity = coplanar_scene.create_entity(name);
                entity.set_pickable(true);
                if (member < 2) coplanar_ids[member] = entity.pick_id();
                auto* mesh_component = new termin::MeshComponent();
                mesh_component->set_mesh(mesh);
                entity.add_component(mesh_component);
                auto* renderer = new termin::MeshRenderer();
                renderer->set_material(material);
                entity.add_component(renderer);
            }
            termin::RenderItemSnapshot coplanar_snapshot;
            termin::TcSceneRenderItemSource coplanar_source(coplanar_scene.handle());
            if (!coplanar_source.publish(coplanar_snapshot, {})) return 1;
            const termin::SceneRenderServices coplanar_services(coplanar_scene);
            termin::RenderExecutionCapabilities coplanar_capabilities;
            coplanar_capabilities.add(coplanar_services);
            exec_ctx.capabilities = &coplanar_capabilities;
            exec_ctx.render_item_snapshot = &coplanar_snapshot;
            exec_ctx.render_target_name = "coplanar-view";
            std::vector<std::string> baseline_order;
            int baseline_winner = 0;
            for (bool enabled : {false, true}) {
                termin::set_render_item_culling_enabled(enabled);
                render_ctx.begin_frame();
                pass.execute_with_data_tgfx2(exec_ctx, exec_ctx.render_rect, coplanar_scene.handle(),
                                            termin::Mat44f::identity(), termin::Mat44f::identity(),
                                            termin::Vec3{0, 0, 0}, UINT64_MAX);
                render_ctx.end_frame();
                device->wait_idle();
                std::vector<std::string> order;
                for (const auto& name : pass.entity_names)
                    if (name.starts_with("Coplanar")) order.push_back(name);
                int winner = 0;
                for (int y : {20, 44}) {
                    float pixel[4]{};
                    all_ok = device->read_pixel_rgba8(color, 40, y, pixel) && all_ok;
                    const int decoded = tc_picking_rgb_to_id(int(std::lround(pixel[0] * 255)),
                                                            int(std::lround(pixel[1] * 255)),
                                                            int(std::lround(pixel[2] * 255)));
                    if (decoded) winner = decoded;
                }
                all_ok = all_ok && order.size() == 2 &&
                         (winner == int(coplanar_ids[0]) || winner == int(coplanar_ids[1]));
                if (!enabled) {
                    baseline_order = order;
                    baseline_winner = winner;
                } else {
                    const bool matches = order == baseline_order && winner == baseline_winner;
                    if (!matches)
                        std::fprintf(stderr, "IdPass culling reordered coplanar survivors: winner %d -> %d\n",
                                     baseline_winner, winner);
                    all_ok = all_ok && matches;
                }
            }
            termin::set_render_item_culling_enabled(true);
        }
        pass.destroy();
        device->destroy(depth);
        device->destroy(color);
        return all_ok ? 0 : 1;
    }

} // namespace

int main(int argc, char** argv) {
    std::printf("--- termin-render-passes IdPass line pixel smoke ---\n");

    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }

    termin::bootstrap::bootstrap_runtime();

    const int line_result = run_smoke(argc > 0 ? argv[0] : nullptr);
    const int world_text_result = run_world_text_smoke(argc > 0 ? argv[0] : nullptr);

    const int batch_result = run_batched_mesh_smoke(argc > 0 ? argv[0] : nullptr);

    termin::bootstrap::shutdown_runtime();
    return line_result != 0 || world_text_result != 0 || batch_result != 0 ? 1 : 0;
}
