#include <termin/modules/term_modules_integration.hpp>

#include <tcbase/tc_log.hpp>

#include <termin/entity/unknown_component_ops.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/tc_scene.hpp>
#include <termin/render/unknown_pass_ops.hpp>
#include <termin/scene/scene_manager.hpp>

#include <core/tc_component.h>
#include <render/tc_pass.h>
#include <tc_inspect_cpp.hpp>
#include <inspect/tc_runtime_type_registry.h>

#include <thread>
#include <stdexcept>

namespace termin {
namespace {

std::vector<TcSceneRef> collect_scenes(
    const TermModulesIntegration::SceneProvider& provider
) {
    return provider ? provider() : std::vector<TcSceneRef>{};
}

std::vector<std::string> module_component_types(const termin_modules::ModuleRecord& record) {
    return ComponentRegistry::instance().list_owned(record.spec.id);
}

std::vector<std::string> module_pass_types_for_owner(const std::string& module_id) {
    std::vector<std::string> result;
    const size_t count = tc_pass_registry_type_count();
    for (size_t i = 0; i < count; ++i) {
        const char* type_name = tc_pass_registry_type_at(i);
        const char* owner = type_name
            ? tc_runtime_type_registry_get_owner(type_name)
            : nullptr;
        if (owner && module_id == owner) {
            result.emplace_back(type_name);
        }
    }
    return result;
}

std::vector<std::string> module_pass_types(const termin_modules::ModuleRecord& record) {
    return module_pass_types_for_owner(record.spec.id);
}

std::vector<std::string> module_runtime_types(const termin_modules::ModuleRecord& record) {
    std::vector<std::string> result;
    const size_t count = tc_runtime_type_registry_type_count();
    for (size_t i = 0; i < count; ++i) {
        const char* type_name = tc_runtime_type_registry_type_at(i);
        const char* owner = type_name
            ? tc_runtime_type_registry_get_owner(type_name)
            : nullptr;
        if (owner && record.spec.id == owner) result.emplace_back(type_name);
    }
    return result;
}

struct RuntimeUnloadContext {
    bool sync_live_scenes = false;
    const std::vector<TcSceneRef>* scenes = nullptr;
    const char* module_id = nullptr;
    bool component_batch_attempted = false;
    bool component_batch_ok = false;
    bool pass_batch_attempted = false;
    bool pass_batch_ok = false;
};

bool prepare_component_unload_for_runtime_type(
    const char* type_name,
    void* context,
    void*
) {
    auto* unload_context = static_cast<RuntimeUnloadContext*>(context);
    if (!type_name || !unload_context || !unload_context->sync_live_scenes) {
        return true;
    }

    if (!unload_context->scenes || unload_context->scenes->empty()) {
        const size_t remaining = tc_runtime_type_registry_instance_count(type_name);
        if (remaining == 0) {
            return true;
        }
        tc::Log::error(
            "TermModulesIntegration: cannot prepare component type '%s' for module '%s': "
            "no managed scenes are available while %zu live instance(s) remain",
            type_name,
            unload_context->module_id ? unload_context->module_id : "<unknown>",
            remaining
        );
        return false;
    }

    if (!unload_context->component_batch_attempted) {
        unload_context->component_batch_attempted = true;
        const std::vector<std::string> type_names =
            ComponentRegistry::instance().list_owned(
                unload_context->module_id ? unload_context->module_id : "");
        UnknownComponentDegradationPlan plan;
        std::string error;
        unload_context->component_batch_ok = prepare_components_to_unknown(
            *unload_context->scenes,
            type_names,
            plan,
            &error
        ) && plan.commit(&error);
        if (!unload_context->component_batch_ok) {
            tc::Log::error(
                "TermModulesIntegration: failed to prepare component batch for module '%s': %s",
                unload_context->module_id ? unload_context->module_id : "<unknown>",
                error.c_str()
            );
            return false;
        }
    }

    const size_t remaining = tc_runtime_type_registry_instance_count(type_name);
    if (remaining > 0) {
        unload_context->component_batch_ok = false;
        tc::Log::error(
            "TermModulesIntegration: component type '%s' still has %zu live instance(s) after prepare-unload for module '%s'",
            type_name,
            remaining,
            unload_context->module_id ? unload_context->module_id : "<unknown>"
        );
    }

    return unload_context->component_batch_ok;
}

bool prepare_pass_unload_for_runtime_type(
    const char* type_name,
    void* context,
    void*
) {
    auto* unload_context = static_cast<RuntimeUnloadContext*>(context);
    if (!type_name) return false;

    const size_t before = tc_runtime_type_registry_instance_count(type_name);
    if (before == 0) return true;
    if (!unload_context || !unload_context->sync_live_scenes) {
        tc::Log::error(
            "TermModulesIntegration: refusing to unload pass type '%s' with %zu live "
            "instance(s) while live-state synchronization is disabled",
            type_name,
            before
        );
        return false;
    }

    if (!unload_context->pass_batch_attempted) {
        unload_context->pass_batch_attempted = true;
        const std::vector<std::string> type_names = module_pass_types_for_owner(
            unload_context->module_id ? unload_context->module_id : "");
        UnknownPassDegradationPlan plan;
        std::string error;
        unload_context->pass_batch_ok = prepare_passes_to_unknown(
            type_names,
            plan,
            &error
        ) && plan.commit(&error);
        if (!unload_context->pass_batch_ok) {
            tc::Log::error(
                "TermModulesIntegration: failed to prepare pass batch for module '%s': %s",
                unload_context->module_id ? unload_context->module_id : "<unknown>",
                error.c_str()
            );
            return false;
        }
    }
    const size_t remaining = tc_runtime_type_registry_instance_count(type_name);
    if (remaining > 0) {
        unload_context->pass_batch_ok = false;
        tc::Log::error(
            "TermModulesIntegration: pass type '%s' still has %zu live "
            "instance(s) after prepared pipeline degradation",
            type_name,
            remaining
        );
    }
    return unload_context->pass_batch_ok;
}

void rollback_module_placeholders(
    const termin_modules::ModuleRecord& record,
    const TermModulesIntegration::SceneProvider& scene_provider
) {
    const std::vector<std::string> component_types = module_component_types(record);
    if (!component_types.empty()) {
        for (const TcSceneRef& scene : collect_scenes(scene_provider)) {
            const UnknownComponentStats stats =
                upgrade_unknown_components(scene, component_types);
            if (stats.failed > 0) {
                tc::Log::error(
                    "TermModulesIntegration: rollback failed for %zu component placeholder(s) "
                    "after refused unload of module '%s'",
                    stats.failed,
                    record.spec.id.c_str()
                );
            }
        }
    }
    const UnknownPassStats pass_stats = upgrade_unknown_passes(module_pass_types(record));
    if (pass_stats.failed > 0) {
        tc::Log::error(
            "TermModulesIntegration: rollback failed for %zu pass placeholder(s) after "
            "refused unload of module '%s'",
            pass_stats.failed,
            record.spec.id.c_str()
        );
    }
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
    bool sync_live_scenes,
    const TermModulesIntegration::SceneProvider& scene_provider
) {
    error.clear();

    try {
        std::vector<TcSceneRef> scenes;
        if (sync_live_scenes) {
            scenes = collect_scenes(scene_provider);
        }
        RuntimeUnloadContext context{
            sync_live_scenes,
            &scenes,
            record.spec.id.c_str()
        };
        const size_t type_count =
            tc_runtime_type_registry_unregister_owner_with_context(
                record.spec.id.c_str(),
                &context
            );
        const std::vector<std::string> remaining_types = module_runtime_types(record);
        if (!remaining_types.empty()) {
            if (sync_live_scenes) rollback_module_placeholders(record, scene_provider);
            error = "Failed to clean module registrations for '" + record.spec.id + "'";
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

bool prepare_module_registration_unload(
    const termin_modules::ModuleRecord& record,
    std::string& error,
    bool sync_live_scenes,
    const TermModulesIntegration::SceneProvider& scene_provider
) {
    error.clear();
    try {
        std::vector<TcSceneRef> scenes;
        if (sync_live_scenes) {
            scenes = collect_scenes(scene_provider);
        }
        RuntimeUnloadContext context{
            sync_live_scenes,
            &scenes,
            record.spec.id.c_str()
        };
        if (!tc_runtime_type_registry_prepare_owner_unload(record.spec.id.c_str(), &context)) {
            if (sync_live_scenes) rollback_module_placeholders(record, scene_provider);
            error = "Failed to prepare module registrations for unload: '" + record.spec.id + "'";
            tc::Log::error("TermModulesIntegration: %s", error.c_str());
            return false;
        }
        return true;
    } catch (const std::exception& e) {
        error = "Failed to prepare module registrations for '" + record.spec.id + "': " + e.what();
        tc::Log::error("TermModulesIntegration: %s", error.c_str());
        return false;
    } catch (...) {
        error = "Failed to prepare module registrations for '" + record.spec.id + "'";
        tc::Log::error("TermModulesIntegration: %s", error.c_str());
        return false;
    }
}

void upgrade_module_components(
    const termin_modules::ModuleRecord& record,
    const TermModulesIntegration::SceneProvider& scene_provider
) {
    const std::vector<std::string> type_names = module_component_types(record);
    if (type_names.empty()) {
        return;
    }

    const std::vector<TcSceneRef> scenes = collect_scenes(scene_provider);
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

bool upgrade_module_passes(
    const termin_modules::ModuleRecord& record,
    std::string* error = nullptr
) {
    const std::vector<std::string> type_names = module_pass_types(record);
    if (type_names.empty()) return true;
    const UnknownPassStats stats = upgrade_unknown_passes(type_names);
    if (stats.failed == 0) return true;
    if (error) {
        *error = "Failed to restore module pass state for '" + record.spec.id + "'";
    }
    tc::Log::error(
        "TermModulesIntegration: failed to upgrade %zu unknown pass instance(s) for module '%s'",
        stats.failed,
        record.spec.id.c_str()
    );
    return false;
}

} // namespace

void TermModulesIntegration::set_environment(termin_modules::ModuleEnvironment environment) {
    _environment = std::move(environment);
}

const termin_modules::ModuleEnvironment& TermModulesIntegration::environment() const {
    return _environment;
}

void TermModulesIntegration::set_scene_provider(SceneProvider provider) {
    _scene_provider = std::move(provider);
}

void TermModulesIntegration::set_scene_manager(SceneManager& scene_manager) {
    set_scene_provider([manager = &scene_manager]() {
        std::vector<TcSceneRef> scenes;
        for (const std::string& name : manager->scene_names()) {
            tc_scene_handle scene = manager->get_scene(name);
            if (tc_scene_alive(scene)) {
                scenes.emplace_back(scene);
            }
        }
        return scenes;
    });
}

void TermModulesIntegration::clear_scene_provider() {
    _scene_provider = nullptr;
}

void TermModulesIntegration::configure_runtime(termin_modules::ModuleRuntime& runtime) const {
    runtime.set_environment(_environment);
    const std::thread::id owner_thread = std::this_thread::get_id();
    runtime.set_mutation_thread_checker([owner_thread](std::string& error) {
        if (std::this_thread::get_id() == owner_thread) {
            return true;
        }
        error = "Live module mutation must run on the integration owner thread";
        return false;
    });
    const bool sync_live_scenes = _environment.sync_live_scenes;
    const SceneProvider scene_provider = _scene_provider;
    if (sync_live_scenes && !scene_provider) {
        throw std::invalid_argument(
            "TermModulesIntegration requires a scene provider when sync_live_scenes is enabled"
        );
    }
    tc_component_registry_set_prepare_unload_callback(
        prepare_component_unload_for_runtime_type,
        nullptr
    );
    tc_pass_registry_set_prepare_unload_callback(
        prepare_pass_unload_for_runtime_type,
        nullptr
    );

    auto cpp_before_unload = [sync_live_scenes, scene_provider](
                                 const termin_modules::ModuleRecord& record,
                                 std::string& error) {
        return prepare_module_registration_unload(
            record,
            error,
            sync_live_scenes,
            scene_provider
        );
    };
    auto after_load = [sync_live_scenes, scene_provider](
                          const termin_modules::ModuleRecord& record) {
        if (sync_live_scenes) {
            upgrade_module_components(record, scene_provider);
            upgrade_module_passes(record);
        }
    };
    auto restore_reload_state = [sync_live_scenes, scene_provider](
                                    const termin_modules::ModuleRecord& record,
                                    const std::shared_ptr<termin_modules::IModuleReloadState>&,
                                    std::string& error) {
        if (!sync_live_scenes) {
            return true;
        }

        const std::vector<std::string> type_names = module_component_types(record);

        const std::vector<TcSceneRef> scenes = collect_scenes(scene_provider);
        for (const TcSceneRef& scene : scenes) {
            const UnknownComponentStats stats = upgrade_unknown_components(scene, type_names);
            if (stats.failed > 0) {
                error = "Failed to restore module component state for '" + record.spec.id + "'";
                return false;
            }
        }
        return upgrade_module_passes(record, &error);
    };

    termin_modules::CppModuleCallbacks cpp_callbacks;
    cpp_callbacks.before_native_init = [](const termin_modules::ModuleRecord& record) {
        begin_module_registration_scope(record);
    };
    cpp_callbacks.after_failed_load = [](const termin_modules::ModuleRecord& record,
                                         const std::string&) {
        std::string error;
        cleanup_module_registrations(record, error, false, {});
        end_module_registration_scope(record);
    };
    cpp_callbacks.before_unload = cpp_before_unload;
    cpp_callbacks.before_native_close = [sync_live_scenes, scene_provider](
                                            const termin_modules::ModuleRecord& record,
                                            std::string& error) {
        return cleanup_module_registrations(
            record,
            error,
            sync_live_scenes,
            scene_provider
        );
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
        cleanup_module_registrations(record, error, false, {});
        end_module_registration_scope(record);
    };
    python_callbacks.before_module_remove = [sync_live_scenes, scene_provider](
                                                  const termin_modules::ModuleRecord& record,
                                                  std::string& error) {
        return prepare_module_registration_unload(
            record,
            error,
            sync_live_scenes,
            scene_provider
        );
    };
    python_callbacks.after_load = [after_load](const termin_modules::ModuleRecord& record) {
        end_module_registration_scope(record);
        after_load(record);
    };
    python_callbacks.restore_reload_state = restore_reload_state;

    runtime.set_cpp_callbacks(std::move(cpp_callbacks));
    runtime.set_python_callbacks(std::move(python_callbacks));
}

} // namespace termin
