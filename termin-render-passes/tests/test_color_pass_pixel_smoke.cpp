#include <termin/render/color_pass.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/camera/camera_component.hpp>
#include <termin/tc_scene.hpp>

#include <components/mesh_component.hpp>

#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <core/tc_scene_pool.h>
}

#include <chrono>
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

constexpr const char* kColorPassSmokeShader = R"(
import termin_prelude;

struct PerFrame {
    column_major float4x4 u_view;
    column_major float4x4 u_projection;
    column_major float4x4 u_view_projection;
    column_major float4x4 u_inv_view;
    column_major float4x4 u_inv_proj;
    float4 u_camera_position;
    float2 u_resolution;
    float u_near;
    float u_far;
};

[[TerminScope("frame")]]
ConstantBuffer<PerFrame> per_frame;

struct DrawData {
    column_major float4x4 u_model;
};

[[TerminScope("draw")]]
ConstantBuffer<DrawData> draw_data;

struct SmokeMaterial {
    float4 u_color;
};

[[TerminScope("material")]]
ConstantBuffer<SmokeMaterial> material;

struct VertexInput {
    float3 position : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
    float4 tangent : TANGENT;
};

struct VertexOutput {
    float4 position : SV_Position;
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
    float2 uv : TEXCOORD2;
    float3 tangent_world : TEXCOORD3;
    float3 bitangent_world : TEXCOORD4;
    float tbn_valid : TEXCOORD5;
};

[shader("vertex")]
VertexOutput vs_main(VertexInput input) {
    VertexOutput output;
    float4 world = mul(draw_data.u_model, float4(input.position, 1.0));
    output.position = termin_to_native_clip(mul(per_frame.u_view_projection, world));
    output.world_pos = world.xyz;
    output.normal_world = input.normal;
    output.uv = input.uv;
    output.tangent_world = input.tangent.xyz;
    output.bitangent_world = cross(input.normal, input.tangent.xyz) * input.tangent.w;
    output.tbn_valid = 1.0;
    return output;
}

struct FragmentInput {
    float4 screen_pos : SV_Position;
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
    float2 uv : TEXCOORD2;
    float3 tangent_world : TEXCOORD3;
    float3 bitangent_world : TEXCOORD4;
    float tbn_valid : TEXCOORD5;
};

struct FragmentOutput {
    float4 color : SV_Target0;
};

[shader("fragment")]
FragmentOutput fs_main(FragmentInput input) {
    FragmentOutput output;
    output.color = material.u_color + float4(input.uv * 0.0, 0.0, 0.0);
    return output;
}
)";

struct SmokeVertex {
    float position[3];
    float normal[3];
    float uv[2];
    float tangent[4];
};

bool matches_clear_color(const float pixel[4]) {
    return pixel[0] >= 0.00f && pixel[0] < 0.08f &&
           pixel[1] >= 0.01f && pixel[1] < 0.09f &&
           pixel[2] >= 0.02f && pixel[2] < 0.10f &&
           pixel[3] > 0.95f;
}

bool matches_material_color(const float pixel[4]) {
    return pixel[0] > 0.08f && pixel[0] < 0.18f &&
           pixel[1] > 0.66f && pixel[1] < 0.80f &&
           pixel[2] > 0.18f && pixel[2] < 0.32f &&
           pixel[3] > 0.95f;
}

