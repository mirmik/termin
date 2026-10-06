#include <components/mesh_component.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/render_item_culling.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/shadow_pass.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
    using namespace termin;
    constexpr int resolution = 128;

    void require(bool condition, const char* message) {
        if (!condition) {
            throw std::runtime_error(message);
        }
    }

    struct ArtifactConfiguration {
        std::filesystem::path root = std::filesystem::temp_directory_path() /
            ("termin-shadow-culling-pixels-" +
             std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
        ArtifactConfiguration() {
            termin::tgfx2_set_shader_artifact_root(root.string().c_str());
            termin::tgfx2_set_shader_cache_root((root / ".cache").string().c_str());
#ifdef TERMIN_SHADOW_CULLING_PIXEL_SMOKE_SHADERC
            termin::tgfx2_set_shader_compiler_path(TERMIN_SHADOW_CULLING_PIXEL_SMOKE_SHADERC);
#endif
            termin::tgfx2_set_shader_dev_compile_enabled(true);
        }
        ~ArtifactConfiguration() {
            termin::tgfx2_set_shader_dev_compile_enabled(false);
            termin::tgfx2_set_shader_compiler_path("");
            termin::tgfx2_set_shader_artifact_root("");
            termin::tgfx2_set_shader_cache_root("");
            std::filesystem::remove_all(root);
        }
    };

    TcMesh make_double_sided_quad() {
        const float positions[] = {-2, 0, -2, 2, 0, -2, 2, 0, 2, -2, 0, 2};
        // ShadowPass draws back faces. Include both windings so this fixture
        // exercises depth independently of an open plane's facing direction.
        const uint32_t indices[] = {0, 1, 2, 0, 2, 3, 2, 1, 0, 3, 2, 0};
        const tc_vertex_layout layout = tc_vertex_layout_pos();
        TcMeshCreateInfo info;
        info.data = TcMeshInterleavedDataView{positions, 4, indices, 12, &layout};
        info.name = "ShadowCullingQuad";
        info.uuid_hint = "shadow-culling-quad";
        return TcMesh::from_interleaved(info);
    }

    void add_quad(TcSceneRef& scene, const char* name, const TcMesh& mesh, const TcMaterial& material,
                  const Vec3& position, double scale) {
        Entity entity = scene.create_entity(name);
        require(entity.valid(), "Failed to create quad entity");
        entity.transform().set_local_position(position);
        entity.transform().set_local_scale({scale, 1, scale});
        auto* component = new MeshComponent();
        component->set_mesh(mesh);
        entity.add_component(component);
        auto* renderer = new MeshRenderer();
        renderer->set_material(material);
        entity.add_component(renderer);
    }

    struct RenderedCascade {
        Mat44f matrix;
        std::vector<float> depth;
    };

    std::vector<RenderedCascade> render(ShadowPass& pass, ExecuteContext& context,
                                       const ShadowPassExecuteRequest& request, bool culling) {
        set_render_item_culling_enabled(culling);
        clear_render_item_culling_diagnostics();
        context.ctx2->begin_frame();
        const auto results = pass.execute_shadow_pass_tgfx2(context, request);
        context.ctx2->end_frame();
        context.ctx2->device().wait_idle();
        require(results.size() == request.lights[0].shadows.cascade_count, "Missing shadow cascade");
        const bool distant_planned = std::find(pass.entity_names.begin(), pass.entity_names.end(), "DistantCaster") !=
                                     pass.entity_names.end();
        const bool upstream_planned = std::find(pass.entity_names.begin(), pass.entity_names.end(), "UpstreamCaster") !=
                                      pass.entity_names.end();
        require(upstream_planned, "Upstream caster was removed by primary-camera visibility");
        require(distant_planned != culling, "Shadow preparation did not skip the wholly distant caster");
        const auto counters = get_render_item_culling_diagnostics();
        require(counters.size() == results.size(), "Missing per-cascade culling counters");
        for (const auto& counter : counters) {
            require(counter.counters.candidates == 3, "Unexpected shadow candidate count");
            if (culling) {
                require(counter.counters.tested == 3 && counter.counters.culled == 1,
                        "Each cascade must reject only the distant caster");
                require(counter.counters.mesh_draws == 2, "Culling must reduce submitted shadow mesh draws to two");
            } else {
                require(counter.counters.tested == 0 && counter.counters.culled == 0,
                        "Diagnostic disable must bypass culling");
                require(counter.counters.mesh_draws == 3, "Unculled cascades must submit all three mesh draws");
            }
        }
        std::vector<RenderedCascade> rendered;
        for (const auto& result : results) {
            RenderedCascade cascade{result.light_space_matrix, std::vector<float>(resolution * resolution)};
            require(context.ctx2->device().read_texture_depth_float(result.depth_tex2, cascade.depth.data()),
                    "Failed to read shadow depth");
            rendered.push_back(std::move(cascade));
        }
        return rendered;
    }

    void run_smoke() {
        ArtifactConfiguration artifacts;
        std::unique_ptr<tgfx::IRenderDevice> device;
        try {
            device = tgfx::create_device(tgfx::BackendType::Vulkan);
        } catch (const std::exception& error) {
            throw std::runtime_error(std::string("Failed to create Vulkan device: ") + error.what());
        }
        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 render_context(*device, cache);
        TcMesh mesh = make_double_sided_quad();
        require(mesh.is_valid(), "Failed to create shadow quad");
        TcMaterial material = TcMaterial::create("ShadowCullingMaterial", "shadow-culling-material");
        require(material.is_valid(), "Failed to create shadow material");
        // ShadowPass supplies its own static vertex transform and engine depth
        // shader. The material only declares participation in the shadow phase.
        require(material.add_phase(tc_shader_handle_invalid(), "shadow", 0) != nullptr,
                "Failed to declare shadow phase");
        MeshComponent::register_type();
        MeshRenderer::register_type();
        TcSceneRef scene = TcSceneRef::create("shadow-culling-pixels");
        require(scene.valid(), "Failed to create shadow scene");
        add_quad(scene, "UpstreamCaster", mesh, material, {0, -3, 0}, 1);
        add_quad(scene, "VisibleReceiver", mesh, material, {0, 12, 0}, 2);
        add_quad(scene, "DistantCaster", mesh, material, {10000, 12, 0}, 1);
        TcSceneRenderItemSource source(scene.handle());
        RenderItemSnapshot snapshot;
        require(source.publish(snapshot, {}), "Failed to publish shadow snapshot");
        require(snapshot.phase_item_indices(TC_PHASE_SHADOW).size() == 3, "Unexpected shadow phase items");
        for (const auto& item : snapshot.items()) {
            require(item.bounds_state == TC_RENDER_ITEM_BOUNDS_VALID, "Mesh fixture must have valid bounds");
        }
        ExecuteContext context;
        context.ctx2 = &render_context;
        context.render_item_snapshot = &snapshot;
        context.render_target_name = "ShadowCullingPixels";
        ShadowPass pass("shadow_maps", "ShadowCullingPixels", 100);
        Light light;
        light.direction = Vec3::unit_y();
        light.shadows.enabled = true;
        light.shadows.map_resolution = resolution;
        light.shadows.max_distance = 48;
        ShadowPassExecuteRequest request;
        request.scene = scene.handle();
        request.lights = std::span<const Light>(&light, 1);
        request.camera_near = 1;
        request.camera_far = 60;
        request.camera_projection = Mat44::perspective(1.2, 1.3, 1, 60);

        for (int cascade_count : {2, 4}) {
            light.shadows.cascade_count = cascade_count;
            for (double camera_y : {0.0, 4.0}) {
                request.camera_view = Mat44::look_at({0.25, camera_y, 0}, {0.25, camera_y + 1, 0});
                const auto unculled = render(pass, context, request, false);
                const auto culled = render(pass, context, request, true);
                for (size_t c = 0; c < culled.size(); ++c) {
                    for (int i = 0; i < 16; ++i) {
                        require(culled[c].matrix.data[i] == unculled[c].matrix.data[i],
                                "Culling changed the fitted shadow volume");
                    }
                    for (size_t i = 0; i < culled[c].depth.size(); ++i) {
                        require(std::isfinite(culled[c].depth[i]) &&
                                std::abs(culled[c].depth[i] - unculled[c].depth[i]) <= 1e-7f,
                                "Culling changed shadow depth pixels");
                    }
                    const Vec3f caster = culled[c].matrix.transform_point({0, -3, 0});
                    const Vec3f receiver = culled[c].matrix.transform_point({0, 12, 0});
                    const int x = int((receiver.x * 0.5f + 0.5f) * resolution);
                    const int y = int((receiver.y * 0.5f + 0.5f) * resolution);
                    require(x >= 0 && x < resolution && y >= 0 && y < resolution,
                            "Receiver shadow texel lies outside cascade");
                    const float depth = culled[c].depth[size_t(y) * resolution + x];
                    require(std::abs(depth - caster.z) < 1e-4f && depth < receiver.z - 0.01f,
                            "Behind-camera caster does not shadow the visible receiver");
                }
            }
        }
        pass.destroy();
        scene.destroy();
        set_render_item_culling_enabled(true);
    }
}

int main() {
    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }
    tc_mesh_init();
    tc_shader_init();
    tc_material_init();
    tc_scene_pool_init();
    int result = 0;
    try {
        run_smoke();
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Shadow culling pixel smoke failed: %s\n", error.what());
        result = 1;
    }
    tc_scene_pool_shutdown();
    tc_material_shutdown();
    tc_shader_shutdown();
    tc_mesh_shutdown();
    return result;
}
