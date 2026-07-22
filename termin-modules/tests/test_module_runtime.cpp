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
    std::vector<std::string> operation_order;
    std::string fail_load_module;
    std::string fail_load_after_handle_module;
    std::string fail_unload_module;
    int build_calls = 0;
    ModuleCleanResult clean_result = ModuleCleanResult::NotSupported;

    ModuleKind kind() const override {
        return ModuleKind::Cpp;
    }

    bool load(ModuleRecord& record, const ModuleEnvironment&) override {
        load_calls.push_back(record.spec.id);
        operation_order.push_back("load:" + record.spec.id);
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
        if (record.spec.id == fail_load_after_handle_module) {
            record.error_message = "load failed after handle publication: " + record.spec.id;
            return false;
        }
        return true;
    }

    bool unload(ModuleRecord& record, const ModuleEnvironment&) override {
        unload_calls.push_back(record.spec.id);
        operation_order.push_back("unload:" + record.spec.id);
        if (record.spec.id == fail_unload_module) {
            record.error_message = "unload failed: " + record.spec.id;
            return false;
        }
        record.handle.reset();
        return true;
    }

    bool build(ModuleRecord&, const ModuleEnvironment&) override {
        ++build_calls;
        return true;
    }

    ModuleCleanResult clean(ModuleRecord& record, const ModuleEnvironment&) override {
        if (clean_result == ModuleCleanResult::Failed) {
            record.error_message = "injected clean failure";
        }
        return clean_result;
    }
};

class FakeStagedCppBackend final : public IModuleBackend {
public:
    std::vector<std::string> order;
    bool fail_begin = false;
    bool fail_finish = false;

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
        if (fail_begin) {
            record.error_message = "injected begin failure";
            return false;
        }
        return true;
    }

    bool finish_unload(ModuleRecord& record, const ModuleEnvironment&) override {
        order.push_back("finish:" + record.spec.id);
        if (fail_finish) {
            record.error_message = "injected finish failure";
            return false;
        }
        record.handle.reset();
        return true;
    }
};

class FakePythonBackend final : public IModuleBackend {
public:
    int prepare_calls = 0;
    int teardown_calls = 0;
    int load_calls = 0;
    int unload_calls = 0;
    bool fail_prepare = false;
    bool fail_unload = false;

    ModuleKind kind() const override {
        return ModuleKind::Python;
    }

    bool prepare_environment(
        const std::vector<ModuleRecord>&,
        const ModuleEnvironment&,
        std::string& diagnostics,
        std::string& error
    ) override {
        ++prepare_calls;
        diagnostics = fail_prepare ? "injected prepare diagnostics" : "";
        error = fail_prepare ? "injected environment prepare failure" : "";
        return !fail_prepare;
    }

    bool teardown_environment(const ModuleEnvironment&, std::string& error) override {
        ++teardown_calls;
        error.clear();
        return true;
    }

    bool load(ModuleRecord& record, const ModuleEnvironment&) override {
        load_calls++;
        record.handle = std::make_shared<PythonModuleHandle>();
        return true;
    }