void print_pixel(const char* label, const float pixel[4]) {
    std::printf(
        "%s: (%.3f %.3f %.3f %.3f)\n",
        label,
        pixel[0],
        pixel[1],
        pixel[2],
        pixel[3]);
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
        const std::filesystem::path exe_dir =
            std::filesystem::absolute(argv0, ec).parent_path();
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

termin::TcShader create_color_shader() {
    termin::TcShaderCreateInfo create_info{};
    create_info.sources.vertex = kColorPassSmokeShader;
    create_info.sources.fragment = kColorPassSmokeShader;
    create_info.sources.name = "ColorPassPixelSmokeMaterialShader";
    create_info.sources.vertex_entry = "vs_main";
    create_info.sources.fragment_entry = "fs_main";
    create_info.language = TC_SHADER_LANGUAGE_SLANG;
    create_info.artifact_policy = TC_SHADER_ARTIFACT_REQUIRED;
    return termin::TcShader::from_sources(create_info);
}

termin::TcMaterial create_color_material(const termin::TcShader& shader) {
    termin::TcMaterial material = termin::TcMaterial::create(
        "ColorPassPixelSmokeMaterial",
        "termin-color-pass-pixel-smoke-material");
    if (!material.is_valid()) {
        return {};
    }

    tc_material_phase* phase = material.add_phase(shader.handle, "opaque", 0);
    if (!phase) {
        return {};
    }

    phase->state = tc_render_state_opaque();
    phase->state.cull = 0;
    phase->state.depth_test = 0;
    phase->state.depth_write = 0;

    const float color[4] = {0.12f, 0.72f, 0.24f, 1.0f};
    tc_material_phase_set_uniform(phase, "u_color", TC_UNIFORM_VEC4, color);
    return material;
}

termin::TcMesh create_triangle_mesh() {
    const SmokeVertex vertices[] = {
        {{-0.65f, -0.65f, 0.0f}, {0.0f, 0.0f, 1.0f}, {0.0f, 0.0f}, {1.0f, 0.0f, 0.0f, 1.0f}},
        {{ 0.65f, -0.65f, 0.0f}, {0.0f, 0.0f, 1.0f}, {1.0f, 0.0f}, {1.0f, 0.0f, 0.0f, 1.0f}},
        {{ 0.00f,  0.65f, 0.0f}, {0.0f, 0.0f, 1.0f}, {0.5f, 1.0f}, {1.0f, 0.0f, 0.0f, 1.0f}},
    };
    const uint32_t indices[] = {0, 1, 2};
    tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv_tangent();

    termin::TcMeshCreateInfo create_info;
    create_info.data = termin::TcMeshInterleavedDataView{
        vertices,
        3,
        indices,
        3,
        &layout};
    create_info.name = "ColorPassPixelSmokeTriangle";
    create_info.uuid_hint = "termin-color-pass-pixel-smoke-triangle";
    return termin::TcMesh::from_interleaved(create_info);
}

termin::TcSceneRef create_scene(
    const termin::TcMesh& mesh,
    const termin::TcMaterial& material) {
    termin::MeshComponent::register_type();
    termin::MeshRenderer::register_type();

    termin::TcSceneRef scene = termin::TcSceneRef::create("color-pass-pixel-smoke");
    termin::Entity entity = scene.create_entity("ColorPassSmokeTriangle");
    if (!entity.valid()) {
        return {};
    }

    auto* mesh_component = new termin::MeshComponent();
    mesh_component->set_mesh(mesh);
    entity.add_component(mesh_component);

    auto* renderer = new termin::MeshRenderer();
    renderer->set_material(material);
    entity.add_component(renderer);

    termin::Entity camera_entity = scene.create_entity("ColorPassNamedCamera");
    if (!camera_entity.valid()) {
        return {};
    }
    auto* camera = new termin::CameraComponent();
    camera_entity.add_component(camera);

    return scene;
}

int run_smoke(const char* argv0) {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const ScopedTempDirectory artifact_root{
        std::filesystem::temp_directory_path() /
        ("termin-render-passes-color-pass-pixel-smoke-" + std::to_string(unique))
    };
    std::filesystem::remove_all(artifact_root.path);
    configure_shader_artifacts(argv0, artifact_root.path);

    termin::TcShader shader = create_color_shader();
    if (!shader.is_valid()) {
        std::fprintf(stderr, "Failed to create ColorPass smoke shader\n");
        return 1;
    }

    termin::TcMaterial material = create_color_material(shader);
    if (!material.is_valid()) {
        std::fprintf(stderr, "Failed to create ColorPass smoke material\n");
        return 1;
    }

    termin::TcMesh mesh = create_triangle_mesh();
    if (!mesh.is_valid()) {
        std::fprintf(stderr, "Failed to create ColorPass smoke mesh\n");
        return 1;
    }

    termin::TcSceneRef scene = create_scene(mesh, material);
    if (!scene.valid()) {
        std::fprintf(stderr, "Failed to create ColorPass smoke scene\n");
        return 1;
    }

    std::unique_ptr<tgfx::IRenderDevice> device;
    try {
        device = tgfx::create_device(tgfx::BackendType::Vulkan);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Failed to create Vulkan device: %s\n", e.what());
        return 1;
    }

    tgfx::TextureDesc target_desc;
    target_desc.width = kWidth;
    target_desc.height = kHeight;
    target_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
    target_desc.usage =
        tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
    tgfx::TextureHandle target = device->create_texture(target_desc);
    if (!target) {
        std::fprintf(stderr, "Failed to create output texture\n");
        return 1;
    }

    tgfx::PipelineCache cache(*device);
    tgfx::RenderContext2 render_ctx(*device, cache);
    termin::ColorPassConfig pass_config;
    pass_config.input_res = "empty";
    pass_config.output_res = "color";
    pass_config.shadow_res = "";
    pass_config.phase_mark = "opaque";
    pass_config.pass_name = "ColorPassPixelSmoke";
    pass_config.camera_name = "ColorPassNamedCamera";
    termin::ColorPass pass(pass_config);

    termin::RenderSceneItemSnapshot render_item_snapshot;
    termin::ExecuteContext exec_ctx;
    exec_ctx.render_item_snapshot = &render_item_snapshot;
    exec_ctx.ctx2 = &render_ctx;
    exec_ctx.tex2_writes.emplace("color", target);
    exec_ctx.render_rect = {0, 0, static_cast<int>(kWidth), static_cast<int>(kHeight)};
    exec_ctx.scene = scene;

    const float clear_color[4] = {0.02f, 0.03f, 0.04f, 1.0f};
    render_ctx.begin_frame();
    render_ctx.begin_pass(target, {}, clear_color, 1.0f, false);
    render_ctx.end_pass();

    pass.execute(exec_ctx);
    const bool named_camera_reached_draw_collection =
        pass.entity_names.size() == 1 &&
        pass.entity_names[0] == "ColorPassSmokeTriangle";

    termin::ColorPassConfig missing_camera_config = pass_config;
    missing_camera_config.camera_name = "MissingColorPassCamera";
    termin::ColorPass missing_camera_pass(missing_camera_config);
    missing_camera_pass.execute(exec_ctx);
    const bool missing_camera_skipped = missing_camera_pass.entity_names.empty();
    missing_camera_pass.destroy();

    termin::ColorPassExecuteData pass_data;
    pass_data.rect = exec_ctx.render_rect;
    pass_data.scene = scene.handle();
    pass_data.view = termin::Mat44f::identity();
    pass_data.projection = termin::Mat44f::identity();
    pass_data.camera_position = termin::Vec3{0.0, 0.0, 1.0};
    pass_data.ambient_color = termin::Vec3{1.0, 1.0, 1.0};
    pass_data.ambient_intensity = 0.0f;
    pass.execute_with_data(exec_ctx, pass_data);

    render_ctx.end_frame();
    device->wait_idle();

    float center[4] = {};
    float corner[4] = {};
    const bool read_ok =
        device->read_pixel_rgba8(
            target,
            static_cast<int>(kWidth / 2),
            static_cast<int>(kHeight / 2),
            center) &&
        device->read_pixel_rgba8(target, 0, 0, corner);

    print_pixel("center", center);
    print_pixel("top-left", corner);

    const size_t pipeline_cache_size = cache.size();
    const bool entity_seen =
        pass.entity_names.size() == 1 &&
        pass.entity_names[0] == "ColorPassSmokeTriangle";
    const bool pass_ok =
        read_ok &&
        matches_material_color(center) &&
        matches_clear_color(corner) &&
        pipeline_cache_size >= 1 &&
        entity_seen &&
        named_camera_reached_draw_collection &&
        missing_camera_skipped;

    pass.destroy();
    device->destroy(target);

    if (!pass_ok) {
        std::fprintf(
            stderr,
            "ColorPass pixel smoke failed: read_ok=%s cache_size=%zu entity_seen=%s named_camera=%s missing_camera=%s\n",
            read_ok ? "true" : "false",
            pipeline_cache_size,
            entity_seen ? "true" : "false",
            named_camera_reached_draw_collection ? "true" : "false",
            missing_camera_skipped ? "true" : "false");
        return 1;
    }

    return 0;
}

} // namespace

int main(int argc, char** argv) {
    std::printf("--- termin-render-passes ColorPass pixel smoke ---\n");

    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }

    tc_mesh_init();
    tc_shader_init();
    tc_material_init();
    tc_scene_pool_init();

    const int result = run_smoke(argc > 0 ? argv[0] : nullptr);

    tc_scene_pool_shutdown();
    tc_material_shutdown();
    tc_shader_shutdown();
    tc_mesh_shutdown();
    return result;
}
