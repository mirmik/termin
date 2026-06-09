#include "guard_main.h"

GUARD_TEST_MAIN();

#include "tgfx2/builtin_shader_sources.hpp"

#include <array>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>

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

    constexpr const char* kVertexFilename = "termin-engine-shadow.vert.glsl";
    constexpr const char* kFragmentFilename = "termin-engine-shadow.frag.glsl";
    constexpr const char* kVertexMarker = "TEST_BUILTIN_VERTEX_SHADER_SOURCE_MARKER";
    constexpr const char* kFragmentMarker = "TEST_BUILTIN_FRAGMENT_SHADER_SOURCE_MARKER";
    write_text(
        root / kVertexFilename,
        "#version 450 core\n"
        "// TEST_BUILTIN_VERTEX_SHADER_SOURCE_MARKER\n"
        "layout(location = 0) in vec3 a_position;\n"
        "void main() { gl_Position = vec4(a_position, 1.0); }\n");
    write_text(
        root / kFragmentFilename,
        "#version 450 core\n"
        "// TEST_BUILTIN_FRAGMENT_SHADER_SOURCE_MARKER\n"
        "void main() {}\n");

    set_builtin_root(root);
    tc_shader_init();

    tc_shader_handle handle = tgfx::register_builtin_vertex_fragment_shader(
        kVertexFilename,
        kFragmentFilename,
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
        "fragment": {"path": "test-catalog-fragment.frag.glsl"}
      },
      "resources": []
    }
  ]
})");
    write_text(
        root / "test-catalog-fragment.frag.glsl",
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
        "vertex": {"path": "test-catalog.vert.glsl"},
        "fragment": {"path": "test-catalog.frag.glsl"}
      },
      "resources": []
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

    tc_shader_shutdown();
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
      "program": {"path": "test-catalog-program.shader"},
      "resources": []
    }
  ]
})");
    write_text(
        root / "test-catalog-program.shader",
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

TEST_CASE("built-in shader catalog resolves migrated live engine shaders from canonical resources") {
    clear_builtin_root();
    tc_shader_init();

    struct ExpectedShader {
        const char* uuid;
        const char* name;
        bool has_vertex;
        bool has_fragment;
    };

    constexpr std::array<ExpectedShader, 27> kExpectedShaders{{
        {"termin-engine-immediate", "ImmediateEngineVSFS", true, true},
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
        {"termin-engine-shadow", "ShadowEngineVSFS", true, true},
        {"termin-engine-debug-triangle", "DebugTrianglePassVSFS", true, true},
        {"termin-engine-id", "IdEngineVSFS", true, true},
        {"termin-engine-grayscale", "GrayscaleEngineFS", false, true},
        {"termin-engine-bloom-bright", "BloomBrightFS", false, true},
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
        REQUIRE(shader->name != nullptr);
        CHECK(std::strcmp(shader->name, expected.name) == 0);
        CHECK((shader->vertex_source != nullptr) == expected.has_vertex);
        CHECK((shader->fragment_source != nullptr) == expected.has_fragment);
    }

    tgfx::BuiltinShaderProgramSource skybox =
        tgfx::load_builtin_shader_program_from_catalog("termin-engine-skybox");
    CHECK(skybox.name == "SkyboxEngineVSFS");
    REQUIRE(!skybox.source.empty());
    CHECK(skybox.source.find("@program Skybox") != std::string::npos);

    tc_shader_shutdown();
}
