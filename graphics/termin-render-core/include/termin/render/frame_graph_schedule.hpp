#pragma once

#include <array>
#include <span>
#include <string>
#include <string_view>
#include <unordered_set>
#include <vector>

#include <render/tc_frame_graph.h>
#include <termin/render/render_export.hpp>

namespace termin {
    class RenderPipeline;
    struct FrameGraphCaptureRequest;

    enum class FrameGraphPassReason {
        Unreachable,
        Dependency,
        Capture,
        RequiredResource,
        ColorExport,
        ExternalOutput,
        SideEffect,
    };

    struct FrameGraphSchedule {
        tc_pipeline_handle pipeline = TC_PIPELINE_HANDLE_INVALID;
        uint64_t pipeline_revision = 0;
        std::array<FrameGraphPassReason, TC_FRAME_GRAPH_MAX_PASSES> reasons{};
        std::array<size_t, TC_FRAME_GRAPH_MAX_PASSES> order{};
        size_t count = 0;
        bool valid = true;
        std::unordered_set<std::string_view> resources;
        std::vector<const char*> canonical_resources;
        // Index in the full graph for each request, or SIZE_MAX for an input.
        std::vector<size_t> capture_writers;

        std::span<const size_t> indices() const { return {order.data(), count}; }
        bool matches(tc_pipeline_handle handle) const {
            return tc_pipeline_handle_eq(pipeline, handle) && pipeline_revision != 0 &&
                   pipeline_revision == tc_pipeline_render_revision(handle);
        }
    };

    // The schedule borrows resource names from the pipeline and the requests.
    RENDER_CORE_API FrameGraphSchedule select_frame_graph_schedule(
        RenderPipeline& pipeline,
        tc_frame_graph* graph,
        std::span<FrameGraphCaptureRequest* const> captures = {},
        std::span<const std::string> required_resources = {});

    RENDER_CORE_API const char* frame_graph_pass_reason_name(FrameGraphPassReason reason);

    inline bool is_external_color_output(const char* name) {
        if (!name)
            return false;
        const std::string_view value(name);
        return value == "OUTPUT" || value == "DISPLAY" || value == "RT_COLOR";
    }

    inline bool is_external_depth_output(const char* name) {
        return name && std::string_view(name) == "RT_DEPTH";
    }

    inline bool is_external_output_resource(const char* name) {
        return is_external_color_output(name) || is_external_depth_output(name);
    }
}
