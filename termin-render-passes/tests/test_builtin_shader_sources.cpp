#include "guard_main.h"

GUARD_TEST_MAIN();

#include "termin/materials/shader_parser.hpp"
#include "tgfx2/builtin_shader_sources.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

#include <array>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace {

void set_builtin_root(const std::filesystem::path& root) {
#ifdef _WIN32
    _putenv_s("TERMIN_BUILTIN_SHADER_ROOT", root.string().c_str());
#else
    setenv("TERMIN_BUILTIN_SHADER_ROOT", root.string().c_str(), 1);
#endif
}

void clear_builtin_root() {
#ifdef _WIN32
    _putenv_s("TERMIN_BUILTIN_SHADER_ROOT", "");
#else
    unsetenv("TERMIN_BUILTIN_SHADER_ROOT");
#endif
}

void write_text(const std::filesystem::path& path, const char* text) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::binary);
    REQUIRE(out.good());
    out << text;
}

const tc_shader_resource_requirement* contract_resource(
    const tc_shader_contract_view& contract,
    const char* name)
{
    for (uint32_t i = 0; i < contract.resource_count; ++i) {
        if (std::strcmp(contract.resources[i].name, name) == 0) {
            return &contract.resources[i];
        }
    }
    return nullptr;
}

void check_contract_resource(
    const tc_shader_contract_view& contract,
    const char* name,
    uint32_t kind,
    uint32_t scope)
{
    const tc_shader_resource_requirement* resource =
        contract_resource(contract, name);
    REQUIRE(resource != nullptr);
    CHECK(resource->kind == kind);
    CHECK(resource->scope == scope);
}

} // namespace

TEST_CASE("built-in fragment shader registration reads source file from resource root") {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::filesystem::path root =
        std::filesystem::temp_directory_path()
        / ("termin-render-passes-builtin-shader-test-" + std::to_string(unique));
    std::filesystem::remove_all(root);

    constexpr const char* kFilename = "termin-engine-tonemap.frag.glsl";
    constexpr const char* kMarker = "TEST_BUILTIN_SHADER_SOURCE_MARKER";
    write_text(
        root / kFilename,
        "#version 450 core\n"
        "// TEST_BUILTIN_SHADER_SOURCE_MARKER\n"
        "layout(location = 0) out vec4 FragColor;\n"
        "void main() { FragColor = vec4(1.0); }\n");

    set_builtin_root(root);
    tc_shader_init();

    tc_shader_handle handle = tgfx::register_builtin_fragment_shader(
        kFilename,
        "TestBuiltinShaderFS",
        "test-builtin-shader-source-uuid");
    REQUIRE(!tc_shader_handle_is_invalid(handle));

    tc_shader* shader = tc_shader_get(handle);
    REQUIRE(shader != nullptr);
    REQUIRE(shader->fragment_source != nullptr);
    CHECK(std::strstr(shader->fragment_source, kMarker) != nullptr);

    tc_shader_shutdown();
    clear_builtin_root();
    std::filesystem::remove_all(root);
}

TEST_CASE("built-in vertex-fragment shader registration reads both source files") {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::filesystem::path root =
        std::filesystem::temp_directory_path()
        / ("termin-render-passes-builtin-vsfs-test-" + std::to_string(unique));
    std::filesystem::remove_all(root);

    constexpr const char* kProgramFilename = "termin-engine-shadow.slang";
    constexpr const char* kVertexMarker = "TEST_BUILTIN_VERTEX_SHADER_SOURCE_MARKER";
    constexpr const char* kFragmentMarker = "TEST_BUILTIN_FRAGMENT_SHADER_SOURCE_MARKER";
    write_text(
        root / kProgramFilename,
        "// TEST_BUILTIN_VERTEX_SHADER_SOURCE_MARKER\n"
        "// TEST_BUILTIN_FRAGMENT_SHADER_SOURCE_MARKER\n"
        "struct In { float3 position : POSITION; };\n"
        "struct Out { float4 position : SV_Position; };\n"
        "[shader(\"vertex\")] Out vs_main(In input) { Out output; output.position = float4(input.position, 1.0); return output; }\n"
        "[shader(\"fragment\")] void fs_main() {}\n");

    set_builtin_root(root);
    tc_shader_init();

    tc_shader_handle handle = tgfx::register_builtin_vertex_fragment_shader(
        kProgramFilename,
        kProgramFilename,
        "TestBuiltinShaderVSFS",
        "test-builtin-vsfs-source-uuid");
    REQUIRE(!tc_shader_handle_is_invalid(handle));

    tc_shader* shader = tc_shader_get(handle);
    REQUIRE(shader != nullptr);
    REQUIRE(shader->vertex_source != nullptr);
    REQUIRE(shader->fragment_source != nullptr);
    CHECK(std::strstr(shader->vertex_source, kVertexMarker) != nullptr);
    CHECK(std::strstr(shader->fragment_source, kFragmentMarker) != nullptr);

    tc_shader_shutdown();
    clear_builtin_root();
    std::filesystem::remove_all(root);
}

