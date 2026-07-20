#pragma once

#include "termin/render/render_topology.hpp"

#include <cstdint>

extern "C" {
#include "render/tc_display.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

namespace termin::rendering_manager_detail {

enum class OffscreenRenderJobKind {
    RenderTarget,
    ScenePipeline,
};

struct OffscreenRenderJob {
    OffscreenRenderJobKind kind = OffscreenRenderJobKind::RenderTarget;
    tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
    tc_render_target_handle render_target = TC_RENDER_TARGET_HANDLE_INVALID;
    tc_viewport_handle viewport = TC_VIEWPORT_HANDLE_INVALID;
    tc_pipeline_handle pipeline = TC_PIPELINE_HANDLE_INVALID;
};

enum class OffscreenRenderDiagnosticKind {
    AllocationFailure,
    DuplicateProducer,
    DisabledDependency,
    DependencyCycle,
};

struct OffscreenRenderDiagnostic {
    OffscreenRenderDiagnosticKind kind = OffscreenRenderDiagnosticKind::AllocationFailure;
    tc_render_target_handle render_target = TC_RENDER_TARGET_HANDLE_INVALID;
    uint32_t consumer_job = UINT32_MAX;
    uint32_t producer_job = UINT32_MAX;
};

using OffscreenRenderJobCallback = void (*)(void* user_data, const OffscreenRenderJob* job);
using OffscreenRenderDiagnosticCallback = void (*)(
    void* user_data,
    const OffscreenRenderDiagnostic* diagnostic
);

class OffscreenRenderPlanner {
public:
    OffscreenRenderPlanner();
    ~OffscreenRenderPlanner();

    OffscreenRenderPlanner(const OffscreenRenderPlanner&) = delete;
    OffscreenRenderPlanner& operator=(const OffscreenRenderPlanner&) = delete;

    bool execute(
        const RenderTopology& topology,
        tc_display_handle only_display,
        bool include_unattached_roots,
        OffscreenRenderJobCallback job_callback,
        void* job_user_data,
        OffscreenRenderDiagnosticCallback diagnostic_callback = nullptr,
        void* diagnostic_user_data = nullptr
    );

private:
    struct Impl;
    Impl* impl_ = nullptr;
};

void update_viewport_rects(
    const RenderTopology& topology,
    tc_display_handle only_display = TC_DISPLAY_HANDLE_INVALID
);

void sync_viewport_render_target_resolutions(
    const RenderTopology& topology,
    tc_display_handle only_display = TC_DISPLAY_HANDLE_INVALID
);

} // namespace termin::rendering_manager_detail
