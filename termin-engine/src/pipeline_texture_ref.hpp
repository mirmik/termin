#pragma once

#include <cstddef>
#include <cstring>

extern "C" {
#include "core/tc_scene.h"
#include "render/tc_render_target.h"
}

namespace termin::rendering_manager_detail {

enum class PipelineTextureRefKind {
    Empty,
    FileTexture,
    RenderTarget,
    NamedTexture,
};

struct PipelineTextureRef {
    PipelineTextureRefKind kind = PipelineTextureRefKind::Empty;
    const char* texture_name = nullptr;
    tc_render_target_handle render_target = TC_RENDER_TARGET_HANDLE_INVALID;
};

inline PipelineTextureRef classify_pipeline_texture_ref(
    const char* ref,
    tc_scene_handle preferred_scene,
    const tc_render_target_handle* render_targets,
    size_t render_target_count
) {
    if (!ref || ref[0] == '\0') {
        return {};
    }

    constexpr const char* file_prefix = "file:";
    constexpr size_t file_prefix_length = 5;
    if (std::strncmp(ref, file_prefix, file_prefix_length) == 0) {
        return {PipelineTextureRefKind::FileTexture, ref + file_prefix_length};
    }

    for (size_t i = 0; i < render_target_count; ++i) {
        tc_render_target_handle target = render_targets[i];
        if (!tc_render_target_handle_valid(target)) {
            continue;
        }
        const char* candidate = tc_render_target_get_name(target);
        if (!candidate || std::strcmp(candidate, ref) != 0) {
            continue;
        }
        if (tc_scene_handle_valid(preferred_scene)
                && !tc_scene_handle_eq(tc_render_target_get_scene(target), preferred_scene)) {
            continue;
        }
        return {PipelineTextureRefKind::RenderTarget, nullptr, target};
    }

    return {PipelineTextureRefKind::NamedTexture, ref};
}

} // namespace termin::rendering_manager_detail
