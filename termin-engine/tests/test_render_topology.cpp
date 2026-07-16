#include "termin/render/render_topology.hpp"

#include <iostream>

int main()
{
    tc_scene_handle scene_a = tc_scene_new();
    tc_scene_handle scene_b = tc_scene_new();
    if (!tc_scene_handle_valid(scene_a) || !tc_scene_handle_valid(scene_b)) {
        std::cerr << "failed to create test scenes\n";
        return 1;
    }

    termin::RenderTopology topology;
    topology.set_pipeline_targets(scene_a, "Main", {"AViewport"});
    topology.set_pipeline_targets(scene_b, "Main", {"BViewport"});

    const auto& a_targets = topology.get_pipeline_targets(scene_a, "Main");
    const auto& b_targets = topology.get_pipeline_targets(scene_b, "Main");
    if (a_targets != std::vector<std::string>{"AViewport"} ||
        b_targets != std::vector<std::string>{"BViewport"}) {
        std::cerr << "same-named scene pipelines overwrote target ownership\n";
        return 1;
    }

    tc_render_target_handle target_a = tc_render_target_new("SharedTarget");
    tc_render_target_handle target_b = tc_render_target_new("SharedTarget");
    tc_render_target_set_scene(target_a, scene_a);
    tc_render_target_set_scene(target_b, scene_b);
    if (!topology.register_render_target(target_a) || !topology.register_render_target(target_b)) {
        std::cerr << "failed to register scene-owned targets\n";
        return 1;
    }
    if (!tc_render_target_handle_eq(topology.find_render_target(scene_a, "SharedTarget"), target_a) ||
        !tc_render_target_handle_eq(topology.find_render_target(scene_b, "SharedTarget"), target_b)) {
        std::cerr << "same-named render targets crossed scene ownership\n";
        return 1;
    }

    tc_render_target_handle duplicate_a = tc_render_target_new("SharedTarget");
    tc_render_target_set_scene(duplicate_a, scene_a);
    if (topology.register_render_target(duplicate_a)) {
        std::cerr << "same-scene duplicate render target name was accepted\n";
        return 1;
    }
    tc_render_target_free(duplicate_a);

    topology.unregister_render_target(target_a);
    if (tc_render_target_handle_valid(topology.find_render_target(scene_a, "SharedTarget")) ||
        !tc_render_target_handle_eq(topology.find_render_target(scene_b, "SharedTarget"), target_b)) {
        std::cerr << "unregistering one scene target corrupted another scene\n";
        return 1;
    }

    topology.unregister_render_target(target_b);

    tc_display* display_a = tc_display_new("DisplayA", nullptr);
    tc_display* display_b = tc_display_new("DisplayB", nullptr);
    tc_viewport_handle viewport_a = tc_viewport_new("SharedViewport", scene_a);
    tc_viewport_handle viewport_b = tc_viewport_new("SharedViewport", scene_b);
    tc_display_add_viewport(display_a, viewport_a);
    tc_display_add_viewport(display_b, viewport_b);
    if (!topology.register_viewport(scene_a, viewport_a, display_a)
            || !topology.register_viewport(scene_b, viewport_b, display_b)) {
        std::cerr << "failed to register scene viewport attachments\n";
        return 1;
    }
    if (!tc_viewport_handle_eq(topology.find_viewport(scene_a, "SharedViewport"), viewport_a)
            || !tc_viewport_handle_eq(topology.find_viewport(scene_b, "SharedViewport"), viewport_b)) {
        std::cerr << "same-named viewports crossed scene ownership\n";
        return 1;
    }
    if (topology.display_for_viewport(viewport_a) != display_a
            || topology.display_for_viewport(viewport_b) != display_b) {
        std::cerr << "viewport display association was not preserved\n";
        return 1;
    }
    topology.unregister_viewport(viewport_a);
    topology.unregister_viewport(viewport_b);
    tc_display_remove_viewport(display_a, viewport_a);
    tc_display_remove_viewport(display_b, viewport_b);
    tc_viewport_free(viewport_a);
    tc_viewport_free(viewport_b);
    tc_display_free(display_a);
    tc_display_free(display_b);

    topology.clear_all();
    tc_render_target_free(target_a);
    tc_render_target_free(target_b);
    tc_scene_free(scene_a);
    tc_scene_free(scene_b);
    return 0;
}
