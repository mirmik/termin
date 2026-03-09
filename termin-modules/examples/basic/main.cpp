#include <filesystem>
#include <iostream>

#include "termin_modules/module_cpp_backend.hpp"
#include "termin_modules/module_python_backend.hpp"
#include "termin_modules/module_runtime.hpp"

using namespace termin_modules;

namespace {

const char* event_kind_to_string(ModuleEventKind kind) {
    switch (kind) {
        case ModuleEventKind::Discovered:
            return "discovered";
        case ModuleEventKind::Loading:
            return "loading";
        case ModuleEventKind::Loaded:
            return "loaded";
        case ModuleEventKind::Unloading:
            return "unloading";
        case ModuleEventKind::Unloaded:
            return "unloaded";
        case ModuleEventKind::Reloading:
            return "reloading";
        case ModuleEventKind::Failed:
            return "failed";
    }
    return "unknown";
}

const char* kind_to_string(ModuleKind kind) {
    switch (kind) {
        case ModuleKind::Cpp:
            return "cpp";
        case ModuleKind::Python:
            return "python";
    }
    return "unknown";
}

const char* state_to_string(ModuleState state) {
    switch (state) {
        case ModuleState::Discovered:
            return "discovered";
        case ModuleState::Loaded:
            return "loaded";
        case ModuleState::Failed:
            return "failed";
        case ModuleState::Unloaded:
            return "unloaded";
    }
    return "unknown";
}

} // namespace

int main(int argc, char** argv) {
    std::filesystem::path project_root;
    if (argc > 1) {
        project_root = argv[1];
    } else {
        project_root = std::filesystem::path(TERMIN_MODULES_EXAMPLE_PROJECT_DIR);
    }

    ModuleRuntime runtime;
    runtime.set_environment(ModuleEnvironment{
        .sdk_prefix = std::filesystem::current_path(),
        .python_executable = "python3",
    });
    runtime.set_cpp_callbacks(CppModuleCallbacks{
        .after_load = [](const ModuleRecord& record) {
            std::cout << "[cpp] loaded " << record.spec.id << "\n";
        },
        .after_unload = [](const ModuleRecord& record) {
            std::cout << "[cpp] unloaded " << record.spec.id << "\n";
        },
        .after_reload = [](const ModuleRecord& record) {
            std::cout << "[cpp] reloaded " << record.spec.id << "\n";
        },
        .after_failed_load = [](const ModuleRecord& record, const std::string& error) {
            std::cout << "[cpp] failed " << record.spec.id << ": " << error << "\n";
        },
    });
    runtime.set_python_callbacks(PythonModuleCallbacks{
        .after_load = [](const ModuleRecord& record) {
            std::cout << "[python] loaded " << record.spec.id << "\n";
        },
        .after_unload = [](const ModuleRecord& record) {
            std::cout << "[python] unloaded " << record.spec.id << "\n";
        },
        .after_reload = [](const ModuleRecord& record) {
            std::cout << "[python] reloaded " << record.spec.id << "\n";
        },
        .after_failed_load = [](const ModuleRecord& record, const std::string& error) {
            std::cout << "[python] failed " << record.spec.id << ": " << error << "\n";
        },
    });
    runtime.register_backend(std::make_shared<CppModuleBackend>());
    runtime.register_backend(std::make_shared<PythonModuleBackend>());
    runtime.set_event_callback([](const ModuleEvent& event) {
        std::cout << "[event] " << event_kind_to_string(event.kind) << " " << event.module_id;
        if (!event.message.empty()) {
            std::cout << " :: " << event.message;
        }
        std::cout << "\n";
    });

    runtime.discover(project_root);
    if (!runtime.load_all()) {
        std::cout << "load_all failed: " << runtime.last_error() << "\n";
    }

    for (const ModuleRecord* record : runtime.list()) {
        std::cout << record->spec.id
                  << " kind=" << kind_to_string(record->spec.kind)
                  << " state=" << state_to_string(record->state);
        if (!record->diagnostics.empty()) {
            std::cout << "\n--- diagnostics ---\n" << record->diagnostics << "--- end diagnostics ---";
        }
        if (!record->error_message.empty()) {
            std::cout << " error=" << record->error_message;
        }
        std::cout << "\n";
    }

    runtime.reload_module("cpp_demo");
    runtime.unload_module("python_demo");
    runtime.unload_module("cpp_demo");
    return 0;
}
