#include <termin/foliage/foliage_data_registry.hpp>
#include <termin/foliage/foliage_layer_component.hpp>
#include <termin/render/depth_pass.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/id_pass.hpp>
#include <termin/render/normal_pass.hpp>
#include <termin/tc_scene.hpp>

#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
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

bool existing_file(const std::filesystem::path& path)
{
    std::error_code ec;
    return std::filesystem::is_regular_file(path, ec);
}

void configure_shader_artifacts(const char* argv0, const std::filesystem::path& root)
{
    std::vector<std::filesystem::path> candidates;
    if (const char* configured = std::getenv("TERMIN_SHADERC")) {
        if (configured[0] != '\0') candidates.emplace_back(configured);
    }
    if (argv0 && argv0[0] != '\0') {
        std::error_code ec;
        const std::filesystem::path exe_dir =
            std::filesystem::absolute(argv0, ec).parent_path();
        if (!ec) candidates.push_back(exe_dir / "termin_shaderc");
    }
    if (const char* sdk = std::getenv("TERMIN_SDK")) {
        if (sdk[0] != '\0') {
            candidates.push_back(
                std::filesystem::path(sdk) / "bin" / "termin_shaderc");
        }
    }
    candidates.push_back(
        std::filesystem::current_path() / "sdk" / "bin" / "termin_shaderc");
    for (const std::filesystem::path& candidate : candidates) {
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
    ~ScopedTempDirectory() { std::filesystem::remove_all(path); }
};

termin::TcMesh create_quad_mesh()
{
    const float vertices[] = {
        -0.55f, -0.55f, 0.0f,  0.0f, 0.0f, 1.0f,  0.0f, 0.0f,
         0.55f, -0.55f, 0.0f,  0.0f, 0.0f, 1.0f,  1.0f, 0.0f,
         0.55f,  0.55f, 0.0f,  0.0f, 0.0f, 1.0f,  1.0f, 1.0f,
        -0.55f,  0.55f, 0.0f,  0.0f, 0.0f, 1.0f,  0.0f, 1.0f,
    };
    const uint32_t indices[] = {0, 2, 1, 0, 3, 2};
    tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv();
    termin::TcMeshCreateInfo info;
    info.data = termin::TcMeshInterleavedDataView{
        vertices, 4, indices, 6, &layout};
    info.name = "foliage-auxiliary-pass-pixel-quad";
    info.uuid_hint = "foliage-auxiliary-pass-pixel-quad";
    return termin::TcMesh::from_interleaved(info);
}

termin::TcMaterial create_material()
{
    termin::TcMaterial material = termin::TcMaterial::create(
        "FoliageAuxiliaryPassPixelMaterial",
        "foliage-auxiliary-pass-pixel-material");
    if (!material.is_valid()) return {};
    tc_material_phase* phase = material.add_phase(
        tc_shader_handle_invalid(), "opaque", 0);
    if (!phase) return {};
    phase->state = tc_render_state_opaque();
    phase->state.cull = 0;
    return material;
}

termin::TcSceneRef create_scene(uint32_t& out_pick_id)
{
    termin::FoliageLayerComponent::register_type();
    termin::TcFoliageData::clear_registry_for_tests();
    termin::TcFoliageData foliage = termin::TcFoliageData::declare(
        "foliage-auxiliary-pass-pixel-data",
        "foliage-auxiliary-pass-pixel-data");
    if (!foliage.is_valid() || !foliage.get()) return {};
    foliage.get()->loaded = true;
    foliage.get()->set_instances({termin::FoliageInstance{
        .px = 0.0f,
        .py = 0.0f,
        .pz = 0.0f,
        .nx = 0.0f,
        .ny = 0.0f,
        .nz = 1.0f,
        .yaw = 0.0f,
        .scale = 1.0f,
        .variant = 0,
        .seed = 1,
    }});

    termin::TcMesh mesh = create_quad_mesh();
    termin::TcMaterial material = create_material();
    if (!mesh.is_valid() || !material.is_valid()) return {};

    termin::TcSceneRef scene = termin::TcSceneRef::create(
        "foliage-auxiliary-pass-pixel-scene");
    termin::Entity entity = scene.create_entity("PickableFoliage");
    if (!entity.valid()) return {};
    entity.set_pickable(true);
    out_pick_id = entity.pick_id();
    auto* layer = new termin::FoliageLayerComponent();
    layer->foliage_uuid = foliage.uuid();
    layer->prototype_mesh = mesh;
    layer->material = material;
    entity.add_component(layer);
    return scene;
}

tgfx::TextureHandle create_color(
    tgfx::IRenderDevice& device,
    tgfx::PixelFormat format = tgfx::PixelFormat::RGBA8_UNorm)
{
    tgfx::TextureDesc desc;
    desc.width = kWidth;
    desc.height = kHeight;
    desc.format = format;
    desc.usage = tgfx::TextureUsage::ColorAttachment |
                 tgfx::TextureUsage::CopySrc;
    return device.create_texture(desc);
}

tgfx::TextureHandle create_depth(tgfx::IRenderDevice& device)
{
    tgfx::TextureDesc desc;
    desc.width = kWidth;
    desc.height = kHeight;
    desc.format = tgfx::PixelFormat::D32F;
    desc.usage = tgfx::TextureUsage::DepthStencilAttachment |
                 tgfx::TextureUsage::CopySrc;
    return device.create_texture(desc);
}

bool matches_pick_color(uint32_t pick_id, const float pixel[4])
{
    int r = 0;
    int g = 0;
    int b = 0;
    tc_picking_id_to_rgb(pick_id, &r, &g, &b);
    constexpr float tolerance = 2.0f / 255.0f;
    return std::abs(pixel[0] - static_cast<float>(r) / 255.0f) <= tolerance &&
           std::abs(pixel[1] - static_cast<float>(g) / 255.0f) <= tolerance &&
           std::abs(pixel[2] - static_cast<float>(b) / 255.0f) <= tolerance;
}

termin::ExecuteContext make_context(
    tgfx::RenderContext2& render_context,
    const termin::TcSceneRef& scene,
    termin::RenderSceneItemSnapshot& snapshot)
{
    termin::ExecuteContext context;
    context.ctx2 = &render_context;
    context.scene = scene;
    context.render_item_snapshot = &snapshot;
    context.render_rect = {
        0, 0, static_cast<int>(kWidth), static_cast<int>(kHeight)};
    context.layer_mask = UINT64_MAX;
    context.render_category_mask = UINT64_MAX;
    return context;
}

bool run_id_pass(
    tgfx::IRenderDevice& device,
    tgfx::RenderContext2& render_context,
    const termin::TcSceneRef& scene,
    uint32_t pick_id)
{
    const tgfx::TextureHandle color = create_color(device);
    const tgfx::TextureHandle depth = create_depth(device);
    if (!color || !depth) return false;
    termin::RenderSceneItemSnapshot snapshot;
    termin::ExecuteContext context = make_context(render_context, scene, snapshot);
    context.tex2_writes.emplace("id", color);
    context.tex2_depth_writes.emplace("id", depth);
    termin::IdPass pass("empty", "id", "FoliageIdPixelSmoke");

    render_context.begin_frame();
    pass.execute_with_data_tgfx2(
        context,
        context.render_rect,
        scene.handle(),
        termin::Mat44f::identity(),
        termin::Mat44f::identity(),
        termin::Vec3::zero(),
        UINT64_MAX);
    render_context.end_frame();
    device.wait_idle();
    float center[4]{};
    float corner[4]{};
    const bool ok = device.read_pixel_rgba8(
                        color, kWidth / 2, kHeight / 2, center) &&
                    device.read_pixel_rgba8(color, 0, 0, corner) &&
                    matches_pick_color(pick_id, center) &&
                    center[3] > 0.95f && corner[3] < 0.05f;
    if (!ok) {
        std::fprintf(stderr, "IdPass: draws=%zu center=(%.3f %.3f %.3f %.3f) corner=(%.3f %.3f %.3f %.3f)\n",
                     pass.entity_names.size(), center[0], center[1], center[2], center[3],
                     corner[0], corner[1], corner[2], corner[3]);
    }
    pass.destroy();
    device.destroy(depth);
    device.destroy(color);
    return ok;
}

bool run_depth_pass(
    tgfx::IRenderDevice& device,
    tgfx::RenderContext2& render_context,
    const termin::TcSceneRef& scene)
{
    const tgfx::TextureHandle color = create_color(device);
    const tgfx::TextureHandle depth = create_depth(device);
    if (!color || !depth) return false;
    termin::RenderSceneItemSnapshot snapshot;
    termin::ExecuteContext context = make_context(render_context, scene, snapshot);
    context.tex2_writes.emplace("depth", color);
    context.tex2_depth_writes.emplace("depth", depth);
    termin::DepthPass pass("empty_depth", "depth", "FoliageDepthPixelSmoke");
    termin::DepthPassExecuteData data;
    data.rect = context.render_rect;
    data.scene = scene.handle();
    data.view = termin::Mat44f::identity();
    data.projection = termin::Mat44f::identity();
    data.near_plane = 0.1f;
    data.far_plane = 100.0f;
    data.layer_mask = UINT64_MAX;

    render_context.begin_frame();
    pass.execute_with_data_tgfx2(context, data);
    render_context.end_frame();
    device.wait_idle();
    float center_depth = 1.0f;
    float corner_depth = 0.0f;
    const bool ok = device.read_pixel_depth_float(
                        depth, kWidth / 2, kHeight / 2, &center_depth) &&
                    device.read_pixel_depth_float(depth, 0, 0, &corner_depth) &&
                    center_depth < 0.75f && corner_depth > 0.95f;
    if (!ok) {
        std::fprintf(stderr, "DepthPass: draws=%zu center=%.6f corner=%.6f\n",
                     pass.entity_names.size(), center_depth, corner_depth);
    }
    pass.destroy();
    device.destroy(depth);
    device.destroy(color);
    return ok;
}

bool run_depth_only_pass(
    tgfx::IRenderDevice& device,
    tgfx::RenderContext2& render_context,
    const termin::TcSceneRef& scene)
{
    const tgfx::TextureHandle depth = create_depth(device);
    if (!depth) return false;
    termin::RenderSceneItemSnapshot snapshot;
    termin::ExecuteContext context = make_context(render_context, scene, snapshot);
    termin::RenderCamera camera;
    context.camera = &camera;
    context.tex2_depth_writes.emplace("depth_only", depth);
    termin::DepthOnlyPass pass("depth_only", "FoliageDepthOnlyPixelSmoke");

    render_context.begin_frame();
    pass.execute(context);
    render_context.end_frame();
    device.wait_idle();
    float center_depth = 1.0f;
    float corner_depth = 0.0f;
    const bool ok = device.read_pixel_depth_float(
                        depth, kWidth / 2, kHeight / 2, &center_depth) &&
                    device.read_pixel_depth_float(depth, 0, 0, &corner_depth) &&
                    center_depth < 0.75f && corner_depth > 0.95f;
    if (!ok) {
        std::fprintf(stderr, "DepthOnlyPass: draws=%zu center=%.6f corner=%.6f\n",
                     pass.entity_names.size(), center_depth, corner_depth);
    }
    pass.destroy();
    device.destroy(depth);
    return ok;
}

bool run_normal_pass(
    tgfx::IRenderDevice& device,
    tgfx::RenderContext2& render_context,
    const termin::TcSceneRef& scene)
{
    const tgfx::TextureHandle color = create_color(device);
    const tgfx::TextureHandle depth = create_depth(device);
    if (!color || !depth) return false;
    termin::RenderSceneItemSnapshot snapshot;
    termin::ExecuteContext context = make_context(render_context, scene, snapshot);
    context.tex2_writes.emplace("normal", color);
    context.tex2_depth_writes.emplace("normal", depth);
    termin::NormalPass pass("empty_normal", "normal", "FoliageNormalPixelSmoke");

    render_context.begin_frame();
    pass.execute_with_data_tgfx2(
        context,
        context.render_rect,
        scene.handle(),
        termin::Mat44f::identity(),
        termin::Mat44f::identity(),
        UINT64_MAX);
    render_context.end_frame();
    device.wait_idle();
    float center[4]{};
    float corner[4]{};
    const bool ok = device.read_pixel_rgba8(
                        color, kWidth / 2, kHeight / 2, center) &&
                    device.read_pixel_rgba8(color, 0, 0, corner) &&
                    center[0] > 0.45f && center[0] < 0.55f &&
                    center[1] > 0.45f && center[1] < 0.55f &&
                    center[2] > 0.95f && corner[2] < 0.55f;
    if (!ok) {
        std::fprintf(stderr, "NormalPass: draws=%zu center=(%.3f %.3f %.3f %.3f) corner=(%.3f %.3f %.3f %.3f)\n",
                     pass.entity_names.size(), center[0], center[1], center[2], center[3],
                     corner[0], corner[1], corner[2], corner[3]);
    }
    pass.destroy();
    device.destroy(depth);
    device.destroy(color);
    return ok;
}

int run_smoke(const char* argv0)
{
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const ScopedTempDirectory artifact_root{
        std::filesystem::temp_directory_path() /
        ("termin-foliage-auxiliary-pass-pixel-smoke-" +
         std::to_string(unique))};
    configure_shader_artifacts(argv0, artifact_root.path);

    uint32_t pick_id = 0;
    termin::TcSceneRef scene = create_scene(pick_id);
    if (!scene.valid() || pick_id == 0) {
        std::fprintf(stderr, "Failed to create foliage pixel test scene\n");
        return 1;
    }

    std::unique_ptr<tgfx::IRenderDevice> device;
    try {
        device = tgfx::create_device(tgfx::BackendType::Vulkan);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Failed to create Vulkan device: %s\n", error.what());
        return 1;
    }
    tgfx::PipelineCache cache(*device);
    tgfx::RenderContext2 render_context(*device, cache);

    const bool id_ok = run_id_pass(*device, render_context, scene, pick_id);
    const bool depth_ok = run_depth_pass(*device, render_context, scene);
    const bool depth_only_ok = run_depth_only_pass(*device, render_context, scene);
    const bool normal_ok = run_normal_pass(*device, render_context, scene);
    termin::TcFoliageData::clear_registry_for_tests();
    if (!id_ok || !depth_ok || !depth_only_ok || !normal_ok) {
        std::fprintf(
            stderr,
            "Foliage auxiliary pass pixel smoke failed: id=%s depth=%s depth_only=%s normal=%s\n",
            id_ok ? "ok" : "failed",
            depth_ok ? "ok" : "failed",
            depth_only_ok ? "ok" : "failed",
            normal_ok ? "ok" : "failed");
        return 1;
    }
    return 0;
}

} // namespace

int main(int argc, char** argv)
{
    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }
    tc_shader_init();
    tc_material_init();
    tc_mesh_init();
    tc_scene_pool_init();
    const int result = run_smoke(argc > 0 ? argv[0] : nullptr);
    tc_scene_pool_shutdown();
    tc_mesh_shutdown();
    tc_material_shutdown();
    tc_shader_shutdown();
    return result;
}
