#include "termin_modules/module_cpp_backend.hpp"
#include "termin_modules/module_runtime.hpp"
#include "termin_modules/text_encoding.hpp"

#include "guard_main.h"

#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <chrono>
#include <vector>
#include <stdexcept>
#include <thread>

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
    std::string fail_load_module;
    std::string fail_unload_module;

    ModuleKind kind() const override {
        return ModuleKind::Cpp;
    }

    bool load(ModuleRecord& record, const ModuleEnvironment&) override {
        load_calls.push_back(record.spec.id);
        if (record.spec.id == fail_load_module) {
            record.error_message = "load failed: " + record.spec.id;
            return false;
        }
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
        if (record.spec.id == fail_unload_module) {
            record.error_message = "unload failed: " + record.spec.id;
            return false;
        }
        record.handle.reset();
        return true;
    }
};

class FakeStagedCppBackend final : public IModuleBackend {
public:
    std::vector<std::string> order;

    ModuleKind kind() const override {
        return ModuleKind::Cpp;
    }

    bool supports_staged_unload() const override {
        return true;
    }

    bool load(ModuleRecord& record, const ModuleEnvironment&) override {
        order.push_back("load:" + record.spec.id);
        record.handle = std::make_shared<CppModuleHandle>();
        return true;
    }

    bool unload(ModuleRecord& record, const ModuleEnvironment&) override {
        order.push_back("legacy-unload:" + record.spec.id);
        record.handle.reset();
        return true;
    }

    bool begin_unload(ModuleRecord& record, const ModuleEnvironment&) override {
        order.push_back("begin:" + record.spec.id);
        return true;
    }

