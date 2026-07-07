#pragma once

#include "termin/render/rendering_manager.hpp"

namespace termin::rendering_manager_detail {

void resolve_render_target_size_for_viewport(
    tc_render_target_handle rt,
    int viewport_width,
    int viewport_height,
    int& render_width,
    int& render_height
);

struct RenderTargetContextBuildRequest {
    RenderingManager& manager;
    RenderEngine* engine = nullptr;
    tc_render_target_handle rt = TC_RENDER_TARGET_HANDLE_INVALID;
    const std::string& base_context_name;
    tc_entity_handle internal_entities = TC_ENTITY_HANDLE_INVALID;
    int render_width = 0;
    int render_height = 0;
    const std::vector<tc_render_target_handle>& managed_render_targets;
    std::unordered_map<int, RenderTargetContextProvider>& providers;
    std::unordered_set<uint64_t>& missing_provider_warnings;
    std::unordered_map<std::string, RenderTargetContext>& contexts;
    std::string& default_context_name;
};

bool build_render_target_contexts(const RenderTargetContextBuildRequest& request);

} // namespace termin::rendering_manager_detail