TEST_CASE("built-in shader catalog registration resolves fragment-only entry by uuid") {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::filesystem::path root =
        std::filesystem::temp_directory_path()
        / ("termin-render-passes-catalog-fragment-test-" + std::to_string(unique));
    std::filesystem::remove_all(root);

    write_text(
        root / "engine-shader-catalog.json",
        R"({
  "version": 1,
  "shaders": [
    {
      "uuid": "test-catalog-fragment",
      "name": "TestCatalogFragmentFS",
      "language": "glsl",
      "stages": {
        "fragment": {"path": "catalog-fragment-source.frag.glsl"}
      }
    }
  ]
})");
    write_text(
        root / "catalog-fragment-source.frag.glsl",
        "#version 450 core\n"
        "// TEST_CATALOG_FRAGMENT_MARKER\n"
        "layout(location = 0) out vec4 FragColor;\n"
        "void main() { FragColor = vec4(1.0); }\n");

    set_builtin_root(root);
    tc_shader_init();

    tc_shader_handle handle =
        tgfx::register_builtin_shader_from_catalog("test-catalog-fragment");
    REQUIRE(!tc_shader_handle_is_invalid(handle));

    tc_shader* shader = tc_shader_get(handle);
    REQUIRE(shader != nullptr);
    CHECK(shader->vertex_source == nullptr);
    REQUIRE(shader->fragment_source != nullptr);
    CHECK(std::strstr(shader->fragment_source, "TEST_CATALOG_FRAGMENT_MARKER") != nullptr);
    CHECK(std::strcmp(shader->name, "TestCatalogFragmentFS") == 0);

    tc_shader_contract_view contract{};
    CHECK(!tc_shader_get_contract_view(shader, &contract));
    CHECK(!tc_shader_has_resource_layout(shader));

    tc_shader_shutdown();
    clear_builtin_root();
    std::filesystem::remove_all(root);
}

TEST_CASE("built-in shader catalog registration resolves vertex-fragment entry by uuid") {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::filesystem::path root =
        std::filesystem::temp_directory_path()
        / ("termin-render-passes-catalog-vsfs-test-" + std::to_string(unique));
    std::filesystem::remove_all(root);

    write_text(
        root / "engine-shader-catalog.json",
        R"({
  "version": 1,
  "shaders": [
    {
      "uuid": "test-catalog-vsfs",
      "name": "TestCatalogVSFS",
      "language": "glsl",
      "stages": {
        "vertex": {
          "path": "test-catalog.vert.glsl"
        },
        "fragment": {"path": "test-catalog.frag.glsl"}
      }
    }
  ]
})");
    write_text(
        root / "test-catalog.vert.glsl",
        "#version 450 core\n"
        "// TEST_CATALOG_VERTEX_MARKER\n"
        "layout(location = 0) in vec3 a_position;\n"
        "void main() { gl_Position = vec4(a_position, 1.0); }\n");
    write_text(
        root / "test-catalog.frag.glsl",
        "#version 450 core\n"
        "// TEST_CATALOG_FRAGMENT_MARKER\n"
        "void main() {}\n");

    set_builtin_root(root);
    tc_shader_init();

    tc_shader_handle handle = tgfx::register_builtin_shader_from_catalog("test-catalog-vsfs");
    REQUIRE(!tc_shader_handle_is_invalid(handle));

    tc_shader* shader = tc_shader_get(handle);
    REQUIRE(shader != nullptr);
    REQUIRE(shader->vertex_source != nullptr);
    REQUIRE(shader->fragment_source != nullptr);
    CHECK(std::strstr(shader->vertex_source, "TEST_CATALOG_VERTEX_MARKER") != nullptr);
    CHECK(std::strstr(shader->fragment_source, "TEST_CATALOG_FRAGMENT_MARKER") != nullptr);
    CHECK(std::strcmp(shader->name, "TestCatalogVSFS") == 0);

    tc_shader_contract_view contract{};
    CHECK(!tc_shader_get_contract_view(shader, &contract));
    CHECK(!tc_shader_has_resource_layout(shader));

    tc_shader_shutdown();
    clear_builtin_root();
    std::filesystem::remove_all(root);
}

