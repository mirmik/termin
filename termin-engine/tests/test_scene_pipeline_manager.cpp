#include "scene_pipeline_manager.hpp"

#include <iostream>

int main()
{
    tc_scene_handle scene_a = tc_scene_new();
    tc_scene_handle scene_b = tc_scene_new();
    if (!tc_scene_handle_valid(scene_a) || !tc_scene_handle_valid(scene_b)) {
        std::cerr << "failed to create test scenes\n";
        return 1;
    }

    termin::rendering_manager_detail::ScenePipelineManager manager;
    manager.set_pipeline_targets(scene_a, "Main", {"AViewport"});
    manager.set_pipeline_targets(scene_b, "Main", {"BViewport"});

    const auto& a_targets = manager.get_pipeline_targets(scene_a, "Main");
    const auto& b_targets = manager.get_pipeline_targets(scene_b, "Main");
    if (a_targets != std::vector<std::string>{"AViewport"} ||
        b_targets != std::vector<std::string>{"BViewport"}) {
        std::cerr << "same-named scene pipelines overwrote target ownership\n";
        return 1;
    }

    manager.detach_scene(scene_a);
    if (!manager.get_pipeline_targets(scene_a, "Main").empty() ||
        manager.get_pipeline_targets(scene_b, "Main") != std::vector<std::string>{"BViewport"}) {
        std::cerr << "detaching one scene corrupted another scene's targets\n";
        return 1;
    }

    tc_scene_free(scene_a);
    tc_scene_free(scene_b);
    return 0;
}
