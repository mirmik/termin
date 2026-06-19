#pragma once

#include <string>
#include <vector>

#include <termin/engine/termin_engine_api.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/render/tc_scene_render_ext.hpp>
#include <termin/tc_scene.hpp>

extern "C" {
#include "core/tc_scene_extension.h"
}

namespace termin {

// --- Scene creation/destruction with render extensions ---

TERMIN_ENGINE_API void register_default_scene_extensions();

TERMIN_ENGINE_API std::vector<tc_scene_ext_type_id> default_scene_extension_ids();

TERMIN_ENGINE_API TcSceneRef create_scene_with_extensions(
    const std::string& name,
    const std::string& uuid,
    const std::vector<tc_scene_ext_type_id>& extensions
);

// Create scene with builtin render extensions attached (render_mount, render_state, collision_world)
TERMIN_ENGINE_API TcSceneRef create_scene_with_render(const std::string& name = "", const std::string& uuid = "");

// Destroy scene and clean up render pipeline cache
TERMIN_ENGINE_API void destroy_scene_with_render(TcSceneRef& scene);

// --- Compiled pipelines ---

TERMIN_ENGINE_API RenderPipeline scene_get_pipeline(const TcSceneRef& scene, const std::string& name);
TERMIN_ENGINE_API std::vector<std::string> scene_get_pipeline_names(const TcSceneRef& scene);
TERMIN_ENGINE_API const std::vector<std::string>& scene_get_pipeline_targets(const std::string& name);

} // namespace termin