TEST_CASE("shader layout sidecar attaches reflected shader contract") {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::filesystem::path root =
        std::filesystem::temp_directory_path()
        / ("termin-render-passes-sidecar-contract-test-" + std::to_string(unique));
    const std::filesystem::path artifact_root = root / "artifacts";
    std::filesystem::remove_all(root);

    write_text(
        root / "engine-shader-catalog.json",
        R"({
  "version": 1,
  "shaders": [
    {
      "uuid": "test-sidecar-fragment",
      "name": "TestSidecarFragmentFS",
      "language": "slang",
      "stages": {
        "fragment": {
          "path": "sidecar-fragment-source.frag.slang",
          "entry": "fs_main"
        }
      }
    }
  ]
})");
    write_text(
        root / "sidecar-fragment-source.frag.slang",
        "// TEST_SIDECAR_FRAGMENT_MARKER\n"
        "struct In { float2 uv : TEXCOORD0; };\n"
        "[shader(\"fragment\")] float4 fs_main(In input) : SV_Target0 { return float4(input.uv, 0.0, 1.0); }\n");

    const std::filesystem::path artifact =
        artifact_root / "shaders" / "opengl" / "test-sidecar-fragment.frag.glsl";
    write_text(
        artifact,
        "#version 450 core\n"
        "// TEST_SIDECAR_ARTIFACT_MARKER\n");
    write_text(
        std::filesystem::path(artifact.string() + ".layout.json"),
        R"({
  "version": 1,
  "language": "slang",
  "target": "opengl",
  "stage": "fragment",
  "resources": [
    {
      "name": "u_params",
      "kind": "constant_buffer",
      "scope": "unscoped",
      "set": 0,
      "binding": 0,
      "stage_mask": 2,
      "size": 16,
      "fields": [
        {"name": "threshold", "type": "Float", "offset": 0, "size": 4}
      ]
    },
    {
      "name": "u_texture",
      "kind": "texture",
      "scope": "transient",
      "set": 0,
      "binding": 32,
      "stage_mask": 2,
      "size": 0
    }
  ]
})");

    set_builtin_root(root);
    termin::tgfx2_set_shader_artifact_root(artifact_root.string().c_str());
    termin::tgfx2_set_shader_dev_compile_enabled(false);
    tc_shader_init();

    tc_shader_handle handle =
        tgfx::register_builtin_shader_from_catalog("test-sidecar-fragment");
    REQUIRE(!tc_shader_handle_is_invalid(handle));
    tc_shader* shader = tc_shader_get(handle);
    REQUIRE(shader != nullptr);

    tc_shader_contract_view before{};
    CHECK(!tc_shader_get_contract_view(shader, &before));
    CHECK(!tc_shader_has_resource_layout(shader));

    std::vector<uint8_t> artifact_bytes;
    REQUIRE(termin::tgfx2_load_or_compile_shader_artifact_for_backend(
        shader,
        tgfx::BackendType::OpenGL,
        tgfx::ShaderStage::Fragment,
        artifact_bytes));
    REQUIRE(!artifact_bytes.empty());
    CHECK(tc_shader_has_resource_layout(shader));

    tc_shader_contract_view contract{};
    REQUIRE(tc_shader_get_contract_view(shader, &contract));
    CHECK(contract.source_kind == TC_SHADER_CONTRACT_SOURCE_REFLECTION);
    CHECK(contract.vertex_input_count == 0);
    check_contract_resource(
        contract,
        "u_params",
        TC_SHADER_RESOURCE_CONSTANT_BUFFER,
        TC_SHADER_RESOURCE_SCOPE_UNSCOPED);
    const tc_shader_resource_requirement* params =
        contract_resource(contract, "u_params");
    REQUIRE(params != nullptr);
    CHECK(params->size == 16);
    REQUIRE(params->field_count == 1);
    CHECK(std::strcmp(params->fields[0].name, "threshold") == 0);
    check_contract_resource(
        contract,
        "u_texture",
        TC_SHADER_RESOURCE_TEXTURE,
        TC_SHADER_RESOURCE_SCOPE_TRANSIENT);
    REQUIRE(tc_shader_find_resource_binding(shader, "u_texture") != nullptr);

    tc_shader_shutdown();
    termin::tgfx2_set_shader_artifact_root("");
    clear_builtin_root();
    std::filesystem::remove_all(root);
}

