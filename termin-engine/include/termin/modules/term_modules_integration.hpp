#pragma once

#include <termin_modules/module_runtime.hpp>

#include <termin/engine/termin_engine_api.hpp>
#include <termin/tc_scene.hpp>

#include <functional>
#include <vector>

namespace termin {

class SceneManager;

class TERMIN_ENGINE_API TermModulesIntegration {
public:
    using SceneProvider = std::function<std::vector<TcSceneRef>()>;

    termin_modules::ModuleEnvironment _environment;
    SceneProvider _scene_provider;

public:
    void set_environment(termin_modules::ModuleEnvironment environment);
    const termin_modules::ModuleEnvironment& environment() const;
    void set_scene_provider(SceneProvider provider);
    void set_scene_manager(SceneManager& scene_manager);
    void clear_scene_provider();
    void configure_runtime(termin_modules::ModuleRuntime& runtime) const;
};

} // namespace termin
