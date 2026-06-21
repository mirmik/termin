#include "termin_modules/module_runtime.hpp"
#include "termin_modules/text_encoding.hpp"

#include "guard_main.h"

#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <chrono>
#include <vector>

using namespace termin_modules;

namespace {

void expect(bool condition, const std::string& message) {
    if (!condition) {
        FAIL(message);
    }
}

class FakeCppBackend final : public IModuleBackend {
public:
    std::vector<std::string> load_calls;
    std::vector<std::string> unload_calls;

    ModuleKind kind() const override {
        return ModuleKind::Cpp;
    }

    bool load(ModuleRecord& record, const ModuleEnvironment&) override {
        load_calls.push_back(record.spec.id);
        auto handle = std::make_shared<CppModuleHandle>();
        const auto config = std::dynamic_pointer_cast<CppModuleConfig>(record.spec.config);
        if (config) {
            handle->artifact_path = config->artifact_path;
            handle->loaded_path = config->artifact_path;
        }
        record.handle = handle;
        return true;
    }

    bool unload(ModuleRecord& record, const ModuleEnvironment&) override {
        unload_calls.push_back(record.spec.id);
        record.handle.reset();
        return true;
    }
};

class TempDir {
public:
    std::filesystem::path path;

    TempDir() {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        path = std::filesystem::temp_directory_path() / ("termin-modules-" + std::to_string(unique));
        std::filesystem::create_directories(path);
    }

    ~TempDir() {
        std::error_code ec;
        std::filesystem::remove_all(path, ec);
    }
};

void write_text_file(const std::filesystem::path& path, const std::string& text) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path);
    out << text;
}

std::shared_ptr<FakeCppBackend> make_runtime(ModuleRuntime& runtime, std::vector<ModuleEvent>* events = nullptr) {
    runtime.set_environment(ModuleEnvironment{});
    auto backend = std::make_shared<FakeCppBackend>();
    runtime.register_backend(backend);
    if (events != nullptr) {
        runtime.set_event_callback([events](const ModuleEvent& event) {
            events->push_back(event);
        });
    }
    return backend;
}

void test_descriptor_parsing_and_discovery() {
    TempDir tmp;

    write_text_file(
        tmp.path / "alpha.module",
        "name: alpha\n"
        "components: [AlphaComponent]\n"
        "build:\n"
        "  command:\n"
        "    linux: cmake --build build --target ${name}\n"
        "    windows: cmake --build build --target ${name}\n"
        "  output:\n"
        "    linux: build/lib${name}.so\n"
        "    windows: build/Release/${name}.dll\n"
    );

    write_text_file(
        tmp.path / "beta.pymodule",
        "name: beta\n"
        "root: Scripts\n"
        "packages: [Scripts]\n"
        "requirements: [pytest]\n"
    );

    ModuleRuntime runtime;
    std::vector<ModuleEvent> events;
    make_runtime(runtime, &events);
    runtime.discover(tmp.path);

    expect(runtime.last_error().empty(), "discover should not set last_error");

    const ModuleRecord* alpha = runtime.find("alpha");
    expect(alpha != nullptr, "alpha should be discovered");
    expect(alpha->spec.kind == ModuleKind::Cpp, "alpha kind");
    expect(alpha->spec.components.size() == 1 && alpha->spec.components[0] == "AlphaComponent", "alpha components");

    auto alpha_config = std::dynamic_pointer_cast<CppModuleConfig>(alpha->spec.config);
    expect(alpha_config != nullptr, "alpha config type");
    expect(alpha_config->build_command.find("alpha") != std::string::npos, "alpha command template resolved");
#ifdef _WIN32
    expect(alpha_config->artifact_path.filename().string() == "alpha.dll", "alpha windows artifact path");
#else
    expect(alpha_config->artifact_path.filename().string() == "libalpha.so", "alpha linux artifact path");
#endif

    const ModuleRecord* beta = runtime.find("beta");
    expect(beta != nullptr, "beta should be discovered");
    expect(beta->spec.kind == ModuleKind::Python, "beta kind");

    auto beta_config = std::dynamic_pointer_cast<PythonModuleConfig>(beta->spec.config);
    expect(beta_config != nullptr, "beta config type");
    expect(beta_config->root == tmp.path / "Scripts", "beta root resolved");
    expect(beta_config->packages.size() == 1 && beta_config->packages[0] == "Scripts", "beta packages");
    expect(beta_config->requirements.size() == 1 && beta_config->requirements[0] == "pytest", "beta requirements");

    size_t discovered_count = 0;
    for (const ModuleEvent& event : events) {
        if (event.kind == ModuleEventKind::Discovered) {
            discovered_count++;
        }
    }
    expect(discovered_count == 2, "two discovered events expected");
}