TEST_CASE("built-in shader catalog resolves shader program source by uuid") {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::filesystem::path root =
        std::filesystem::temp_directory_path()
        / ("termin-render-passes-catalog-program-test-" + std::to_string(unique));
    std::filesystem::remove_all(root);

    write_text(
        root / "engine-shader-catalog.json",
        R"({
  "version": 1,
  "shaders": [
    {
      "uuid": "test-catalog-program",
      "name": "TestCatalogProgram",
      "language": "shader",
      "program": {"path": "catalog-program-source.shader"}
    }
  ]
})");
    write_text(
        root / "catalog-program-source.shader",
        "@program TestCatalogProgram\n"
        "// TEST_CATALOG_PROGRAM_MARKER\n");

    set_builtin_root(root);

    tgfx::BuiltinShaderProgramSource program =
        tgfx::load_builtin_shader_program_from_catalog("test-catalog-program");
    CHECK(program.name == "TestCatalogProgram");
    REQUIRE(!program.source.empty());
    CHECK(program.source.find("TEST_CATALOG_PROGRAM_MARKER") != std::string::npos);

    clear_builtin_root();
    std::filesystem::remove_all(root);
}

TEST_CASE("built-in shader convention resolves canonical files without catalog manifest") {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::filesystem::path root =
        std::filesystem::temp_directory_path()
        / ("termin-render-passes-convention-shader-test-" + std::to_string(unique));
    std::filesystem::remove_all(root);

    write_text(
        root / "test-convention-vsfs.slang",
        "// TEST_CONVENTION_VSFS_MARKER\n"
        "struct In { float3 position : POSITION; };\n"
        "struct Out { float4 position : SV_Position; };\n"
        "[shader(\"vertex\")] Out vs_main(In input) { Out output; output.position = float4(input.position, 1.0); return output; }\n"
        "[shader(\"fragment\")] float4 fs_main() : SV_Target0 { return float4(1.0); }\n");
    write_text(
        root / "test-convention-stage.frag.slang",
        "// TEST_CONVENTION_FRAGMENT_STAGE_MARKER\n"
        "[shader(\"fragment\")] float4 fs_main() : SV_Target0 { return float4(1.0); }\n");
    write_text(
        root / "test-convention-program.shader",
        "@program TestConventionProgram\n"
        "// TEST_CONVENTION_PROGRAM_MARKER\n");

    set_builtin_root(root);
    tc_shader_init();

    tc_shader_handle handle =
        tgfx::register_builtin_shader_from_catalog("test-convention-vsfs");
    REQUIRE(!tc_shader_handle_is_invalid(handle));

    tc_shader* shader = tc_shader_get(handle);
    REQUIRE(shader != nullptr);
    CHECK(std::strcmp(shader->uuid, "test-convention-vsfs") == 0);
    REQUIRE(shader->name != nullptr);
    CHECK(std::strcmp(shader->name, "test-convention-vsfs") == 0);
    REQUIRE(shader->vertex_source != nullptr);
    REQUIRE(shader->fragment_source != nullptr);
    CHECK(std::strstr(shader->vertex_source, "TEST_CONVENTION_VSFS_MARKER") != nullptr);
    CHECK(std::strstr(shader->fragment_source, "TEST_CONVENTION_VSFS_MARKER") != nullptr);
    REQUIRE(shader->vertex_entry != nullptr);
    REQUIRE(shader->fragment_entry != nullptr);
    CHECK(std::strcmp(shader->vertex_entry, "vs_main") == 0);
    CHECK(std::strcmp(shader->fragment_entry, "fs_main") == 0);

    std::string fragment_stage =
        tgfx::load_builtin_shader_stage_source_from_catalog(
            "test-convention-stage", "fragment");
    CHECK(fragment_stage.find("TEST_CONVENTION_FRAGMENT_STAGE_MARKER") != std::string::npos);

    tgfx::BuiltinShaderProgramSource program =
        tgfx::load_builtin_shader_program_from_catalog("test-convention-program");
    CHECK(program.name == "test-convention-program");
    REQUIRE(!program.source.empty());
    CHECK(program.source.find("TEST_CONVENTION_PROGRAM_MARKER") != std::string::npos);

    tc_shader_shutdown();
    clear_builtin_root();
    std::filesystem::remove_all(root);
}

