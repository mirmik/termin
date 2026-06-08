#include "guard_main.h"

GUARD_TEST_MAIN();

#include "builtin_shader_sources.hpp"

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

    tc_shader_handle handle = termin::register_builtin_fragment_shader(
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
