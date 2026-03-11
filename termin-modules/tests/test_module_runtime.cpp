#include "termin_modules/module_runtime.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <chrono>
#include <vector>

using namespace termin_modules;

namespace {

struct TestFailure {
    std::string message;
};

void expect(bool condition, const std::string& message) {
    if (!condition) {
        throw TestFailure{message};
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
    expect(alpha_config->artifact_path.filename().string() == "libalpha.so", "alpha linux artifact path");

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

void run_test(const char* name, void (*fn)(), int& failures) {
    try {
        fn();
        std::cout << "[PASS] " << name << "\n";
    } catch (const TestFailure& failure) {
        ++failures;
        std::cerr << "[FAIL] " << name << ": " << failure.message << "\n";
    } catch (const std::exception& e) {
        ++failures;
        std::cerr << "[FAIL] " << name << ": unexpected exception: " << e.what() << "\n";
    }
}

} // namespace

int main() {
    int failures = 0;

    run_test("descriptor_parsing_and_discovery", test_descriptor_parsing_and_discovery, failures);
    run_test("load_order_and_unload_guard", test_load_order_and_unload_guard, failures);
    run_test("cycle_detection", test_cycle_detection, failures);
    run_test("missing_dependency", test_missing_dependency, failures);

    if (failures != 0) {
        std::cerr << failures << " termin-modules test(s) failed\n";
        return 1;
    }

    std::cout << "All termin-modules tests passed\n";
    return 0;
}