TEST_CASE("typed engine shader descriptors register without catalog manifest") {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const std::filesystem::path root =
        std::filesystem::temp_directory_path()
        / ("termin-render-passes-typed-engine-shader-test-" + std::to_string(unique));
    std::filesystem::remove_all(root);

    write_text(
        root / "termin-engine-fsq.vert.slang",
        "// TYPED_FSQ_MARKER\n"
        "struct In { float3 position : POSITION; float2 uv : TEXCOORD0; };\n"
        "struct Out { float4 position : SV_Position; float2 uv : TEXCOORD0; };\n"
        "[shader(\"vertex\")] Out vs_main(In input) { Out output; output.position = float4(input.position, 1.0); output.uv = input.uv; return output; }\n");
    write_text(
        root / "termin-engine-shadow.slang",
        "// TYPED_SHADOW_MARKER\n"
        "struct In { float3 position : POSITION; };\n"
        "struct Out { float4 position : SV_Position; };\n"
        "[shader(\"vertex\")] Out vs_main(In input) { Out output; output.position = float4(input.position, 1.0); return output; }\n"
        "[shader(\"fragment\")] void fs_main() {}\n");
    write_text(
        root / "termin-engine-tonemap.frag.slang",
        "// TYPED_TONEMAP_MARKER\n"
        "struct In { float2 uv : TEXCOORD0; };\n"
        "[shader(\"fragment\")] float4 fs_main(In input) : SV_Target0 { return float4(input.uv, 0.0, 1.0); }\n");

    set_builtin_root(root);
    tc_shader_init();

    std::string fsq_vertex =
        tgfx::load_builtin_shader_stage_source_from_catalog("termin-engine-fsq", "vertex");
    CHECK(fsq_vertex.find("TYPED_FSQ_MARKER") != std::string::npos);

    tc_shader_handle shadow_handle =
        tgfx::register_builtin_shader_from_catalog("termin-engine-shadow");
    REQUIRE(!tc_shader_handle_is_invalid(shadow_handle));
    tc_shader* shadow = tc_shader_get(shadow_handle);
    REQUIRE(shadow != nullptr);
    REQUIRE(shadow->vertex_source != nullptr);
    REQUIRE(shadow->fragment_source != nullptr);
    CHECK(std::strstr(shadow->vertex_source, "TYPED_SHADOW_MARKER") != nullptr);
    tc_shader_contract_view shadow_contract{};
    CHECK(!tc_shader_get_contract_view(shadow, &shadow_contract));
    CHECK(!tc_shader_has_resource_layout(shadow));

    tc_shader_handle tonemap_handle =
        tgfx::register_builtin_shader_from_catalog("termin-engine-tonemap");
    REQUIRE(!tc_shader_handle_is_invalid(tonemap_handle));
    tc_shader* tonemap = tc_shader_get(tonemap_handle);
    REQUIRE(tonemap != nullptr);
    CHECK(tonemap->vertex_source == nullptr);
    REQUIRE(tonemap->fragment_source != nullptr);
    CHECK(std::strstr(tonemap->fragment_source, "TYPED_TONEMAP_MARKER") != nullptr);
    tc_shader_contract_view tonemap_contract{};
    CHECK(!tc_shader_get_contract_view(tonemap, &tonemap_contract));
    CHECK(!tc_shader_has_resource_layout(tonemap));

    std::string tonemap_fragment =
        tgfx::load_builtin_shader_stage_source_from_catalog("termin-engine-tonemap", "fragment");
    CHECK(tonemap_fragment.find("TYPED_TONEMAP_MARKER") != std::string::npos);

    tc_shader_shutdown();
    clear_builtin_root();
    std::filesystem::remove_all(root);
}

