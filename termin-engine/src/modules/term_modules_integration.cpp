#include <termin/modules/term_modules_integration.hpp>

#include <tcbase/tc_log.hpp>

#include <termin/entity/unknown_component_ops.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/tc_scene.hpp>

#include <termin/scene/scene_manager.hpp>

#include <core/tc_component.h>
#include <tc_inspect_cpp.hpp>
#include <inspect/tc_runtime_type_registry.h>

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

struct ComponentUnloadContext {
    bool sync_live_scenes = false;
    const std::vector<TcSceneRef>* scenes = nullptr;
    const char* module_id = nullptr;
};

bool prepare_component_unload_for_runtime_type(
    const char* type_name,
    void* context,
    void*
) {
    auto* unload_context = static_cast<ComponentUnloadContext*>(context);
    if (!type_name || !unload_context || !unload_context->sync_live_scenes) {
        return true;
    }

    if (!unload_context->scenes || unload_context->scenes->empty()) {
        tc::Log::warn(
            "TermModulesIntegration: no scenes available to prepare component type '%s' for module '%s'",
            type_name,
            unload_context->module_id ? unload_context->module_id : "<unknown>"
        );
        return true;
    }

    const std::vector<std::string> type_names{type_name};
    bool ok = true;
    for (const TcSceneRef& scene : *unload_context->scenes) {
        const UnknownComponentStats stats = degrade_components_to_unknown(scene, type_names);
        if (stats.failed > 0) {
            ok = false;
            tc::Log::error(
                "TermModulesIntegration: failed to prepare %zu component instance(s) of type '%s' for module '%s' in scene '%s'",
                stats.failed,
                type_name,
                unload_context->module_id ? unload_context->module_id : "<unknown>",
                scene.name().c_str()
            );
        }
    }

    const size_t remaining = tc_runtime_type_registry_instance_count(type_name);
    if (remaining > 0) {
        ok = false;
        tc::Log::error(
            "TermModulesIntegration: component type '%s' still has %zu live instance(s) after prepare-unload for module '%s'",
            type_name,
            remaining,
            unload_context->module_id ? unload_context->module_id : "<unknown>"
        );
    }

    return ok;
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

bool cleanup_module_registrations(
    const termin_modules::ModuleRecord& record,
    std::string& error,
    bool sync_live_scenes
) {
    error.clear();

    try {
        std::vector<TcSceneRef> scenes;
        if (sync_live_scenes) {
            scenes = collect_scenes();
        }
        ComponentUnloadContext context{
            sync_live_scenes,
            &scenes,
            record.spec.id.c_str()
        };
        const size_t type_count =
            tc_runtime_type_registry_unregister_owner_with_context(
                record.spec.id.c_str(),
                &context
            );
        const std::vector<std::string> remaining_component_types =
            ComponentRegistry::instance().list_owned(record.spec.id);
        if (!remaining_component_types.empty()) {
            error = "Failed to clean module component registrations for '" + record.spec.id + "'";
            tc::Log::error("TermModulesIntegration: %s", error.c_str());
            return false;
        }
        if (type_count > 0) {
            tc::Log::info(
                "TermModulesIntegration: cleaned %zu runtime type registrations for module '%s'",
                type_count,
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
    tc_component_registry_set_prepare_unload_callback(
        prepare_component_unload_for_runtime_type,
        nullptr
    );

    auto cpp_before_unload = [](const termin_modules::ModuleRecord&) {};
    auto python_before_unload = [sync_live_scenes](const termin_modules::ModuleRecord& record) {
        std::string error;
        if (!cleanup_module_registrations(record, error, sync_live_scenes) &&
            !error.empty()) {
            tc::Log::error("TermModulesIntegration: %s", error.c_str());
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
    cpp_callbacks.before_native_init = [](const termin_modules::ModuleRecord& record) {
        begin_module_registration_scope(record);
    };
    cpp_callbacks.after_failed_load = [](const termin_modules::ModuleRecord& record,
                                         const std::string&) {
        std::string error;
        cleanup_module_registrations(record, error, false);
        end_module_registration_scope(record);
    };
    cpp_callbacks.before_unload = cpp_before_unload;
    cpp_callbacks.before_native_close = [sync_live_scenes](
                                            const termin_modules::ModuleRecord& record,
                                            std::string& error) {
        return cleanup_module_registrations(record, error, sync_live_scenes);
    };
    cpp_callbacks.after_native_init = [](const termin_modules::ModuleRecord& record) {
        end_module_registration_scope(record);
    };
    cpp_callbacks.after_load = [after_load](const termin_modules::ModuleRecord& record) {
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
        cleanup_module_registrations(record, error, false);
        end_module_registration_scope(record);
    };
    python_callbacks.before_unload = python_before_unload;
    python_callbacks.after_load = [after_load](const termin_modules::ModuleRecord& record) {
        end_module_registration_scope(record);
        after_load(record);
    };
    python_callbacks.restore_reload_state = restore_reload_state;

    runtime.set_cpp_callbacks(std::move(cpp_callbacks));
    runtime.set_python_callbacks(std::move(python_callbacks));
}

} // namespace termin