    bool finish_unload(ModuleRecord& record, const ModuleEnvironment&) override {
        order.push_back("finish:" + record.spec.id);
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

std::filesystem::path write_shadow_test_descriptor(
    const std::filesystem::path& project_root,
    const std::string& module_id
) {
#ifdef _WIN32
    const std::filesystem::path artifact = project_root / "build" / "shadow_test_module.dll";
    const std::string output = "build/shadow_test_module.dll";
#else
    const std::filesystem::path artifact = project_root / "build" / "libshadow_test_module.so";
    const std::string output = "build/libshadow_test_module.so";
#endif
    std::filesystem::create_directories(artifact.parent_path());
    std::filesystem::copy_file(
        TERMIN_MODULES_TEST_SHADOW_MODULE,
        artifact,
        std::filesystem::copy_options::overwrite_existing
    );
    const std::filesystem::path dependency_source = TERMIN_MODULES_TEST_SHADOW_DEPENDENCY;
    std::filesystem::copy_file(
        dependency_source,
        artifact.parent_path() / dependency_source.filename(),
        std::filesystem::copy_options::overwrite_existing
    );
    write_text_file(
        project_root / (module_id + ".module"),
        "name: " + module_id + "\nbuild:\n  output: " + output + "\n"
    );
    return artifact;
}

size_t count_regular_files(const std::filesystem::path& root) {
    if (!std::filesystem::exists(root)) {
        return 0;
    }
    size_t result = 0;
    for (const auto& entry : std::filesystem::recursive_directory_iterator(root)) {
        if (entry.is_regular_file()) {
            ++result;
        }
    }
    return result;
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

void test_descriptor_rejects_explicit_components() {
    TempDir tmp;

    write_text_file(
        tmp.path / "legacy.pymodule",
        "name: legacy\n"
        "root: .\n"
        "packages: [legacy]\n"
        "components: [LegacyComponent]\n"
    );

    ModuleRuntime runtime;
    make_runtime(runtime);
    runtime.discover(tmp.path);

    expect(runtime.last_error().find("Field 'components' is no longer supported") != std::string::npos,
           "components field should be rejected");
    expect(runtime.find("legacy") == nullptr, "legacy module should not be discovered");
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
    expect(!runtime.reload_module("core"), "single-module reload should keep loaded dependent guard");
    expect(runtime.last_error().find("game") != std::string::npos, "reload guard should mention dependent");

    expect(runtime.unload_module("game"), "dependent unload should succeed");
    expect(runtime.unload_module("core"), "dependency unload should succeed after dependent");
    expect(backend->unload_calls.size() == 2, "two unload calls expected");
}

void write_dependency_chain(TempDir& tmp) {
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

    write_text_file(
        tmp.path / "ui.module",
        "name: ui\n"
        "dependencies: [game]\n"
        "build:\n"
        "  output: build/libui.so\n"
    );
}

void test_cascade_reload_unloads_dependents_before_dependency() {
    TempDir tmp;
    write_dependency_chain(tmp);

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    runtime.discover(tmp.path);

    expect(runtime.load_all(), "load_all should succeed for dependency chain");
    backend->load_calls.clear();
    backend->unload_calls.clear();

    expect(runtime.reload_module_with_dependents("core"), runtime.last_error());

    expect(backend->unload_calls.size() == 3, "cascade should unload three modules");
    expect(backend->unload_calls[0] == "ui", "deepest dependent should unload first");
    expect(backend->unload_calls[1] == "game", "direct dependent should unload before dependency");
    expect(backend->unload_calls[2] == "core", "dependency should unload last");

    expect(backend->load_calls.size() == 3, "cascade should reload three modules");
    expect(backend->load_calls[0] == "core", "dependency should load first");
    expect(backend->load_calls[1] == "game", "direct dependent should load after dependency");
    expect(backend->load_calls[2] == "ui", "deepest dependent should load last");

    expect(runtime.find("core")->state == ModuleState::Loaded, "core loaded after cascade");
    expect(runtime.find("game")->state == ModuleState::Loaded, "game loaded after cascade");
    expect(runtime.find("ui")->state == ModuleState::Loaded, "ui loaded after cascade");
}

void test_cascade_reload_leaves_unloaded_dependents_unloaded() {
    TempDir tmp;
    write_dependency_chain(tmp);

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    runtime.discover(tmp.path);

    expect(runtime.load_module("core"), "core load should succeed");
    expect(runtime.load_module("game"), "game load should succeed");
    backend->load_calls.clear();
    backend->unload_calls.clear();

    expect(runtime.reload_module_with_dependents("core"), runtime.last_error());

    expect(backend->unload_calls.size() == 2, "cascade should unload only loaded modules");
    expect(backend->unload_calls[0] == "game", "loaded dependent should unload first");
    expect(backend->unload_calls[1] == "core", "target should unload second");
    expect(backend->load_calls.size() == 2, "cascade should reload only target and loaded dependents");
    expect(backend->load_calls[0] == "core", "target should load first");
    expect(backend->load_calls[1] == "game", "loaded dependent should load second");
    expect(runtime.find("ui")->state == ModuleState::Discovered, "unloaded dependent should remain discovered");
}

void test_cascade_reload_stops_on_dependent_load_failure() {
    TempDir tmp;
    write_dependency_chain(tmp);

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    runtime.discover(tmp.path);

    expect(runtime.load_all(), "load_all should succeed before failure injection");
    backend->load_calls.clear();
    backend->unload_calls.clear();
    backend->fail_load_module = "game";

    expect(!runtime.reload_module_with_dependents("core"), "cascade should fail when dependent reload fails");
    expect(runtime.last_error() == "load failed: game", "dependent load failure should be reported");

    expect(backend->unload_calls.size() == 3, "all affected modules should have been unloaded before reload");
    expect(backend->unload_calls[0] == "ui", "ui unload before failed reload");
    expect(backend->unload_calls[1] == "game", "game unload before failed reload");
    expect(backend->unload_calls[2] == "core", "core unload before failed reload");
    expect(backend->load_calls.size() == 2, "reload should stop at failed dependent");
    expect(backend->load_calls[0] == "core", "core should reload before dependent failure");
    expect(backend->load_calls[1] == "game", "game load should fail");

    expect(runtime.find("core")->state == ModuleState::Loaded, "core remains loaded after dependent failure");
    expect(runtime.find("game")->state == ModuleState::Failed, "failed dependent should be marked failed");
    expect(runtime.find("ui")->state == ModuleState::Unloaded, "later dependent remains unloaded");
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

void test_cpp_backend_clean_process_validation_reports_unresolved_symbol() {
#ifdef _WIN32
    return;
#else
    TempDir tmp;

    write_text_file(
        tmp.path / "broken_native.cpp",
        "extern \"C\" void missing_termin_module_symbol();\n"
        "extern \"C\" void module_init() { missing_termin_module_symbol(); }\n"
    );

    const std::string compiler = TERMIN_MODULES_TEST_CXX_COMPILER;
    write_text_file(
        tmp.path / "broken_native.module",
        "name: broken_native\n"
        "build:\n"
        "  command:\n"
        "    linux: mkdir -p build && " + compiler + " -shared -fPIC broken_native.cpp -o build/libbroken_native.so\n"
        "  output:\n"
        "    linux: build/libbroken_native.so\n"
    );

    ModuleEnvironment environment;
    environment.sdk_prefix = TERMIN_MODULES_TEST_BUILD_ROOT;

    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    runtime.discover(tmp.path);

    expect(!runtime.load_module("broken_native"), "native validation must reject unresolved symbols");
    const ModuleRecord* record = runtime.find("broken_native");
    expect(record != nullptr, "broken_native record should exist");
    expect(record->state == ModuleState::Failed, "broken_native should be marked failed");
    expect(
        record->error_message.find("Native artifact validation failed") != std::string::npos,
        "validation failure should be reported"
    );
    expect(
        record->error_message.find("missing_termin_module_symbol") != std::string::npos ||
            record->diagnostics.find("missing_termin_module_symbol") != std::string::npos,
        "missing symbol should be present in diagnostics"
    );
#endif
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

void test_staged_cpp_unload_runs_cleanup_before_close() {
    TempDir tmp;

    write_text_file(
        tmp.path / "native.module",
        "name: native\n"
        "build:\n"
        "  output: build/libnative.so\n"
    );

    ModuleRuntime runtime;
    runtime.set_environment(ModuleEnvironment{});
    auto backend = std::make_shared<FakeStagedCppBackend>();
    runtime.register_backend(backend);

    CppModuleCallbacks callbacks;
    callbacks.before_native_close = [backend](const ModuleRecord& record, std::string& error) {
        (void)error;
        backend->order.push_back("cleanup:" + record.spec.id);
        return true;
    };
    runtime.set_cpp_callbacks(std::move(callbacks));

    runtime.discover(tmp.path);
    expect(runtime.load_module("native"), "native load should succeed");
    expect(runtime.unload_module("native"), "native unload should succeed");

    expect(backend->order.size() == 4, "staged unload order event count");
    expect(backend->order[0] == "load:native", "staged load order");
    expect(backend->order[1] == "begin:native", "begin_unload before cleanup");
    expect(backend->order[2] == "cleanup:native", "cleanup before finish_unload");
    expect(backend->order[3] == "finish:native", "finish_unload after cleanup");

    const ModuleRecord* record = runtime.find("native");
    expect(record != nullptr && record->state == ModuleState::Unloaded, "native unloaded after staged cleanup");
    expect(record != nullptr && !record->handle, "native handle reset after staged finish");
}

void test_staged_cpp_unload_keeps_handle_when_cleanup_fails() {
    TempDir tmp;

    write_text_file(
        tmp.path / "native.module",
        "name: native\n"
        "build:\n"
        "  output: build/libnative.so\n"
    );

    ModuleRuntime runtime;
    runtime.set_environment(ModuleEnvironment{});
    auto backend = std::make_shared<FakeStagedCppBackend>();
    runtime.register_backend(backend);

    CppModuleCallbacks callbacks;
    callbacks.before_native_close = [backend](const ModuleRecord& record, std::string& error) {
        backend->order.push_back("cleanup:" + record.spec.id);
        error = "cleanup failed";
        return false;
    };
    runtime.set_cpp_callbacks(std::move(callbacks));

    runtime.discover(tmp.path);
    expect(runtime.load_module("native"), "native load before failed cleanup should succeed");
    expect(!runtime.unload_module("native"), "native unload should fail when cleanup fails");

    expect(backend->order.size() == 3, "failed cleanup order event count");
    expect(backend->order[0] == "load:native", "failed cleanup load order");
    expect(backend->order[1] == "begin:native", "failed cleanup begin order");
    expect(backend->order[2] == "cleanup:native", "failed cleanup before skipped finish");

    const ModuleRecord* record = runtime.find("native");
    expect(record != nullptr && record->state == ModuleState::Failed, "native marked failed after cleanup failure");
    expect(record != nullptr && record->handle, "native handle retained when cleanup fails");
    expect(runtime.last_error() == "cleanup failed", "cleanup failure propagated to last_error");

    const size_t order_after_failed_unload = backend->order.size();
    expect(!runtime.load_module("native"), "load should be blocked while failed module retains handle");
    expect(backend->order.size() == order_after_failed_unload, "blocked load must not call backend load");

    CppModuleCallbacks retry_callbacks;
    retry_callbacks.before_native_close = [](const ModuleRecord&, std::string&) {
        return true;
    };
    runtime.set_cpp_callbacks(std::move(retry_callbacks));
    expect(runtime.shutdown(), "retained staged handle should be releasable on retry");
}

void test_discovery_rejects_active_handles_without_losing_records() {
    TempDir first;
    TempDir second;
    write_text_file(first.path / "active.module", "name: active\nbuild:\n  output: build/libactive.so\n");
    write_text_file(second.path / "replacement.module", "name: replacement\nbuild:\n  output: build/libreplacement.so\n");

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    expect(runtime.discover(first.path), "initial discovery should succeed");
    expect(runtime.load_module("active"), "active module should load");

    expect(!runtime.discover(second.path), "rediscovery over an active handle must fail");
    expect(runtime.find("active") != nullptr, "active record must survive rejected rediscovery");
    expect(runtime.find("active")->handle != nullptr, "active handle must survive rejected rediscovery");
    expect(runtime.find("replacement") == nullptr, "rejected rediscovery must not publish replacement records");
    expect(backend->unload_calls.empty(), "rediscovery must not implicitly unload modules");

    expect(runtime.shutdown(), "explicit shutdown should unload the active module");
    expect(runtime.discover(second.path), "discovery should succeed after shutdown");
    expect(runtime.find("replacement") != nullptr, "replacement should be visible after safe discovery");
}

void test_shutdown_unloads_reverse_dependencies_and_retries_failed_handles() {
    TempDir tmp;
    write_text_file(tmp.path / "core.module", "name: core\nbuild:\n  output: build/libcore.so\n");
    write_text_file(
        tmp.path / "game.module",
        "name: game\ndependencies: [core]\nbuild:\n  output: build/libgame.so\n"
    );

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    expect(runtime.discover(tmp.path), "shutdown test discovery should succeed");
    expect(runtime.load_all(), "shutdown test modules should load");

    backend->fail_unload_module = "game";
    expect(!runtime.shutdown(), "shutdown must report retained failed handle");
    expect(backend->unload_calls.size() == 1, "dependency guard must keep core backend untouched");
    expect(backend->unload_calls[0] == "game", "shutdown must unload dependent first");
    expect(runtime.find("game")->state == ModuleState::Failed, "failed shutdown record should be retryable");
    expect(runtime.find("game")->handle != nullptr, "failed shutdown must retain backend handle");
    expect(runtime.find("core")->handle != nullptr, "dependency stays active while dependent handle remains");

    backend->fail_unload_module.clear();
    backend->unload_calls.clear();
    expect(runtime.shutdown(), "second shutdown should retry retained handles");
    expect(backend->unload_calls.size() == 2, "retry should unload both retained handles");
    expect(backend->unload_calls[0] == "game", "retry keeps reverse dependency order");
    expect(backend->unload_calls[1] == "core", "retry unloads dependency last");
    expect(runtime.find("game")->handle == nullptr, "retry clears dependent handle");
    expect(runtime.find("core")->handle == nullptr, "retry clears dependency handle");
}

void test_destructor_runs_non_throwing_shutdown() {
    TempDir tmp;
    write_text_file(tmp.path / "native.module", "name: native\nbuild:\n  output: build/libnative.so\n");

    auto backend = std::make_shared<FakeCppBackend>();
    {
        ModuleRuntime runtime;
        runtime.set_environment(ModuleEnvironment{});
        runtime.register_backend(backend);
        expect(runtime.discover(tmp.path), "destructor test discovery should succeed");
        expect(runtime.load_module("native"), "destructor test module should load");
    }

    expect(backend->unload_calls.size() == 1, "destructor must attempt runtime shutdown");
    expect(backend->unload_calls[0] == "native", "destructor should unload the active module");
}

void test_cpp_backend_cleans_shadow_artifacts_after_repeated_unload() {
    TempDir tmp;
    const std::filesystem::path artifact = write_shadow_test_descriptor(tmp.path, "native");
    const std::filesystem::path shadow_root = tmp.path / "shadow-cache";

    ModuleEnvironment environment;
    environment.native_shadow_root = shadow_root;
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    expect(runtime.discover(tmp.path), "shadow cleanup discovery should succeed");

    for (size_t iteration = 0; iteration < 3; ++iteration) {
        expect(runtime.load_module("native"), "native shadow module should load");
        const ModuleRecord* record = runtime.find("native");
        auto handle = std::dynamic_pointer_cast<CppModuleHandle>(record->handle);
        expect(handle != nullptr, "native shadow handle should be available");
        expect(handle->loaded_path.parent_path() != artifact.parent_path(), "shadow must not live beside artifact");
        expect(handle->loaded_path.string().starts_with(shadow_root.string()), "shadow must live under configured root");
        expect(std::filesystem::exists(handle->loaded_path), "shadow file should exist while loaded");
        const std::filesystem::path loaded_path = handle->loaded_path;

        expect(runtime.unload_module("native"), "native shadow module should unload");
        expect(!std::filesystem::exists(loaded_path), "shadow file must be removed after native close");
        expect(count_regular_files(shadow_root) == 0, "shadow root must contain no files after unload");
    }
}

void test_cpp_backend_cleans_shadow_after_post_copy_load_failure() {
    TempDir tmp;
    write_shadow_test_descriptor(tmp.path, "failing_native");
    const std::filesystem::path shadow_root = tmp.path / "shadow-cache";

    ModuleEnvironment environment;
    environment.native_shadow_root = shadow_root;
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    CppModuleCallbacks callbacks;
    callbacks.before_native_init = [](const ModuleRecord&) {
        throw std::runtime_error("injected native init scope failure");
    };
    runtime.set_cpp_callbacks(std::move(callbacks));
    expect(runtime.discover(tmp.path), "failed shadow load discovery should succeed");

    expect(!runtime.load_module("failing_native"), "injected init failure should reject load");
    expect(runtime.find("failing_native")->handle == nullptr, "failed load must not publish a native handle");
    expect(count_regular_files(shadow_root) == 0, "failed post-copy load must remove shadow file");
}

void test_cpp_backend_shadow_sessions_do_not_collide_between_runtimes() {
    TempDir first;
    TempDir second;
    write_shadow_test_descriptor(first.path, "first_native");
    write_shadow_test_descriptor(second.path, "second_native");
    const std::filesystem::path shadow_root = first.path / "shared-shadow-cache";

    ModuleEnvironment environment;
    environment.native_shadow_root = shadow_root;
    ModuleRuntime first_runtime;
    ModuleRuntime second_runtime;
    first_runtime.set_environment(environment);
    second_runtime.set_environment(environment);
    first_runtime.register_backend(std::make_shared<CppModuleBackend>());
    second_runtime.register_backend(std::make_shared<CppModuleBackend>());
    expect(first_runtime.discover(first.path), "first concurrent runtime discovery should succeed");
    expect(second_runtime.discover(second.path), "second concurrent runtime discovery should succeed");

    bool first_loaded = false;
    bool second_loaded = false;
    std::thread first_thread([&]() { first_loaded = first_runtime.load_module("first_native"); });
    std::thread second_thread([&]() { second_loaded = second_runtime.load_module("second_native"); });
    first_thread.join();
    second_thread.join();
    expect(first_loaded && second_loaded, "concurrent runtimes should both load");

    auto first_handle = std::dynamic_pointer_cast<CppModuleHandle>(first_runtime.find("first_native")->handle);
    auto second_handle = std::dynamic_pointer_cast<CppModuleHandle>(second_runtime.find("second_native")->handle);
    expect(first_handle && second_handle, "both concurrent handles should exist");
    expect(first_handle->loaded_path != second_handle->loaded_path, "concurrent shadow paths must be unique");
    expect(first_handle->loaded_path.parent_path() != second_handle->loaded_path.parent_path(),
           "concurrent runtimes must own separate session directories");

    expect(first_runtime.shutdown(), "first concurrent runtime should shut down");
    expect(second_runtime.shutdown(), "second concurrent runtime should shut down");
    expect(count_regular_files(shadow_root) == 0, "concurrent shutdown must remove every shadow file");
}

void test_cpp_backend_prunes_only_aged_abandoned_shadow_sessions() {
    TempDir tmp;
    write_shadow_test_descriptor(tmp.path, "native");
    const std::filesystem::path shadow_root = tmp.path / "shadow-cache";
    const std::filesystem::path abandoned = shadow_root / "session-999999999-old";
    const std::filesystem::path recent = shadow_root / "session-999999998-recent";
    std::filesystem::create_directories(abandoned);
    std::filesystem::create_directories(recent);
    write_text_file(abandoned / "stale.dll", "stale");
    write_text_file(recent / "active.dll", "active");
    std::filesystem::last_write_time(
        abandoned,
        std::filesystem::file_time_type::clock::now() - std::chrono::hours(25)
    );

    ModuleEnvironment environment;
    environment.native_shadow_root = shadow_root;
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    expect(runtime.discover(tmp.path), "abandoned cleanup discovery should succeed");
    expect(runtime.load_module("native"), "abandoned cleanup trigger module should load");
    expect(!std::filesystem::exists(abandoned), "aged abandoned session should be removed");
    expect(std::filesystem::exists(recent / "active.dll"), "recent session must not be pruned");
    expect(runtime.shutdown(), "abandoned cleanup runtime should shut down");
}

} // namespace

TEST_CASE("module runtime parses descriptors and discovers modules") {
    test_descriptor_parsing_and_discovery();
}

TEST_CASE("module runtime rejects explicit component descriptor lists") {
    test_descriptor_rejects_explicit_components();
}

TEST_CASE("module runtime respects load order and unload guards") {
    test_load_order_and_unload_guard();
}

TEST_CASE("module runtime cascade reload unloads dependents before dependencies") {
    test_cascade_reload_unloads_dependents_before_dependency();
}

TEST_CASE("module runtime cascade reload does not load inactive dependents") {
    test_cascade_reload_leaves_unloaded_dependents_unloaded();
}

TEST_CASE("module runtime cascade reload stops on dependent load failure") {
    test_cascade_reload_stops_on_dependent_load_failure();
}

TEST_CASE("module runtime rejects dependency cycles") {
    test_cycle_detection();
}

TEST_CASE("module runtime reports missing dependencies") {
    test_missing_dependency();
}

TEST_CASE("cpp backend validates native artifact in clean process") {
    test_cpp_backend_clean_process_validation_reports_unresolved_symbol();
}

TEST_CASE("module runtime ignores dist build output") {
    test_discovery_ignores_dist_directory();
}

TEST_CASE("module runtime ignores configured discovery roots") {
    test_discovery_ignores_configured_roots();
}

TEST_CASE("module runtime stages C++ unload cleanup before native close") {
    test_staged_cpp_unload_runs_cleanup_before_close();
}

TEST_CASE("module runtime keeps native handle loaded when C++ cleanup fails") {
    test_staged_cpp_unload_keeps_handle_when_cleanup_fails();
}

TEST_CASE("module runtime rejects discovery over active backend handles") {
    test_discovery_rejects_active_handles_without_losing_records();
}

TEST_CASE("module runtime shutdown retries failed handles in reverse dependency order") {
    test_shutdown_unloads_reverse_dependencies_and_retries_failed_handles();
}

TEST_CASE("module runtime destructor performs non-throwing shutdown") {
    test_destructor_runs_non_throwing_shutdown();
}

TEST_CASE("cpp backend cleans shadow artifacts after repeated unload") {
    test_cpp_backend_cleans_shadow_artifacts_after_repeated_unload();
}

TEST_CASE("cpp backend cleans shadow artifacts after post-copy load failure") {
    test_cpp_backend_cleans_shadow_after_post_copy_load_failure();
}

TEST_CASE("cpp backend shadow sessions are collision-free across concurrent runtimes") {
    test_cpp_backend_shadow_sessions_do_not_collide_between_runtimes();
}

TEST_CASE("cpp backend prunes only aged abandoned shadow sessions") {
    test_cpp_backend_prunes_only_aged_abandoned_shadow_sessions();
}

TEST_CASE("module text diagnostics are sanitized to utf8") {
    expect(is_valid_utf8("plain ascii"), "ascii is valid utf8");
    expect(
        is_valid_utf8(
            "\xd1\x80\xd1\x83\xd1\x81\xd1\x81\xd0\xba\xd0\xb8\xd0\xb9 "
            "\xd1\x82\xd0\xb5\xd0\xba\xd1\x81\xd1\x82"),
        "utf8 cyrillic is valid utf8");

    std::string external_text = "prefix ";
    external_text.push_back(static_cast<char>(0x91));
    external_text += " suffix";
    const std::string sanitized = sanitize_external_text(external_text);
    expect(is_valid_utf8(sanitized), "sanitized external text must be valid utf8");
    expect(sanitized.find("prefix ") == 0, "sanitized text should preserve ascii prefix");
    expect(sanitized.find(" suffix") != std::string::npos, "sanitized text should preserve ascii suffix");
}

GUARD_TEST_MAIN();