TEST_CASE("built-in shader catalog resolves migrated live engine shaders from canonical sources") {
    clear_builtin_root();
    tc_shader_init();

    struct ExpectedShader {
        const char* uuid;
        const char* name;
        bool has_vertex;
        bool has_fragment;
    };

    constexpr std::array<ExpectedShader, 46> kExpectedShaders{{
        {"termin-engine-immediate", "ImmediateEngineVSFS", true, true},
        {"termin-engine-present-blit", "PresentBlitVSFS", true, true},
        {"termin-engine-canvas2d-solid", "Canvas2DSolidVSFS", true, true},
        {"termin-engine-canvas2d-texture", "Canvas2DTextureVSFS", true, true},
        {"termin-engine-text2d", "Text2DEngineVSFS", true, true},
        {"termin-engine-text2d-sdf", "Text2DEngineSdfVSFS", true, true},
        {"termin-engine-text3d", "Text3DEngineVSFS", true, true},
        {"termin-engine-screen-line", "ScreenSpaceLineVSFS", true, true},
        {"termin-engine-screen-line-cap", "ScreenSpaceLineCapVSFS", true, true},
        {"termin-engine-screen-line-join", "ScreenSpaceLineJoinVSFS", true, true},
        {"termin-engine-screen-line-round-join", "ScreenSpaceLineRoundJoinVSFS", true, true},
        {"termin-engine-world-line", "WorldSpaceLineVSFS", true, true},
        {"termin-engine-world-line-cap", "WorldSpaceLineCapVSFS", true, true},
        {"termin-engine-world-line-join", "WorldSpaceLineJoinVSFS", true, true},
        {"termin-engine-world-line-round-join", "WorldSpaceLineRoundJoinVSFS", true, true},
        {"termin-engine-world-line-lit", "WorldSpaceLineLitFS", false, true},
        {"termin-engine-world-tube-line", "WorldTubeLineVSFS", true, true},
        {"termin-engine-world-tube-line-cap", "WorldTubeLineCapVSFS", true, true},
        {"termin-engine-world-tube-line-lit", "WorldTubeLineLitFS", false, true},
        {"termin-engine-line-default", "DefaultLineShader", true, true},
        {"termin-engine-navmesh-debug", "NavMeshDebugVSFS", true, true},
        {"termin-engine-off-mesh-link-debug", "OffMeshLinkDebugVSFS", true, true},
        {"termin-engine-voxel-display", "VoxelDisplay", true, true},
        {"termin-engine-voxelizer-line", "VoxelizerLine", true, true},
        {"termin-engine-pick-material", "PickShader", true, true},
        {"termin-engine-shadow-material", "ShadowShader", true, true},
        {"termin-engine-depth-material", "DepthShader", true, true},
        {"termin-runtime-default-color", "TerminRuntimeDefaultColor", true, true},
        {"termin-engine-shadow", "ShadowEngineVSFS", true, true},
        {"termin-engine-debug-triangle", "DebugTrianglePassVSFS", true, true},
        {"termin-engine-id", "IdEngineVSFS", true, true},
        {"termin-engine-normal", "NormalEngineVSFS", true, true},
        {"termin-engine-depth", "DepthEngineVSFS_Encoding", true, true},
        {"termin-engine-depth-only", "DepthOnlyEngineVSFS", true, true},
        {"termin-engine-depth-to-color", "DepthToColorFS", false, true},
        {"termin-engine-color-to-depth", "ColorToDepthFS", false, true},
        {"termin-engine-grayscale", "GrayscaleEngineFS", false, true},
        {"termin-engine-bloom-bright", "BloomBrightFS", false, true},
        {"termin-engine-highlight", "HighlightEngineFS", false, true},
        {"termin-engine-gizmo-mask", "GizmoMaskVSFS", true, true},
        {"termin-engine-ground-grid", "GroundGridEngineVSFS", true, true},
        {"termin-engine-solid-primitive", "SolidPrimitiveEngineVSFS", true, true},
        {"termin-engine-bloom-downsample", "BloomDownsampleFS", false, true},
        {"termin-engine-bloom-upsample", "BloomUpsampleFS", false, true},
        {"termin-engine-bloom-composite", "BloomCompositeFS", false, true},
        {"termin-engine-tonemap", "TonemapEngineFS", false, true},
    }};

    for (const ExpectedShader& expected : kExpectedShaders) {
        tc_shader_handle handle = tgfx::register_builtin_shader_from_catalog(expected.uuid);
        REQUIRE(!tc_shader_handle_is_invalid(handle));

        tc_shader* shader = tc_shader_get(handle);
        REQUIRE(shader != nullptr);
        CHECK(std::strcmp(shader->uuid, expected.uuid) == 0);
        REQUIRE(shader->name != nullptr);
        CHECK((shader->vertex_source != nullptr) == expected.has_vertex);
        CHECK((shader->fragment_source != nullptr) == expected.has_fragment);

        tc_shader_contract_view contract{};
        CHECK(!tc_shader_get_contract_view(shader, &contract));
        CHECK(!tc_shader_has_resource_layout(shader));
    }

    tgfx::BuiltinShaderProgramSource skybox =
        tgfx::load_builtin_shader_program_from_catalog("termin-engine-skybox");
    CHECK(skybox.name == "termin-engine-skybox");
    REQUIRE(!skybox.source.empty());
    CHECK(skybox.source.find("@program Skybox") != std::string::npos);

    tc_shader_shutdown();
}

