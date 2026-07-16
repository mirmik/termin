#pragma once

#include "termin/engine/termin_engine_api.hpp"

#include <string>
#include <unordered_map>
#include <vector>

extern "C" {
#include "core/tc_scene.h"
#include "render/tc_pipeline.h"
#include "render/tc_render_target.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"
}

namespace termin {

class TERMIN_ENGINE_API RenderTopology {
public:
    struct ViewportAttachment {
        tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
        tc_viewport_handle viewport = TC_VIEWPORT_HANDLE_INVALID;
        tc_display* display = nullptr;
        bool destroy_on_scene_detach = true;
    };

private:
    struct SceneRecord {
        tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
        std::unordered_map<std::string, tc_pipeline_handle> pipelines;
        std::unordered_map<std::string, std::vector<std::string>> pipeline_targets;
        std::vector<tc_render_target_handle> render_targets;
        std::vector<tc_viewport_handle> viewports;
        bool attached = false;
    };

    std::unordered_map<uint64_t, SceneRecord> scenes_;
    std::vector<tc_scene_handle> attached_scenes_;
    std::vector<tc_render_target_handle> managed_render_targets_;
    std::vector<ViewportAttachment> viewport_attachments_;

public:
    RenderTopology() = default;
    ~RenderTopology();

    RenderTopology(const RenderTopology&) = delete;
    RenderTopology& operator=(const RenderTopology&) = delete;

    // Compile and atomically install one scene's pipeline topology.
    bool attach_scene(tc_scene_handle scene);

    // Notify components while attachments are alive, then destroy pipelines.
    void detach_scene(tc_scene_handle scene);

    bool is_attached(tc_scene_handle scene) const;
    const std::vector<tc_scene_handle>& attached_scenes() const { return attached_scenes_; }

    tc_pipeline_handle get_pipeline(tc_scene_handle scene, const std::string& name) const;
    std::vector<std::string> get_pipeline_names(tc_scene_handle scene) const;
    void set_pipeline_targets(
        tc_scene_handle scene,
        const std::string& pipeline_name,
        const std::vector<std::string>& targets
    );
    const std::vector<std::string>& get_pipeline_targets(
        tc_scene_handle scene,
        const std::string& pipeline_name
    ) const;

    bool register_render_target(tc_render_target_handle render_target);
    bool unregister_render_target(tc_render_target_handle render_target);
    tc_render_target_handle find_render_target(
        tc_scene_handle scene,
        const std::string& name
    ) const;
    const std::vector<tc_render_target_handle>& render_targets(tc_scene_handle scene) const;
    const std::vector<tc_render_target_handle>& managed_render_targets() const {
        return managed_render_targets_;
    }

    bool register_viewport(
        tc_scene_handle scene,
        tc_viewport_handle viewport,
        tc_display* display,
        bool destroy_on_scene_detach = true
    );
    bool unregister_viewport(tc_viewport_handle viewport);
    const std::vector<tc_viewport_handle>& viewports(tc_scene_handle scene) const;
    const std::vector<ViewportAttachment>& viewport_attachments() const {
        return viewport_attachments_;
    }
    tc_viewport_handle find_viewport(
        tc_scene_handle scene,
        const std::string& name
    ) const;
    tc_display* display_for_viewport(tc_viewport_handle viewport) const;

    void clear_scene_pipelines(tc_scene_handle scene, bool notify_detach = true);
    void clear_all();

private:
    static uint64_t scene_key(tc_scene_handle scene);
    SceneRecord* find_record(tc_scene_handle scene);
    const SceneRecord* find_record(tc_scene_handle scene) const;
    SceneRecord& ensure_record(tc_scene_handle scene);
    void destroy_pipelines(SceneRecord& record);
    void erase_record_if_empty(uint64_t key);
};

} // namespace termin
