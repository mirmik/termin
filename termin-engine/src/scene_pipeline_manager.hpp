#pragma once

#include <string>
#include <unordered_map>
#include <vector>

extern "C" {
#include "core/tc_scene.h"
#include "render/tc_pipeline.h"
}

namespace termin::rendering_manager_detail {

class ScenePipelineManager {
public:
    void attach_scene(tc_scene_handle scene);
    void detach_scene(tc_scene_handle scene);

    tc_pipeline_handle get_scene_pipeline(tc_scene_handle scene, const std::string& name) const;
    tc_pipeline_handle get_scene_pipeline(const std::string& name) const;

    void set_pipeline_targets(const std::string& pipeline_name, const std::vector<std::string>& targets);
    const std::vector<std::string>& get_pipeline_targets(const std::string& pipeline_name) const;
    std::vector<std::string> get_pipeline_names(tc_scene_handle scene) const;

    void clear_scene_pipelines(tc_scene_handle scene);
    void clear_all_scene_pipelines();

private:
    static uint64_t scene_key(tc_scene_handle h);
    void destroy_scene_pipelines(tc_scene_handle scene, bool notify_detach);

    std::unordered_map<uint64_t, std::unordered_map<std::string, tc_pipeline_handle>> scene_pipelines_;
    std::unordered_map<std::string, std::vector<std::string>> pipeline_targets_;
};

} // namespace termin::rendering_manager_detail
