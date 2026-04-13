#include "term_modules_integration.hpp"

#include <tcbase/tc_log.hpp>

#include <termin/entity/unknown_component_ops.hpp>
#include <termin/tc_scene.hpp>

#include "termin/scene/scene_manager.hpp"

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

const std::vector<std::string>& module_component_types(const termin_modules::ModuleRecord& record) {
    return record.spec.components;
}

void degrade_module_components(const termin_modules::ModuleRecord& record) {
    const std::vector<std::string>& type_names = module_component_types(record);
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
    const std::vector<std::string>& type_names = module_component_types(record);
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

    termin_modules::CppModuleCallbacks callbacks;
    callbacks.before_unload = [](const termin_modules::ModuleRecord& record) {
        degrade_module_components(record);
    };
    callbacks.after_load = [](const termin_modules::ModuleRecord& record) {
        upgrade_module_components(record);
    };

    runtime.set_cpp_callbacks(std::move(callbacks));
}

} // namespace termin
