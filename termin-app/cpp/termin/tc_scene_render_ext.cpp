// tc_scene_render_ext.cpp - Render extension functions for TcSceneRef
#include "termin/tc_scene_render_ext.hpp"
#include <termin/render/rendering_manager.hpp>
#include "core/tc_scene_extension.h"
#include "core/tc_scene_extension_ids.h"
#include <tcbase/tc_log.hpp>

namespace termin {

std::vector<tc_scene_ext_type_id> default_scene_extension_ids() {
    return {
        TC_SCENE_EXT_TYPE_RENDER_MOUNT,
        TC_SCENE_EXT_TYPE_RENDER_STATE,
        TC_SCENE_EXT_TYPE_COLLISION_WORLD,
    };
}

TcSceneRef create_scene_with_extensions(
    const std::string& name,
    const std::string& uuid,
    const std::vector<tc_scene_ext_type_id>& extensions
) {
    TcSceneRef scene = TcSceneRef::create(name, uuid);
    tc_scene_handle h = scene.handle();

    if (tc_scene_handle_valid(h)) {
        for (tc_scene_ext_type_id type_id : extensions) {
            if (!tc_scene_ext_attach(h, type_id)) {
                tc::Log::error("[create_scene_with_extensions] failed to attach scene extension %llu",
                               (unsigned long long)type_id);
            }
        }
    }

    return scene;
}

TcSceneRef create_scene_with_render(const std::string& name, const std::string& uuid) {
    return create_scene_with_extensions(name, uuid, default_scene_extension_ids());
}

void destroy_scene_with_render(TcSceneRef& scene) {
    if (scene.valid()) {
        RenderingManager::instance().clear_scene_pipelines(scene.handle());
        scene.destroy();
    }
}

RenderPipeline scene_get_pipeline(const TcSceneRef& scene, const std::string& name) {
    return RenderPipeline(RenderingManager::instance().get_scene_pipeline(scene._h, name));
}

std::vector<std::string> scene_get_pipeline_names(const TcSceneRef& scene) {
    return RenderingManager::instance().get_pipeline_names(scene._h);
}

const std::vector<std::string>& scene_get_pipeline_targets(const std::string& name) {
    return RenderingManager::instance().get_pipeline_targets(name);
}

} // namespace termin
