// tc_scene_render_ext.hpp - Render extension functions for TcSceneRef
// These free functions extend TcSceneRef with render-specific functionality
// that depends on core_c render headers (render_mount, render_state, etc.)
#pragma once

#include <string>
#include <vector>

#include <termin/render/tc_scene_render_accessors.hpp>
#include <termin/tc_scene.hpp>
#include <termin/entity/entity.hpp>
#include "core/tc_scene_render_mount.h"
#include "core/tc_scene_render_state.h"
#include "core/tc_scene_skybox.h"
#include <termin/geom/vec3.hpp>
#include <termin/geom/vec4.hpp>
#include "termin/viewport_config.hpp"

namespace termin {

// Forward declarations
class TcScenePipelineTemplate;
class RenderPipeline;
class RenderingManager;

// ============================================================================
// TcSceneRef render extension functions
// ============================================================================

// --- Scene creation/destruction with render extensions ---

std::vector<tc_scene_ext_type_id> default_scene_extension_ids();

TcSceneRef create_scene_with_extensions(
    const std::string& name,
    const std::string& uuid,
    const std::vector<tc_scene_ext_type_id>& extensions
);

// Create scene with builtin render extensions attached (render_mount, render_state, collision_world)
TcSceneRef create_scene_with_render(const std::string& name = "", const std::string& uuid = "");

// Destroy scene and clean up render pipeline cache
void destroy_scene_with_render(TcSceneRef& scene);

// --- Viewport configs ---

void scene_add_viewport_config(const TcSceneRef& scene, const ViewportConfig& config);
void scene_remove_viewport_config(const TcSceneRef& scene, size_t index);
void scene_clear_viewport_configs(const TcSceneRef& scene);
size_t scene_viewport_config_count(const TcSceneRef& scene);
ViewportConfig scene_viewport_config_at(const TcSceneRef& scene, size_t index);
std::vector<ViewportConfig> scene_viewport_configs(const TcSceneRef& scene);

// --- Pipeline templates ---

void scene_add_pipeline_template(const TcSceneRef& scene, const TcScenePipelineTemplate& templ);
void scene_clear_pipeline_templates(const TcSceneRef& scene);
size_t scene_pipeline_template_count(const TcSceneRef& scene);
TcScenePipelineTemplate scene_pipeline_template_at(const TcSceneRef& scene, size_t index);

// --- Compiled pipelines ---

RenderPipeline* scene_get_pipeline(const TcSceneRef& scene, const std::string& name);
std::vector<std::string> scene_get_pipeline_names(const TcSceneRef& scene);
const std::vector<std::string>& scene_get_pipeline_targets(const std::string& name);

// --- Legacy adapter for load_from_data render mount/state ---

// Merge legacy render_mount/render_state fields into extensions dict.
// Called from the termin wrapper around load_from_data.
void scene_merge_legacy_render_extensions(const nos::trent& data, nos::trent& merged_extensions);

} // namespace termin