TEST_CASE("built-in skybox shader is explicit Slang material shader") {
    tgfx::BuiltinShaderProgramSource skybox =
        tgfx::load_builtin_shader_program_from_catalog("termin-engine-skybox");
    REQUIRE(!skybox.source.empty());
    CHECK(skybox.source.find("@language slang") != std::string::npos);

    termin::ShaderMultyPhaseProgramm parsed = termin::parse_shader_text(skybox.source);
    CHECK(parsed.language == "slang");
    REQUIRE(!parsed.phases.empty());
    const termin::ShaderPhase& phase = parsed.phases.front();

    const std::string& vertex = phase.stages.at("vertex").source;
    const std::string& fragment = phase.stages.at("fragment").source;

    CHECK(vertex.find("struct MaterialParams") != std::string::npos);
    CHECK(vertex.find("ConstantBuffer<MaterialParams> material;") != std::string::npos);
    CHECK(fragment.find("struct MaterialParams") != std::string::npos);
    CHECK(fragment.find("ConstantBuffer<MaterialParams> material;") != std::string::npos);

    CHECK(vertex.find("material.u_view") != std::string::npos);
    CHECK(vertex.find("material.u_projection") != std::string::npos);
    CHECK(fragment.find("material.u_skybox_type") != std::string::npos);
    CHECK(fragment.find("material.u_skybox_color") != std::string::npos);
    CHECK(fragment.find("material.u_skybox_top_color") != std::string::npos);
    CHECK(fragment.find("material.u_skybox_bottom_color") != std::string::npos);
}

