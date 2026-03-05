// tc_scene_render_ext.cpp - Render extension functions for TcSceneRef
#include "termin/tc_scene_render_ext.hpp"
#include <termin/entity/entity.hpp>
#include "entity/tc_component_ref.hpp"
#include "render/rendering_manager.hpp"
#include "render/scene_pipeline_template.hpp"
#include "render/tc_value_trent.hpp"
#include "core/tc_scene_extension.h"
#include "physics/tc_collision_world.h"
#include <tcbase/tc_log.hpp>

namespace termin {

static void ensure_builtin_scene_extensions_registered() {
    tc_scene_render_mount_extension_init();
    tc_scene_render_state_extension_init();
    tc_collision_world_extension_init();
}

TcSceneRef create_scene_with_render(const std::string& name, const std::string& uuid) {
    ensure_builtin_scene_extensions_registered();

    TcSceneRef scene = TcSceneRef::create(name, uuid);
    tc_scene_handle h = scene.handle();

    if (tc_scene_handle_valid(h)) {
        if (!tc_scene_ext_attach(h, TC_SCENE_EXT_TYPE_RENDER_MOUNT)) {
            tc::Log::error("[create_scene_with_render] failed to attach render_mount extension");
        }
        if (!tc_scene_ext_attach(h, TC_SCENE_EXT_TYPE_RENDER_STATE)) {
            tc::Log::error("[create_scene_with_render] failed to attach render_state extension");
        }
        if (!tc_scene_ext_attach(h, TC_SCENE_EXT_TYPE_COLLISION_WORLD)) {
            tc::Log::warn("[create_scene_with_render] failed to attach collision_world extension");
        }
    }

    return scene;
}

void destroy_scene_with_render(TcSceneRef& scene) {
    if (scene.valid()) {
        RenderingManager::instance().clear_scene_pipelines(scene.handle());
        scene.destroy();
    }
}

// --- Background color ---

std::tuple<float, float, float, float> scene_get_background_color(const TcSceneRef& scene) {
    float r = 0, g = 0, b = 0, a = 1;
    if (tc_scene_render_state* state = tc_scene_render_state_get(scene._h)) {
        r = state->background_color[0];
        g = state->background_color[1];
        b = state->background_color[2];
        a = state->background_color[3];
    }
    return {r, g, b, a};
}

void scene_set_background_color(const TcSceneRef& scene, float r, float g, float b, float a) {
    if (!tc_scene_render_state_ensure(scene._h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(scene._h);
    if (!state) return;
    state->background_color[0] = r;
    state->background_color[1] = g;
    state->background_color[2] = b;
    state->background_color[3] = a;
}

Vec4 scene_background_color(const TcSceneRef& scene) {
    auto [r, g, b, a] = scene_get_background_color(scene);
    return Vec4(r, g, b, a);
}

void scene_set_background_color(const TcSceneRef& scene, const Vec4& color) {
    scene_set_background_color(scene,
        static_cast<float>(color.x),
        static_cast<float>(color.y),
        static_cast<float>(color.z),
        static_cast<float>(color.w)
    );
}

// --- Skybox ---

Vec3 scene_skybox_color(const TcSceneRef& scene) {
    float r = 0.5f, g = 0.7f, b = 0.9f;
    if (tc_scene_render_state* state = tc_scene_render_state_get(scene._h)) {
        r = state->skybox.color[0];
        g = state->skybox.color[1];
        b = state->skybox.color[2];
    }
    return Vec3(r, g, b);
}

void scene_set_skybox_color(const TcSceneRef& scene, const Vec3& color) {
    if (!tc_scene_render_state_ensure(scene._h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(scene._h);
    if (!state) return;
    state->skybox.color[0] = static_cast<float>(color.x);
    state->skybox.color[1] = static_cast<float>(color.y);
    state->skybox.color[2] = static_cast<float>(color.z);
}

Vec3 scene_skybox_top_color(const TcSceneRef& scene) {
    float r = 0.4f, g = 0.6f, b = 0.9f;
    if (tc_scene_render_state* state = tc_scene_render_state_get(scene._h)) {
        r = state->skybox.top_color[0];
        g = state->skybox.top_color[1];
        b = state->skybox.top_color[2];
    }
    return Vec3(r, g, b);
}

void scene_set_skybox_top_color(const TcSceneRef& scene, const Vec3& color) {
    if (!tc_scene_render_state_ensure(scene._h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(scene._h);
    if (!state) return;
    state->skybox.top_color[0] = static_cast<float>(color.x);
    state->skybox.top_color[1] = static_cast<float>(color.y);
    state->skybox.top_color[2] = static_cast<float>(color.z);
}

Vec3 scene_skybox_bottom_color(const TcSceneRef& scene) {
    float r = 0.6f, g = 0.5f, b = 0.4f;
    if (tc_scene_render_state* state = tc_scene_render_state_get(scene._h)) {
        r = state->skybox.bottom_color[0];
        g = state->skybox.bottom_color[1];
        b = state->skybox.bottom_color[2];
    }
    return Vec3(r, g, b);
}

void scene_set_skybox_bottom_color(const TcSceneRef& scene, const Vec3& color) {
    if (!tc_scene_render_state_ensure(scene._h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(scene._h);
    if (!state) return;
    state->skybox.bottom_color[0] = static_cast<float>(color.x);
    state->skybox.bottom_color[1] = static_cast<float>(color.y);
    state->skybox.bottom_color[2] = static_cast<float>(color.z);
}

// --- Ambient lighting ---

Vec3 scene_ambient_color(const TcSceneRef& scene) {
    tc_scene_render_state* state = tc_scene_render_state_get(scene._h);
    tc_scene_lighting* lit = state ? &state->lighting : nullptr;
    if (lit) {
        return Vec3(lit->ambient_color[0], lit->ambient_color[1], lit->ambient_color[2]);
    }
    return Vec3(1.0, 1.0, 1.0);
}

void scene_set_ambient_color(const TcSceneRef& scene, const Vec3& color) {
    if (!tc_scene_render_state_ensure(scene._h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(scene._h);
    tc_scene_lighting* lit = state ? &state->lighting : nullptr;
    if (lit) {
        lit->ambient_color[0] = static_cast<float>(color.x);
        lit->ambient_color[1] = static_cast<float>(color.y);
        lit->ambient_color[2] = static_cast<float>(color.z);
    }
}

float scene_ambient_intensity(const TcSceneRef& scene) {
    tc_scene_render_state* state = tc_scene_render_state_get(scene._h);
    tc_scene_lighting* lit = state ? &state->lighting : nullptr;
    return lit ? lit->ambient_intensity : 0.1f;
}

void scene_set_ambient_intensity(const TcSceneRef& scene, float intensity) {
    if (!tc_scene_render_state_ensure(scene._h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(scene._h);
    tc_scene_lighting* lit = state ? &state->lighting : nullptr;
    if (lit) {
        lit->ambient_intensity = intensity;
    }
}

// --- Lighting ---

tc_scene_lighting* scene_lighting(const TcSceneRef& scene) {
    tc_scene_render_state* state = tc_scene_render_state_get(scene._h);
    return state ? &state->lighting : nullptr;
}

// --- Viewport configs ---

void scene_add_viewport_config(const TcSceneRef& scene, const ViewportConfig& config) {
    tc_viewport_config c = config.to_c();
    tc_scene_add_viewport_config(scene._h, &c);
}

void scene_remove_viewport_config(const TcSceneRef& scene, size_t index) {
    tc_scene_remove_viewport_config(scene._h, index);
}

void scene_clear_viewport_configs(const TcSceneRef& scene) {
    tc_scene_clear_viewport_configs(scene._h);
}

size_t scene_viewport_config_count(const TcSceneRef& scene) {
    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene._h);
    return mount ? mount->viewport_config_count : 0;
}

ViewportConfig scene_viewport_config_at(const TcSceneRef& scene, size_t index) {
    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene._h);
    if (!mount || index >= mount->viewport_config_count) {
        return ViewportConfig();
    }
    tc_viewport_config* c = &mount->viewport_configs[index];
    return ViewportConfig::from_c(c);
}

std::vector<ViewportConfig> scene_viewport_configs(const TcSceneRef& scene) {
    std::vector<ViewportConfig> result;
    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene._h);
    size_t count = mount ? mount->viewport_config_count : 0;
    result.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        tc_viewport_config* c = &mount->viewport_configs[i];
        result.push_back(ViewportConfig::from_c(c));
    }
    return result;
}

// --- Pipeline templates ---

void scene_add_pipeline_template(const TcSceneRef& scene, const TcScenePipelineTemplate& templ) {
    tc_scene_add_pipeline_template(scene._h, templ.handle());
}

void scene_clear_pipeline_templates(const TcSceneRef& scene) {
    tc_scene_clear_pipeline_templates(scene._h);
}

size_t scene_pipeline_template_count(const TcSceneRef& scene) {
    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene._h);
    return mount ? mount->pipeline_template_count : 0;
}

TcScenePipelineTemplate scene_pipeline_template_at(const TcSceneRef& scene, size_t index) {
    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene._h);
    if (!mount || index >= mount->pipeline_template_count) {
        return TcScenePipelineTemplate(TC_SPT_HANDLE_INVALID);
    }
    return TcScenePipelineTemplate(mount->pipeline_templates[index]);
}

// --- Compiled pipelines ---

RenderPipeline* scene_get_pipeline(const TcSceneRef& scene, const std::string& name) {
    return RenderingManager::instance().get_scene_pipeline(scene._h, name);
}

std::vector<std::string> scene_get_pipeline_names(const TcSceneRef& scene) {
    return RenderingManager::instance().get_pipeline_names(scene._h);
}

const std::vector<std::string>& scene_get_pipeline_targets(const std::string& name) {
    return RenderingManager::instance().get_pipeline_targets(name);
}

// --- Legacy adapter ---

void scene_merge_legacy_render_extensions(const nos::trent& data, nos::trent& merged_extensions) {
    if (!merged_extensions.contains("render_mount")) {
        bool has_legacy_render_mount =
            (data.contains("viewport_configs") && data["viewport_configs"].is_list()) ||
            (data.contains("scene_pipelines") && data["scene_pipelines"].is_list());

        if (has_legacy_render_mount) {
            nos::trent render_mount;
            if (data.contains("viewport_configs") && data["viewport_configs"].is_list()) {
                render_mount["viewport_configs"] = data["viewport_configs"];
            }
            if (data.contains("scene_pipelines") && data["scene_pipelines"].is_list()) {
                render_mount["scene_pipelines"] = data["scene_pipelines"];
            }
            merged_extensions["render_mount"] = std::move(render_mount);
        }
    }

    if (!merged_extensions.contains("render_state")) {
        bool has_legacy_render_state =
            data.contains("background_color") ||
            data.contains("ambient_color") ||
            data.contains("ambient_intensity") ||
            data.contains("shadow_settings") ||
            data.contains("skybox_type") ||
            data.contains("skybox_color") ||
            data.contains("skybox_top_color") ||
            data.contains("skybox_bottom_color");

        if (has_legacy_render_state) {
            nos::trent render_state;

            if (data.contains("background_color")) {
                render_state["background_color"] = data["background_color"];
            }

            nos::trent lighting;
            bool has_lighting = false;
            if (data.contains("ambient_color")) {
                lighting["ambient_color"] = data["ambient_color"];
                has_lighting = true;
            }
            if (data.contains("ambient_intensity")) {
                lighting["ambient_intensity"] = data["ambient_intensity"];
                has_lighting = true;
            }
            if (data.contains("shadow_settings")) {
                lighting["shadow_settings"] = data["shadow_settings"];
                has_lighting = true;
            }
            if (has_lighting) {
                render_state["lighting"] = std::move(lighting);
            }

            nos::trent skybox;
            bool has_skybox = false;
            if (data.contains("skybox_type")) {
                std::string type_str = data["skybox_type"].as_string_default("gradient");
                int type_int = TC_SKYBOX_GRADIENT;
                if (type_str == "none") type_int = TC_SKYBOX_NONE;
                else if (type_str == "solid") type_int = TC_SKYBOX_SOLID;
                skybox["type"] = static_cast<int64_t>(type_int);
                has_skybox = true;
            }
            if (data.contains("skybox_color")) {
                skybox["color"] = data["skybox_color"];
                has_skybox = true;
            }
            if (data.contains("skybox_top_color")) {
                skybox["top_color"] = data["skybox_top_color"];
                has_skybox = true;
            }
            if (data.contains("skybox_bottom_color")) {
                skybox["bottom_color"] = data["skybox_bottom_color"];
                has_skybox = true;
            }
            if (has_skybox) {
                render_state["skybox"] = std::move(skybox);
            }

            merged_extensions["render_state"] = std::move(render_state);
        }
    }
}

} // namespace termin
