#include <termin/modules/term_modules_integration.hpp>

#include <tcbase/tc_log.hpp>

#include <termin/entity/unknown_component_ops.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/tc_scene.hpp>

#include <termin/scene/scene_manager.hpp>

#include <tc_inspect_cpp.hpp>

namespace termin {
namespace {

std::vector<TcSceneRef> collect_scenes() {
    std::vector<TcSceneRef> scenes;

    SceneManager* manager = SceneManager::instance();
    if (manager == nullptr) {
        return scenes;
    }

    for (const std::string& name : manager->scene_names()) {
        tc_scene_handle scene = manager->get_scene(name);
        if (tc_scene_alive(scene)) {
            scenes.emplace_back(scene);
        }
    }

    return scenes;
}

std::vector<std::string> module_component_types(const termin_modules::ModuleRecord& record) {
    return ComponentRegistry::instance().list_owned(record.spec.id);
}

void begin_module_registration_scope(const termin_modules::ModuleRecord& record) {
    ComponentRegistry::instance().set_registration_owner(record.spec.id);
    tc::InspectRegistry::instance().set_registration_owner(record.spec.id);
}

void end_module_registration_scope(const termin_modules::ModuleRecord& record) {
    auto& components = ComponentRegistry::instance();
    auto& inspect = tc::InspectRegistry::instance();

    if (!components.registration_owner().empty() &&
        components.registration_owner() != record.spec.id) {
        tc::Log::warn(
            "TermModulesIntegration: component registration owner scope mismatch while ending module '%s'",
            record.spec.id.c_str()
        );
    }
    if (!inspect.registration_owner().empty() &&
        inspect.registration_owner() != record.spec.id) {
        tc::Log::warn(
            "TermModulesIntegration: inspect registration owner scope mismatch while ending module '%s'",
            record.spec.id.c_str()
        );
    }

    components.set_registration_owner("");
    inspect.set_registration_owner("");
}

bool cleanup_module_registrations(const termin_modules::ModuleRecord& record, std::string& error) {
    error.clear();

    try {
        const size_t inspect_count = tc::InspectRegistry::instance().unregister_owner(record.spec.id);
        const size_t component_count = ComponentRegistry::instance().unregister_owner(record.spec.id);
        if (inspect_count > 0 || component_count > 0) {
            tc::Log::info(
                "TermModulesIntegration: cleaned %zu inspect and %zu component registrations for module '%s'",
                inspect_count,
                component_count,
                record.spec.id.c_str()
            );
        }
        return true;
    } catch (const std::exception& e) {
        error = "Failed to clean module registrations for '" + record.spec.id + "': " + e.what();
        tc::Log::error("TermModulesIntegration: %s", error.c_str());
        return false;
    } catch (...) {
        error = "Failed to clean module registrations for '" + record.spec.id + "'";
        tc::Log::error("TermModulesIntegration: %s", error.c_str());
        return false;
    }
}

void degrade_module_components(const termin_modules::ModuleRecord& record) {
    const std::vector<std::string> type_names = module_component_types(record);
    if (type_names.empty()) {
        return;
    }

    const std::vector<TcSceneRef> scenes = collect_scenes();
    if (scenes.empty()) {
        tc::Log::warn(
            "TermModulesIntegration: no scenes available to degrade components for module '%s'",
            record.spec.id.c_str()
        );
        return;
    }

    for (const TcSceneRef& scene : scenes) {
        const UnknownComponentStats stats = degrade_components_to_unknown(scene, type_names);
        if (stats.failed > 0) {
            tc::Log::error(
                "TermModulesIntegration: failed to degrade %zu component instances for module '%s' in scene '%s'",
                stats.failed,
                record.spec.id.c_str(),
                scene.name().c_str()
            );
        }
    }
}

void upgrade_module_components(const termin_modules::ModuleRecord& record) {
    const std::vector<std::string> type_names = module_component_types(record);
    if (type_names.empty()) {
        return;
    }

    const std::vector<TcSceneRef> scenes = collect_scenes();
    if (scenes.empty()) {
        tc::Log::warn(
            "TermModulesIntegration: no scenes available to upgrade components for module '%s'",
            record.spec.id.c_str()
        );
        return;
    }

    for (const TcSceneRef& scene : scenes) {
        const UnknownComponentStats stats = upgrade_unknown_components(scene, type_names);
        if (stats.failed > 0) {
            tc::Log::error(
                "TermModulesIntegration: failed to upgrade %zu unknown component instances for module '%s' in scene '%s'",
                stats.failed,
                record.spec.id.c_str(),
                scene.name().c_str()
            );
        }
    }
}

} // namespace

void TermModulesIntegration::set_environment(termin_modules::ModuleEnvironment environment) {
    _environment = std::move(environment);
}

const termin_modules::ModuleEnvironment& TermModulesIntegration::environment() const {
    return _environment;
}

void TermModulesIntegration::configure_runtime(termin_modules::ModuleRuntime& runtime) const {
    runtime.set_environment(_environment);
    const bool sync_live_scenes = _environment.sync_live_scenes;

    auto before_unload = [sync_live_scenes](const termin_modules::ModuleRecord& record) {
        if (sync_live_scenes) {
            degrade_module_components(record);
        }
    };
    auto after_load = [sync_live_scenes](const termin_modules::ModuleRecord& record) {
        if (sync_live_scenes) {
            upgrade_module_components(record);
        }
    };
    auto restore_reload_state = [sync_live_scenes](const termin_modules::ModuleRecord& record,
                                                   const std::shared_ptr<termin_modules::IModuleReloadState>&,
                                                   std::string& error) {
        if (!sync_live_scenes) {
            return true;
        }

        const std::vector<std::string> type_names = module_component_types(record);
        if (type_names.empty()) {
            return true;
        }

        const std::vector<TcSceneRef> scenes = collect_scenes();
        for (const TcSceneRef& scene : scenes) {
            const UnknownComponentStats stats = upgrade_unknown_components(scene, type_names);
            if (stats.failed > 0) {
                error = "Failed to restore module component state for '" + record.spec.id + "'";
                return false;
            }
        }
        return true;
    };

    termin_modules::CppModuleCallbacks cpp_callbacks;
    cpp_callbacks.before_load = [](const termin_modules::ModuleRecord& record) {
        begin_module_registration_scope(record);
    };
    cpp_callbacks.after_failed_load = [](const termin_modules::ModuleRecord& record,
                                         const std::string&) {
        std::string error;
        cleanup_module_registrations(record, error);
        end_module_registration_scope(record);
    };
    cpp_callbacks.before_unload = before_unload;
    cpp_callbacks.before_native_close = [](const termin_modules::ModuleRecord& record,
                                           std::string& error) {
        return cleanup_module_registrations(record, error);
    };
    cpp_callbacks.after_load = [after_load](const termin_modules::ModuleRecord& record) {
        end_module_registration_scope(record);
        after_load(record);
    };
    cpp_callbacks.restore_reload_state = restore_reload_state;

    termin_modules::PythonModuleCallbacks python_callbacks;
    python_callbacks.before_load = [](const termin_modules::ModuleRecord& record) {
        begin_module_registration_scope(record);
    };
    python_callbacks.after_failed_load = [](const termin_modules::ModuleRecord& record,
                                            const std::string&) {
        std::string error;
        cleanup_module_registrations(record, error);
        end_module_registration_scope(record);
    };
    python_callbacks.before_unload = before_unload;
    python_callbacks.after_load = [after_load](const termin_modules::ModuleRecord& record) {
        end_module_registration_scope(record);
        after_load(record);
    };
    python_callbacks.restore_reload_state = restore_reload_state;

    runtime.set_cpp_callbacks(std::move(cpp_callbacks));
    runtime.set_python_callbacks(std::move(python_callbacks));
}

} // namespace termin