void test_load_order_and_unload_guard() {
    TempDir tmp;

    write_text_file(
        tmp.path / "core.module",
        "name: core\n"
        "build:\n"
        "  output: build/libcore.so\n"
    );

    write_text_file(
        tmp.path / "game.module",
        "name: game\n"
        "dependencies: [core]\n"
        "build:\n"
        "  output: build/libgame.so\n"
    );

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    runtime.discover(tmp.path);

    expect(runtime.load_all(), "load_all should succeed");
    expect(backend->load_calls.size() == 2, "two load calls expected");
    expect(backend->load_calls[0] == "core", "dependency should load first");
    expect(backend->load_calls[1] == "game", "dependent should load second");

    const ModuleRecord* core = runtime.find("core");
    const ModuleRecord* game = runtime.find("game");
    expect(core != nullptr && core->state == ModuleState::Loaded, "core loaded");
    expect(game != nullptr && game->state == ModuleState::Loaded, "game loaded");

    expect(!runtime.unload_module("core"), "unloading loaded dependency must fail");
    expect(runtime.last_error().find("game") != std::string::npos, "dependent name should be mentioned");

    expect(runtime.unload_module("game"), "dependent unload should succeed");
    expect(runtime.unload_module("core"), "dependency unload should succeed after dependent");
    expect(backend->unload_calls.size() == 2, "two unload calls expected");
}

void test_cycle_detection() {
    TempDir tmp;

    write_text_file(
        tmp.path / "a.module",
        "name: a\n"
        "dependencies: [b]\n"
        "build:\n"
        "  output: build/liba.so\n"
    );

    write_text_file(
        tmp.path / "b.module",
        "name: b\n"
        "dependencies: [a]\n"
        "build:\n"
        "  output: build/libb.so\n"
    );

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    runtime.discover(tmp.path);

    expect(!runtime.load_all(), "cycle must fail");
    expect(runtime.last_error().find("Dependency cycle detected") != std::string::npos, "cycle error expected");
    expect(backend->load_calls.empty(), "no module should load on cycle");
}

void test_missing_dependency() {
    TempDir tmp;

    write_text_file(
        tmp.path / "broken.module",
        "name: broken\n"
        "dependencies: [missing]\n"
        "build:\n"
        "  output: build/libbroken.so\n"
    );

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    runtime.discover(tmp.path);

    expect(!runtime.load_all(), "missing dependency must fail");
    expect(runtime.last_error().find("Missing dependency 'missing'") != std::string::npos, "missing dependency error expected");
    expect(backend->load_calls.empty(), "backend must not be called");
}

void test_discovery_ignores_dist_directory() {
    TempDir tmp;

    write_text_file(
        tmp.path / "chess.pymodule",
        "name: chess\n"
        "root: .\n"
        "packages: [Scripts]\n"
    );

    write_text_file(
        tmp.path / "dist" / "Chess" / "chess.pymodule",
        "name: chess\n"
        "root: .\n"
        "packages: [Scripts]\n"
    );

    ModuleRuntime runtime;
    std::vector<ModuleEvent> events;
    make_runtime(runtime, &events);
    runtime.discover(tmp.path);

    expect(runtime.last_error().empty(), "dist module descriptor should be ignored");
    expect(runtime.find("chess") != nullptr, "root chess module should be discovered");

    size_t discovered_count = 0;
    for (const ModuleEvent& event : events) {
        if (event.kind == ModuleEventKind::Discovered) {
            discovered_count++;
        }
    }
    expect(discovered_count == 1, "only root module should be discovered");
}

void test_discovery_ignores_configured_roots() {
    TempDir tmp;

    write_text_file(
        tmp.path / "game.pymodule",
        "name: game\n"
        "root: .\n"
        "packages: [Scripts]\n"
    );

    write_text_file(
        tmp.path / "tests" / "test_game.pymodule",
        "name: test_game\n"
        "root: .\n"
        "packages: [tests]\n"
    );

    ModuleRuntime runtime;
    std::vector<ModuleEvent> events;
    make_runtime(runtime, &events);
    runtime.set_discovery_ignored_roots({tmp.path / "tests"});
    runtime.discover(tmp.path);

    expect(runtime.last_error().empty(), "ignored module descriptor should be skipped");
    expect(runtime.find("game") != nullptr, "root game module should be discovered");
    expect(runtime.find("test_game") == nullptr, "ignored test module should not be discovered");

    size_t discovered_count = 0;
    for (const ModuleEvent& event : events) {
        if (event.kind == ModuleEventKind::Discovered) {
            discovered_count++;
        }
    }
    expect(discovered_count == 1, "only non-ignored module should be discovered");
}

} // namespace

TEST_CASE("module runtime parses descriptors and discovers modules") {
    test_descriptor_parsing_and_discovery();
}

TEST_CASE("module runtime respects load order and unload guards") {
    test_load_order_and_unload_guard();
}

TEST_CASE("module runtime rejects dependency cycles") {
    test_cycle_detection();
}

TEST_CASE("module runtime reports missing dependencies") {
    test_missing_dependency();
}

TEST_CASE("module runtime ignores dist build output") {
    test_discovery_ignores_dist_directory();
}

TEST_CASE("module runtime ignores configured discovery roots") {
    test_discovery_ignores_configured_roots();
}

TEST_CASE("module text diagnostics are sanitized to utf8") {
    expect(is_valid_utf8("plain ascii"), "ascii is valid utf8");
    expect(is_valid_utf8(u8"русский текст"), "utf8 cyrillic is valid utf8");

    std::string external_text = "prefix ";
    external_text.push_back(static_cast<char>(0x91));
    external_text += " suffix";
    const std::string sanitized = sanitize_external_text(external_text);
    expect(is_valid_utf8(sanitized), "sanitized external text must be valid utf8");
    expect(sanitized.find("prefix ") == 0, "sanitized text should preserve ascii prefix");
    expect(sanitized.find(" suffix") != std::string::npos, "sanitized text should preserve ascii suffix");
}

GUARD_TEST_MAIN();