TEST_CASE("built-in slang shader catalog registers explicit stage entry points") {
    clear_builtin_root();
    tc_shader_init();

    tc_shader_handle handle = tgfx::register_builtin_shader_from_catalog("termin-engine-shadow");
    REQUIRE(!tc_shader_handle_is_invalid(handle));

    tc_shader* shader = tc_shader_get(handle);
    REQUIRE(shader != nullptr);
    REQUIRE(shader->vertex_source != nullptr);
    REQUIRE(shader->fragment_source != nullptr);
    CHECK(shader->vertex_source != shader->fragment_source);
    REQUIRE(shader->vertex_entry != nullptr);
    REQUIRE(shader->fragment_entry != nullptr);
    CHECK(std::strcmp(shader->vertex_entry, "vs_main") == 0);
    CHECK(std::strcmp(shader->fragment_entry, "fs_main") == 0);

    tc_shader_shutdown();
}

TEST_CASE("built-in shader catalog resolves vertex-only variant templates") {
    clear_builtin_root();

    std::string foliage_vertex =
        tgfx::load_builtin_shader_stage_source_from_catalog(
            "termin-engine-foliage-instanced", "vertex");
    REQUIRE(!foliage_vertex.empty());
    CHECK(foliage_vertex.find("import termin_prelude") != std::string::npos);
    CHECK(foliage_vertex.find("[[TerminScope(\"frame\")]]") != std::string::npos);
    CHECK(foliage_vertex.find("[[TerminScope(\"draw\")]]") != std::string::npos);
    CHECK(foliage_vertex.find("ConstantBuffer<FoliagePushData> foliage_draw") != std::string::npos);
    CHECK(foliage_vertex.find("StructuredBuffer<FoliageInstance> foliage_instances") != std::string::npos);
    CHECK(foliage_vertex.find("SV_InstanceID") != std::string::npos);
    CHECK(foliage_vertex.find("tangent_world : TEXCOORD3") != std::string::npos);
    CHECK(foliage_vertex.find("bitangent_world : TEXCOORD4") != std::string::npos);
    CHECK(foliage_vertex.find("tbn_valid : TEXCOORD5") != std::string::npos);
    CHECK(foliage_vertex.find("out mat3 v_TBN") == std::string::npos);
    CHECK(foliage_vertex.find("layout(") == std::string::npos);

    std::string foliage_shadow_vertex =
        tgfx::load_builtin_shader_stage_source_from_catalog(
            "termin-engine-foliage-shadow", "vertex");
    REQUIRE(!foliage_shadow_vertex.empty());
    CHECK(foliage_shadow_vertex.find("import termin_prelude") != std::string::npos);
    CHECK(foliage_shadow_vertex.find("[[TerminScope(\"frame\")]]") != std::string::npos);
    CHECK(foliage_shadow_vertex.find("[[TerminScope(\"draw\")]]") != std::string::npos);
    CHECK(foliage_shadow_vertex.find("ConstantBuffer<FoliagePushData> foliage_draw") != std::string::npos);
    CHECK(foliage_shadow_vertex.find("StructuredBuffer<FoliageInstance> foliage_instances") != std::string::npos);
    CHECK(foliage_shadow_vertex.find("SV_InstanceID") != std::string::npos);
    CHECK(foliage_shadow_vertex.find("layout(") == std::string::npos);

    std::string tube_vertex =
        tgfx::load_builtin_shader_stage_source_from_catalog(
            "termin-engine-world-tube-line", "vertex");
    REQUIRE(!tube_vertex.empty());
    CHECK(tube_vertex.find("world_pos : TEXCOORD0") != std::string::npos);
    CHECK(tube_vertex.find("normal_world : TEXCOORD1") != std::string::npos);
    CHECK(tube_vertex.find("uv : TEXCOORD2") != std::string::npos);
    CHECK(tube_vertex.find("tangent_world : TEXCOORD3") != std::string::npos);
    CHECK(tube_vertex.find("bitangent_world : TEXCOORD4") != std::string::npos);
    CHECK(tube_vertex.find("tbn_valid : TEXCOORD5") != std::string::npos);
    CHECK(tube_vertex.find("world_pos : POSITION1") == std::string::npos);
    CHECK(tube_vertex.find("normal : NORMAL") == std::string::npos);
}