    bool unload(ModuleRecord& record, const ModuleEnvironment&) override {
        unload_calls++;
        if (fail_unload) {
            record.error_message = "injected Python backend commit failure";
            return false;
        }
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

std::filesystem::path write_native_abi_descriptor(
    const std::filesystem::path& project_root,
    const std::string& module_id,
    const std::filesystem::path& source_artifact
) {
    const std::filesystem::path artifact =
        project_root / "build" / source_artifact.filename();
    std::filesystem::create_directories(artifact.parent_path());
    std::filesystem::copy_file(
        source_artifact,
        artifact,
        std::filesystem::copy_options::overwrite_existing
    );
    write_text_file(
        project_root / (module_id + ".module"),
        "name: " + module_id + "\nbuild:\n  output: " + artifact.string() + "\n"
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

void test_rebuild_distinguishes_no_clean_step_from_clean_failure() {
    TempDir tmp;
    write_text_file(
        tmp.path / "native.module",
        "name: native\n"
        "build:\n"
        "  output: build/libnative.so\n"
    );

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    expect(runtime.discover(tmp.path), "rebuild clean-result discovery should succeed");

    backend->clean_result = ModuleCleanResult::NotSupported;
    expect(runtime.rebuild_module("native"), "rebuild should proceed when clean is unsupported");
    expect(backend->build_calls == 1, "build should run after no-op clean");

    backend->clean_result = ModuleCleanResult::Failed;
    expect(!runtime.rebuild_module("native"), "rebuild should fail after attempted clean failure");
    expect(backend->build_calls == 1, "build must not run after failed clean");
    expect(runtime.last_error() == "injected clean failure", "clean diagnostic should be preserved");

    backend->clean_result = ModuleCleanResult::Succeeded;
    expect(runtime.rebuild_module("native"), "rebuild should proceed after successful clean");
    expect(backend->build_calls == 2, "build should run after successful clean");
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

void test_selected_closure_is_deterministic_and_mixed() {
    TempDir tmp;
    write_text_file(tmp.path / "z_python.pymodule",
                    "name: gameplay\ntype: python\ndependencies: [render, physics]\npackages: []\n");
    write_text_file(tmp.path / "physics.module",
                    "name: physics\nbuild:\n  output: build/libphysics.so\n");
    write_text_file(tmp.path / "render.module",
                    "name: render\ndependencies: [physics]\nbuild:\n  output: build/librender.so\n");
    write_text_file(tmp.path / "unused.pymodule", "name: unused\npackages: []\n");

    ModuleRuntime runtime;
    expect(runtime.discover(tmp.path), "mixed closure discovery should succeed");
    std::vector<const ModuleRecord*> closure;
    expect(runtime.resolve_closure({"gameplay"}, closure), runtime.last_error());
    expect(closure.size() == 3, "closure should exclude unrelated modules");
    expect(closure[0]->spec.id == "physics", "shared dependency should be first");
    expect(closure[1]->spec.id == "render", "native dependent should follow dependency");
    expect(closure[2]->spec.id == "gameplay", "selected root should be last");

    expect(!runtime.resolve_closure({"missing"}, closure), "missing selected root must fail");
    expect(runtime.last_error() == "Selected module not found: missing",
           "missing selected root diagnostic should name the root");
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

void test_single_reload_crosses_completed_unload_before_replacement_load() {
    TempDir tmp;
    write_text_file(
        tmp.path / "sample.module",
        "name: sample\nbuild:\n  output: build/libsample.so\n"
    );

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    expect(runtime.discover(tmp.path), "single reload gate discovery");
    expect(runtime.load_module("sample"), "single reload gate initial load");
    const std::shared_ptr<IModuleHandle> old_handle = runtime.find("sample")->handle;
    backend->operation_order.clear();

    expect(runtime.reload_module("sample"), runtime.last_error());
    expect(
        backend->operation_order == std::vector<std::string>{"unload:sample", "load:sample"},
        "single reload must finish old backend unload before replacement load"
    );
    expect(runtime.find("sample")->handle != old_handle, "replacement must publish a new handle");
}

void test_cascade_unload_failure_prevents_every_replacement_load() {
    TempDir tmp;
    write_dependency_chain(tmp);

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    expect(runtime.discover(tmp.path), "cascade unload failure discovery");
    expect(runtime.load_all(), "cascade unload failure initial load");
    backend->load_calls.clear();
    backend->unload_calls.clear();
    backend->operation_order.clear();
    backend->fail_unload_module = "game";

    expect(!runtime.reload_module_with_dependents("core"), "cascade unload must fail");
    expect(backend->load_calls.empty(), "no replacement may load after any unload failure");
    expect(
        backend->unload_calls == std::vector<std::string>{"ui", "game"},
        "cascade must stop its unload tail at the failing dependent"
    );
    expect(runtime.find("ui")->state == ModuleState::Unloaded,
           "already cleaned dependent stays unloaded");
    expect(runtime.find("game")->state == ModuleState::CleanupFailed,
           "failing dependent exposes retryable cleanup state");
    expect(runtime.find("core")->state == ModuleState::Loaded,
           "not-yet-processed dependency keeps its old active generation");
}

void test_failed_replacement_handle_is_cleaned_before_reporting_failure() {
    TempDir tmp;
    write_text_file(
        tmp.path / "sample.module",
        "name: sample\nbuild:\n  output: build/libsample.so\n"
    );

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    expect(runtime.discover(tmp.path), "failed replacement cleanup discovery");
    expect(runtime.load_module("sample"), "failed replacement cleanup initial load");
    backend->operation_order.clear();
    backend->fail_load_after_handle_module = "sample";

    expect(!runtime.reload_module("sample"), "replacement load failure must propagate");
    expect(
        backend->operation_order == std::vector<std::string>{
            "unload:sample", "load:sample", "unload:sample"
        },
        "a partially published replacement handle must be cleaned immediately"
    );
    const ModuleRecord* failed = runtime.find("sample");
    expect(failed->state == ModuleState::Failed, "cleaned replacement failure is non-active");
    expect(failed->cleanup_phase == ModuleCleanupPhase::None,
           "successful failed-load cleanup leaves no retry phase");
    expect(failed->handle == nullptr, "failed replacement leaves no backend handle");

    backend->fail_load_after_handle_module.clear();
    expect(runtime.load_module("sample"), "later clean load must recover the failed module");
    expect(runtime.find("sample")->state == ModuleState::Loaded,
           "later clean load publishes the compatible replacement");
}

void test_reload_rejects_invalid_descriptor_before_unload() {
    TempDir tmp;
    write_dependency_chain(tmp);

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    expect(runtime.discover(tmp.path), "discovery should succeed");
    expect(runtime.load_all(), "load_all should succeed before descriptor corruption");
    backend->load_calls.clear();
    backend->unload_calls.clear();

    write_text_file(tmp.path / "game.module", "name: game\ndependencies: [\n");

    expect(!runtime.reload_module_with_dependents("core"), "invalid descriptor must reject cascade reload");
    expect(runtime.last_error().find((tmp.path / "game.module").string()) != std::string::npos,
           "descriptor error should identify the invalid file");
    expect(backend->unload_calls.empty(), "descriptor validation must finish before any unload");
    expect(backend->load_calls.empty(), "descriptor validation failure must not load modules");
    expect(runtime.find("core")->state == ModuleState::Loaded, "core must remain loaded");
    expect(runtime.find("game")->state == ModuleState::Loaded, "game must remain loaded");
    expect(runtime.find("game")->spec.dependencies.size() == 1,
           "failed snapshot must preserve the last valid descriptor graph");
}

void test_cascade_reload_uses_atomic_updated_dependency_graph() {
    TempDir tmp;
    write_text_file(tmp.path / "core.module", "name: core\nbuild:\n  output: build/libcore.so\n");
    write_text_file(tmp.path / "game.module", "name: game\nbuild:\n  output: build/libgame.so\n");

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    expect(runtime.discover(tmp.path), "discovery should succeed");
    expect(runtime.load_all(), "independent modules should load");
    backend->load_calls.clear();
    backend->unload_calls.clear();

    write_text_file(
        tmp.path / "game.module",
        "name: game\ndependencies: [core]\nbuild:\n  output: build/libgame.so\n"
    );

    expect(runtime.reload_module_with_dependents("core"), runtime.last_error());
    expect(backend->unload_calls.size() == 2, "new dependent edge must expand the reload closure");
    expect(backend->unload_calls[0] == "game", "new dependent must unload before its dependency");
    expect(backend->unload_calls[1] == "core", "target must unload after its new dependent");
    expect(backend->load_calls.size() == 2, "both modules must reload using the new graph");
    expect(backend->load_calls[0] == "core" && backend->load_calls[1] == "game",
           "new dependency order must be used for loading");
}

void test_reload_rejects_duplicate_ids_and_simultaneous_cycle_atomically() {
    TempDir tmp;
    write_text_file(tmp.path / "a.module", "name: a\nbuild:\n  output: build/liba.so\n");
    write_text_file(tmp.path / "b.module", "name: b\nbuild:\n  output: build/libb.so\n");

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    expect(runtime.discover(tmp.path), "discovery should succeed");
    expect(runtime.load_all(), "modules should load before edits");
    backend->unload_calls.clear();

    write_text_file(tmp.path / "b.module", "name: a\nbuild:\n  output: build/libb.so\n");
    expect(!runtime.reload_module("a"), "duplicate module ids must reject reload");
    expect(runtime.last_error().find("Duplicate module id 'a'") != std::string::npos,
           "duplicate id diagnostic expected");
    expect(backend->unload_calls.empty(), "duplicate validation must happen before unload");
    expect(runtime.find("b") != nullptr, "failed duplicate snapshot must preserve old identity");

    write_text_file(
        tmp.path / "a.module",
        "name: a\ndependencies: [b]\nbuild:\n  output: build/liba.so\n"
    );
    write_text_file(
        tmp.path / "b.module",
        "name: b\ndependencies: [a]\nbuild:\n  output: build/libb.so\n"
    );
    expect(!runtime.reload_module_with_dependents("a"), "simultaneous cyclic edits must reject reload");
    expect(runtime.last_error().find("Dependency cycle detected") != std::string::npos,
           "cycle diagnostic expected");
    expect(backend->unload_calls.empty(), "cycle validation must happen before unload");
    expect(runtime.find("a")->spec.dependencies.empty() && runtime.find("b")->spec.dependencies.empty(),
           "failed cyclic snapshot must preserve the entire old graph");
}

void test_python_unload_prepare_failure_preserves_loaded_handle() {
    TempDir tmp;
    write_text_file(
        tmp.path / "sample.pymodule",
        "name: sample\nroot: Scripts\npackages: [sample]\n"
    );
    write_text_file(
        tmp.path / "consumer.pymodule",
        "name: consumer\nroot: Scripts\npackages: [consumer]\ndependencies: [sample]\n"
    );

    ModuleRuntime runtime;
    runtime.set_environment(ModuleEnvironment{});
    auto backend = std::make_shared<FakePythonBackend>();
    runtime.register_backend(backend);
    std::vector<ModuleEvent> events;
    runtime.set_event_callback([&events](const ModuleEvent& event) {
        events.push_back(event);
    });
    PythonModuleCallbacks callbacks;
    callbacks.before_module_remove = [](const ModuleRecord&, std::string& error) {
        error = "injected Python unload prepare failure";
        return false;
    };
    runtime.set_python_callbacks(std::move(callbacks));

    expect(runtime.discover(tmp.path), "Python module discovery should succeed");
    expect(runtime.load_module("sample"), "Python module load should succeed");
    const std::shared_ptr<IModuleHandle> loaded_handle = runtime.find("sample")->handle;

    expect(!runtime.unload_module("sample"), "fallible Python prepare must abort unload");
    expect(runtime.last_error() == "injected Python unload prepare failure",
           "prepare error must cross the runtime boundary");
    expect(backend->unload_calls == 0, "backend must not remove sys.modules after prepare failure");
    expect(runtime.find("sample")->state == ModuleState::Loaded, "module must remain loaded");
    expect(runtime.find("sample")->handle == loaded_handle, "retryable backend handle must be retained");
    expect(events.back().kind == ModuleEventKind::Failed,
           "preparation failure must not publish a cleanup transition");

    int successful_prepare_calls = 0;
    PythonModuleCallbacks retry_callbacks;
    retry_callbacks.before_module_remove = [&successful_prepare_calls](const ModuleRecord&, std::string&) {
        ++successful_prepare_calls;
        return true;
    };
    runtime.set_python_callbacks(std::move(retry_callbacks));
    backend->fail_unload = true;
    expect(!runtime.unload_module("sample"), "backend commit failure must abort Python unload");
    expect(runtime.find("sample")->state == ModuleState::CleanupFailed,
           "Python backend commit failure must enter the non-active cleanup state");
    expect(runtime.find("sample")->cleanup_phase == ModuleCleanupPhase::BackendUnload,
           "Python retry must retain the backend unload phase");
    expect(runtime.find("sample")->handle == loaded_handle,
           "Python backend commit failure must retain the handle");
    expect(events.back().kind == ModuleEventKind::CleanupFailed,
           "post-boundary failure must publish CleanupFailed");
    expect(!runtime.load_module("sample"), "load must be blocked while Python cleanup is incomplete");
    expect(!runtime.reload_module("sample"), "reload must be blocked while Python cleanup is incomplete");
    expect(!runtime.load_module("consumer"),
           "dependent activation must be blocked while dependency cleanup is incomplete");

    backend->fail_unload = false;
    expect(runtime.unload_module("sample"), "retry should unload after prepare succeeds");
    expect(backend->unload_calls == 2, "failed backend commit and retry must each run once");
    expect(successful_prepare_calls == 1, "cleanup retry must not repeat completed preparation");
    expect(runtime.find("sample")->cleanup_phase == ModuleCleanupPhase::None,
           "successful retry must clear the cleanup phase");
    expect(events.back().kind == ModuleEventKind::Unloaded,
           "successful cleanup retry must publish Unloaded");
    size_t unloading_events = 0;
    for (const ModuleEvent& event : events) {
        if (event.module_id == "sample" && event.kind == ModuleEventKind::Unloading) {
            ++unloading_events;
        }
    }
    expect(unloading_events == 2, "initial cleanup and retry must each publish Unloading");
}

void test_cpp_unload_prepare_failure_stays_loaded() {
    TempDir tmp;
    write_text_file(
        tmp.path / "native.module",
        "name: native\nbuild:\n  output: build/libnative.so\n"
    );

    ModuleRuntime runtime;
    runtime.set_environment(ModuleEnvironment{});
    auto backend = std::make_shared<FakeStagedCppBackend>();
    runtime.register_backend(backend);
    CppModuleCallbacks callbacks;
    callbacks.before_unload = [](const ModuleRecord&, std::string& error) {
        error = "injected C++ unload prepare failure";
        return false;
    };
    runtime.set_cpp_callbacks(std::move(callbacks));

    expect(runtime.discover(tmp.path), "native discovery before prepare failure");
    expect(runtime.load_module("native"), "native load before prepare failure");
    const auto handle = runtime.find("native")->handle;
    expect(!runtime.unload_module("native"), "C++ preparation failure must abort unload");
    expect(runtime.find("native")->state == ModuleState::Loaded,
           "C++ preparation failure must stay Loaded before the revoke boundary");
    expect(runtime.find("native")->cleanup_phase == ModuleCleanupPhase::None,
           "C++ preparation failure must not publish a retry phase");
    expect(runtime.find("native")->handle == handle, "preparation failure must retain the handle");
    expect(backend->order.size() == 1, "preparation failure must not call begin_unload");

    CppModuleCallbacks retry_callbacks;
    retry_callbacks.before_unload = [](const ModuleRecord&, std::string&) { return true; };
    runtime.set_cpp_callbacks(std::move(retry_callbacks));
    expect(runtime.unload_module("native"), "C++ preparation can be retried from Loaded");
}

void test_python_environment_lifecycle_wraps_module_handles() {
    TempDir tmp;
    write_text_file(
        tmp.path / "sample.pymodule",
        "name: sample\nroot: Scripts\npackages: [sample]\n"
    );

    ModuleRuntime runtime;
    auto backend = std::make_shared<FakePythonBackend>();
    runtime.register_backend(backend);

    expect(runtime.discover(tmp.path), "Python environment discovery should succeed");
    expect(backend->prepare_calls == 1, "environment must prepare once after discovery");
    expect(backend->load_calls == 0, "environment prepare must precede module imports");
    expect(runtime.load_module("sample"), "Python module should load in prepared environment");
    expect(runtime.unload_module("sample"), "Python module should unload");
    expect(backend->teardown_calls == 0, "module unload must not teardown session environment");
    expect(runtime.load_module("sample"), "Python module should reload without environment prepare");
    expect(backend->prepare_calls == 1, "repeated module loads must reuse session environment");
    expect(runtime.shutdown(), "runtime shutdown should unload and teardown environment");
    expect(backend->teardown_calls == 1, "shutdown must teardown session environment once");
}

void test_python_environment_prepare_failure_aborts_discovery() {
    TempDir tmp;
    write_text_file(
        tmp.path / "sample.pymodule",
        "name: sample\nroot: Scripts\npackages: [sample]\n"
    );

    ModuleRuntime runtime;
    auto backend = std::make_shared<FakePythonBackend>();
    backend->fail_prepare = true;
    runtime.register_backend(backend);

    expect(!runtime.discover(tmp.path), "environment prepare failure must reject discovery");
    expect(runtime.last_error().find("injected environment prepare failure") != std::string::npos,
           "environment prepare error must cross the runtime boundary");
    expect(backend->load_calls == 0, "failed environment must prevent module loads");
    expect(backend->teardown_calls == 1, "failed prepare must run transaction rollback");
    expect(runtime.find("sample")->diagnostics == "injected prepare diagnostics",
           "environment diagnostics must remain visible on discovered records");
}

void test_live_mutation_thread_guard_fails_before_backend_calls() {
    TempDir tmp;
    write_text_file(tmp.path / "guarded.module", "name: guarded\nbuild:\n  output: build/libguarded.so\n");

    ModuleRuntime runtime;
    auto backend = make_runtime(runtime);
    const std::thread::id owner_thread = std::this_thread::get_id();
    runtime.set_mutation_thread_checker([owner_thread](std::string& error) {
        if (std::this_thread::get_id() == owner_thread) return true;
        error = "injected wrong-thread mutation";
        return false;
    });
    expect(runtime.discover(tmp.path), "guarded module discovery should succeed");

    bool worker_result = true;
    std::thread worker([&runtime, &worker_result]() {
        worker_result = runtime.load_module("guarded");
    });
    worker.join();

    expect(!worker_result, "wrong-thread load must fail closed");
    expect(runtime.last_error().find("injected wrong-thread mutation") != std::string::npos,
           "wrong-thread diagnostic expected");
    expect(backend->load_calls.empty(), "thread guard must run before backend load");
    expect(runtime.find("guarded")->state == ModuleState::Discovered,
           "wrong-thread attempt must not mutate module state");
    expect(runtime.load_module("guarded"), "owner-thread load should succeed");
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
    expect(record != nullptr && record->state == ModuleState::CleanupFailed,
           "native enters the non-active cleanup state after revoke failure");
    expect(record != nullptr && record->cleanup_phase == ModuleCleanupPhase::RevokeContributions,
           "native retry must resume contribution revocation");
    expect(record != nullptr && record->handle, "native handle retained when cleanup fails");
    expect(runtime.last_error() == "cleanup failed", "cleanup failure propagated to last_error");

    const size_t order_after_failed_unload = backend->order.size();
    expect(!runtime.load_module("native"), "load should be blocked while failed module retains handle");
    expect(backend->order.size() == order_after_failed_unload, "blocked load must not call backend load");

    CppModuleCallbacks retry_callbacks;
    retry_callbacks.before_native_close = [backend](const ModuleRecord& record, std::string&) {
        backend->order.push_back("cleanup:" + record.spec.id);
        return true;
    };
    runtime.set_cpp_callbacks(std::move(retry_callbacks));
    expect(runtime.unload_module("native"), "retained staged handle should be releasable on retry");
    expect(backend->order.size() == 5, "retry must only repeat the incomplete phases");
    expect(backend->order[3] == "cleanup:native", "retry resumes contribution cleanup");
    expect(backend->order[4] == "finish:native", "retry closes only after cleanup succeeds");
}

void test_staged_cpp_finish_retry_does_not_repeat_completed_phases() {
    TempDir tmp;
    write_text_file(
        tmp.path / "native.module",
        "name: native\nbuild:\n  output: build/libnative.so\n"
    );

    ModuleRuntime runtime;
    runtime.set_environment(ModuleEnvironment{});
    auto backend = std::make_shared<FakeStagedCppBackend>();
    backend->fail_finish = true;
    runtime.register_backend(backend);
    CppModuleCallbacks callbacks;
    callbacks.before_native_close = [backend](const ModuleRecord& record, std::string&) {
        backend->order.push_back("cleanup:" + record.spec.id);
        return true;
    };
    runtime.set_cpp_callbacks(std::move(callbacks));

    expect(runtime.discover(tmp.path), "native discovery before finish retry");
    expect(runtime.load_module("native"), "native load before finish retry");
    expect(!runtime.unload_module("native"), "finish failure must retain retry state");
    expect(runtime.find("native")->state == ModuleState::CleanupFailed,
           "finish failure must be non-active");
    expect(runtime.find("native")->cleanup_phase == ModuleCleanupPhase::BackendFinish,
           "finish failure must retain the exact backend phase");

    backend->fail_finish = false;
    expect(runtime.unload_module("native"), "finish retry must complete unload");
    expect(backend->order.size() == 5, "finish retry must add exactly one backend call");
    expect(backend->order[4] == "finish:native", "finish retry must not repeat begin or cleanup");
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
    expect(runtime.find("game")->state == ModuleState::CleanupFailed,
           "failed shutdown record should enter retryable cleanup state");
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
    const std::filesystem::path artifact = write_shadow_test_descriptor(tmp.path, "shadow_test");
    const std::filesystem::path shadow_root = tmp.path / "shadow-cache";

    ModuleEnvironment environment;
    environment.native_shadow_root = shadow_root;
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    expect(runtime.discover(tmp.path), "shadow cleanup discovery should succeed");

    for (size_t iteration = 0; iteration < 3; ++iteration) {
        expect(runtime.load_module("shadow_test"), "native shadow module should load");
        const ModuleRecord* record = runtime.find("shadow_test");
        auto handle = std::dynamic_pointer_cast<CppModuleHandle>(record->handle);
        expect(handle != nullptr, "native shadow handle should be available");
        expect(handle->loaded_path.parent_path() != artifact.parent_path(), "shadow must not live beside artifact");
        expect(handle->loaded_path.string().starts_with(shadow_root.string()), "shadow must live under configured root");
        expect(std::filesystem::exists(handle->loaded_path), "shadow file should exist while loaded");
#ifdef _WIN32
        expect(
            count_regular_files(handle->loaded_path.parent_path()) == 1,
            "Windows shadow directory must own only the uniquely loaded module, not sibling DLL dependencies"
        );
#endif
        const std::filesystem::path loaded_path = handle->loaded_path;

        expect(runtime.unload_module("shadow_test"), "native shadow module should unload");
        expect(!std::filesystem::exists(loaded_path), "shadow file must be removed after native close");
        expect(count_regular_files(shadow_root) == 0, "shadow root must contain no files after unload");
    }
}

void test_cpp_reload_removes_old_shadow_before_publishing_replacement() {
    TempDir tmp;
    write_shadow_test_descriptor(tmp.path, "shadow_test");
    const std::filesystem::path shadow_root = tmp.path / "shadow-cache";

    ModuleEnvironment environment;
    environment.native_shadow_root = shadow_root;
    environment.sdk_prefix = TERMIN_MODULES_TEST_BUILD_ROOT;
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());

    expect(runtime.discover(tmp.path), "shadow reload discovery should succeed");
    expect(runtime.load_module("shadow_test"), "shadow reload initial load should succeed");
    const auto old_handle = std::dynamic_pointer_cast<CppModuleHandle>(
        runtime.find("shadow_test")->handle
    );
    expect(old_handle != nullptr, "initial native shadow handle should be available");
    const std::filesystem::path old_path = old_handle->loaded_path;
    expect(std::filesystem::exists(old_path), "initial native shadow must exist while loaded");

    expect(runtime.reload_module("shadow_test"), runtime.last_error());
    const auto replacement_handle = std::dynamic_pointer_cast<CppModuleHandle>(
        runtime.find("shadow_test")->handle
    );
    expect(replacement_handle != nullptr, "replacement native shadow handle should be available");
    expect(replacement_handle->loaded_path != old_path,
           "replacement must use a distinct native shadow path");
    expect(!std::filesystem::exists(old_path),
           "old native shadow must be removed before reload completes");
    expect(std::filesystem::exists(replacement_handle->loaded_path),
           "replacement native shadow must remain while loaded");

    expect(runtime.unload_module("shadow_test"), "shadow reload final unload should succeed");
    expect(count_regular_files(shadow_root) == 0,
           "shadow reload final unload must leave no native shadow files");
}

void test_cpp_backend_cleans_shadow_after_post_copy_load_failure() {
    TempDir tmp;
    write_shadow_test_descriptor(tmp.path, "shadow_test");
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

    expect(!runtime.load_module("shadow_test"), "injected init failure should reject load");
    expect(runtime.find("shadow_test")->handle == nullptr, "failed load must not publish a native handle");
    expect(count_regular_files(shadow_root) == 0, "failed post-copy load must remove shadow file");
}

void test_cpp_backend_shadow_sessions_do_not_collide_between_runtimes() {
    TempDir first;
    TempDir second;
    write_shadow_test_descriptor(first.path, "shadow_test");
    write_shadow_test_descriptor(second.path, "shadow_test");
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
    std::thread first_thread([&]() { first_loaded = first_runtime.load_module("shadow_test"); });
    std::thread second_thread([&]() { second_loaded = second_runtime.load_module("shadow_test"); });
    first_thread.join();
    second_thread.join();
    expect(first_loaded && second_loaded, "concurrent runtimes should both load");

    auto first_handle = std::dynamic_pointer_cast<CppModuleHandle>(first_runtime.find("shadow_test")->handle);
    auto second_handle = std::dynamic_pointer_cast<CppModuleHandle>(second_runtime.find("shadow_test")->handle);
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
    write_shadow_test_descriptor(tmp.path, "shadow_test");
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
    expect(runtime.load_module("shadow_test"), "abandoned cleanup trigger module should load");
    expect(!std::filesystem::exists(abandoned), "aged abandoned session should be removed");
    expect(std::filesystem::exists(recent / "active.dll"), "recent session must not be pruned");
    expect(runtime.shutdown(), "abandoned cleanup runtime should shut down");
}

void test_native_abi_rejects_missing_descriptor_before_init_scope() {
    TempDir tmp;
    write_native_abi_descriptor(
        tmp.path,
        "abi_missing",
        TERMIN_MODULES_TEST_ABI_MISSING
    );

    ModuleEnvironment environment;
    environment.sdk_prefix = TERMIN_MODULES_TEST_BUILD_ROOT;
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    int init_scope_calls = 0;
    CppModuleCallbacks callbacks;
    callbacks.before_native_init = [&](const ModuleRecord&) { ++init_scope_calls; };
    runtime.set_cpp_callbacks(std::move(callbacks));
    expect(runtime.discover(tmp.path), "missing ABI descriptor discovery should succeed");
    expect(!runtime.load_module("abi_missing"), "missing ABI descriptor must reject load");
    expect(init_scope_calls == 0, "missing ABI descriptor must fail before registration scope");
    expect(runtime.last_error().find("missing native module descriptor") != std::string::npos,
           "missing ABI descriptor diagnostic should be actionable: " + runtime.last_error());
}

void test_native_abi_rejects_version_mismatch_before_init_scope() {
    TempDir tmp;
    write_native_abi_descriptor(
        tmp.path,
        "abi_mismatch",
        TERMIN_MODULES_TEST_ABI_MISMATCH
    );

    ModuleEnvironment environment;
    environment.sdk_prefix = TERMIN_MODULES_TEST_BUILD_ROOT;
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    int init_scope_calls = 0;
    CppModuleCallbacks callbacks;
    callbacks.before_native_init = [&](const ModuleRecord&) { ++init_scope_calls; };
    runtime.set_cpp_callbacks(std::move(callbacks));
    expect(runtime.discover(tmp.path), "ABI mismatch discovery should succeed");
    expect(!runtime.load_module("abi_mismatch"), "ABI mismatch must reject load");
    expect(init_scope_calls == 0, "ABI mismatch must fail before registration scope");
    expect(runtime.last_error().find("native module ABI mismatch") != std::string::npos,
           "ABI mismatch diagnostic should include module and host versions: " + runtime.last_error());
}

void test_native_abi_propagates_structured_init_failure_once() {
    TempDir tmp;
    write_native_abi_descriptor(
        tmp.path,
        "abi_init_failure",
        TERMIN_MODULES_TEST_ABI_INIT_FAILURE
    );

    ModuleEnvironment environment;
    environment.sdk_prefix = TERMIN_MODULES_TEST_BUILD_ROOT;
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    int failure_callbacks = 0;
    CppModuleCallbacks callbacks;
    callbacks.after_failed_load = [&](const ModuleRecord&, const std::string&, std::string&) {
        ++failure_callbacks;
        return true;
    };
    runtime.set_cpp_callbacks(std::move(callbacks));
    expect(runtime.discover(tmp.path), "structured init failure discovery should succeed");
    expect(!runtime.load_module("abi_init_failure"), "structured init failure must reject load");
    expect(failure_callbacks == 1, "in-process init failure cleanup callback must run exactly once");
    expect(runtime.last_error().find("status 17") != std::string::npos,
           "structured init failure should preserve status: " + runtime.last_error());
    expect(runtime.last_error().find("injected structured init failure") != std::string::npos,
           "structured init failure should preserve message");
    expect(runtime.find("abi_init_failure")->handle == nullptr,
           "failed init must not publish native handle");
}

void test_native_init_failure_retains_library_until_owner_cleanup_completes() {
    TempDir tmp;
    write_native_abi_descriptor(
        tmp.path,
        "abi_init_failure",
        TERMIN_MODULES_TEST_ABI_INIT_FAILURE
    );

    ModuleEnvironment environment;
    environment.sdk_prefix = TERMIN_MODULES_TEST_BUILD_ROOT;
    environment.native_shadow_root = tmp.path / "shadow-cache";
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    CppModuleCallbacks callbacks;
    callbacks.after_failed_load = [](
        const ModuleRecord&,
        const std::string&,
        std::string& error
    ) {
        error = "injected failed-load contribution cleanup failure";
        return false;
    };
    callbacks.before_native_close = [](
        const ModuleRecord&,
        std::string& error
    ) {
        error = "injected retained contribution";
        return false;
    };
    runtime.set_cpp_callbacks(std::move(callbacks));

    expect(runtime.discover(tmp.path), "failed-init cleanup discovery should succeed");
    expect(!runtime.load_module("abi_init_failure"), "injected native init must fail");
    const ModuleRecord* failed = runtime.find("abi_init_failure");
    const auto retained_handle = std::dynamic_pointer_cast<CppModuleHandle>(failed->handle);
    expect(failed->state == ModuleState::CleanupFailed,
           "failed owner cleanup must expose a retryable non-active state");
    expect(failed->cleanup_phase == ModuleCleanupPhase::RevokeContributions,
           "failed owner cleanup must retain the exact revoke phase");
    expect(retained_handle != nullptr && retained_handle->native_handle != nullptr,
           "native library must stay loaded while owner callbacks remain");
    const std::filesystem::path retained_path = retained_handle->loaded_path;
    expect(std::filesystem::exists(retained_path),
           "native shadow must stay present while its library is retained");
    expect(!runtime.reload_module("abi_init_failure"),
           "replacement load must be blocked while failed cleanup retains the library");

    CppModuleCallbacks retry_callbacks;
    retry_callbacks.before_native_close = [](const ModuleRecord&, std::string&) {
        return true;
    };
    runtime.set_cpp_callbacks(std::move(retry_callbacks));
    expect(runtime.unload_module("abi_init_failure"),
           "explicit cleanup retry should release the failed replacement");
    expect(runtime.find("abi_init_failure")->handle == nullptr,
           "successful cleanup retry must clear the native handle");
    expect(!std::filesystem::exists(retained_path),
           "successful cleanup retry must remove the retained native shadow");
}

void test_native_abi_shutdown_failure_is_retryable_and_metadata_is_exposed() {
    TempDir tmp;
    write_native_abi_descriptor(
        tmp.path,
        "abi_shutdown_retry",
        TERMIN_MODULES_TEST_ABI_SHUTDOWN_RETRY
    );

    ModuleEnvironment environment;
    environment.sdk_prefix = TERMIN_MODULES_TEST_BUILD_ROOT;
    ModuleRuntime runtime;
    runtime.set_environment(environment);
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    expect(runtime.discover(tmp.path), "shutdown retry discovery should succeed");
    const bool loaded = runtime.load_module("abi_shutdown_retry");
    expect(loaded, "compatible ABI module should load: " + runtime.last_error());

    auto handle = std::dynamic_pointer_cast<CppModuleHandle>(
        runtime.find("abi_shutdown_retry")->handle
    );
    expect(handle && handle->descriptor, "loaded handle should expose validated descriptor");
    expect(std::string(handle->descriptor->module_version) == "1.0.0",
           "module version metadata should be available to host");
    expect(std::string(handle->descriptor->build_id) == "abi-shutdown-retry-test",
           "module build identity should be available to host");

    expect(!runtime.unload_module("abi_shutdown_retry"),
           "fallible shutdown must keep library loaded on failure");
    expect(runtime.find("abi_shutdown_retry")->handle != nullptr,
           "failed shutdown must preserve retryable handle");
    expect(runtime.last_error().find("status 23") != std::string::npos,
           "shutdown failure should preserve structured status");
    expect(runtime.unload_module("abi_shutdown_retry"),
           "idempotent shutdown retry should complete unload");
    expect(runtime.find("abi_shutdown_retry")->handle == nullptr,
           "successful shutdown retry should release handle");
}

} // namespace

TEST_CASE("module runtime parses descriptors and discovers modules") {
    test_descriptor_parsing_and_discovery();
}

TEST_CASE("module runtime resolves deterministic selected mixed closure") {
    test_selected_closure_is_deterministic_and_mixed();
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

TEST_CASE("module runtime single reload completes unload before replacement load") {
    test_single_reload_crosses_completed_unload_before_replacement_load();
}

TEST_CASE("module runtime cascade unload failure blocks every replacement load") {
    test_cascade_unload_failure_prevents_every_replacement_load();
}

TEST_CASE("module runtime cleans partial replacement handles before reporting failure") {
    test_failed_replacement_handle_is_cleaned_before_reporting_failure();
}

TEST_CASE("module runtime rejects invalid descriptor snapshots before unload") {
    test_reload_rejects_invalid_descriptor_before_unload();
}

TEST_CASE("module runtime cascade reload uses updated dependency snapshot") {
    test_cascade_reload_uses_atomic_updated_dependency_graph();
}

TEST_CASE("module runtime rebuild distinguishes clean outcomes") {
    test_rebuild_distinguishes_no_clean_step_from_clean_failure();
}

TEST_CASE("module runtime rejects duplicate ids and simultaneous cycles atomically") {
    test_reload_rejects_duplicate_ids_and_simultaneous_cycle_atomically();
}

TEST_CASE("module runtime keeps Python module loaded when unload preparation fails") {
    test_python_unload_prepare_failure_preserves_loaded_handle();
}

TEST_CASE("module runtime keeps C++ module loaded when unload preparation fails") {
    test_cpp_unload_prepare_failure_stays_loaded();
}

TEST_CASE("module runtime owns Python environment around module handles") {
    test_python_environment_lifecycle_wraps_module_handles();
}

TEST_CASE("module runtime rolls back failed Python environment prepare") {
    test_python_environment_prepare_failure_aborts_discovery();
}

TEST_CASE("module runtime rejects live mutation from a non-owner thread") {
    test_live_mutation_thread_guard_fails_before_backend_calls();
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

TEST_CASE("module runtime retries only the incomplete native finish phase") {
    test_staged_cpp_finish_retry_does_not_repeat_completed_phases();
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

TEST_CASE("cpp reload removes the old shadow before publishing its replacement") {
    test_cpp_reload_removes_old_shadow_before_publishing_replacement();
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

TEST_CASE("native ABI rejects missing descriptor before registration") {
    test_native_abi_rejects_missing_descriptor_before_init_scope();
}

TEST_CASE("native ABI rejects version mismatch before registration") {
    test_native_abi_rejects_version_mismatch_before_init_scope();
}

TEST_CASE("native ABI propagates structured init failure exactly once") {
    test_native_abi_propagates_structured_init_failure_once();
}

TEST_CASE("native init failure retains its library until owner cleanup completes") {
    test_native_init_failure_retains_library_until_owner_cleanup_completes();
}

TEST_CASE("native ABI exposes metadata and retries fallible shutdown") {
    test_native_abi_shutdown_failure_is_retryable_and_metadata_is_exposed();
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
