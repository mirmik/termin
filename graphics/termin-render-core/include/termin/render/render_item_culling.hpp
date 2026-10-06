#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include <core/tc_render_item.h>
#include <termin/render/render_camera.hpp>
#include <termin/render/render_export.hpp>

namespace termin {

    struct RenderItemCullingCounters {
        uint64_t candidates = 0;
        uint64_t tested = 0;
        uint64_t culled = 0;
        uint64_t without_bounds = 0;
        // Successful mesh encoder submissions, separately from candidate items.
        uint64_t mesh_draws = 0;
    };

    // Clip depth is the engine's [0,1] range, before backend conversion.
    // A stereo view accepts an item visible to either eye. Storage is fixed;
    // construction and per-item tests allocate no memory.
    class RENDER_CORE_API RenderItemCullingView {
        struct Plane {
            double x = 0, y = 0, z = 0, w = 0;
        };
        Plane planes_[2][6]{};
        uint32_t view_count_ = 0;
        bool valid_ = false;

        bool initialize_view(uint32_t index, const Mat44f& view, const Mat44f& projection);

    public:
        RenderItemCullingView() = default;
        RenderItemCullingView(const Mat44f& view, const Mat44f& projection);
        explicit RenderItemCullingView(const RenderCamera& camera);
        explicit RenderItemCullingView(const StereoRenderViews& stereo);
        bool visible(const tc_render_item& item,
                     RenderItemCullingCounters& counters,
                     bool bounds_supported = true) const;
    };

    // Recomputed after snapshot producers and static batching have finished.
    RENDER_CORE_API void update_render_item_world_bounds(tc_render_item& item);
    // Accepts finite affine matrices only; leaves output unchanged on failure.
    RENDER_CORE_API bool transform_render_item_bounds(const tc_aabb& local,
                                                      const Mat44f& model,
                                                      tc_aabb& out_world);

    RENDER_CORE_API void set_render_item_culling_enabled(bool enabled);
    RENDER_CORE_API bool render_item_culling_enabled();

    // Latest counters for each execution target/pass/view (cascade for shadows).
    // Strings and vector copies belong to diagnostic inspection, not item tests.
    struct RenderItemCullingDiagnostic {
        std::string target;
        std::string pass;
        int view_index = -1;
        RenderItemCullingCounters counters;
    };
    RENDER_CORE_API void publish_render_item_culling_counters(const char* target,
                                                             const char* pass,
                                                             int view_index,
                                                             const RenderItemCullingCounters& counters);
    RENDER_CORE_API std::vector<RenderItemCullingDiagnostic> get_render_item_culling_diagnostics();
    RENDER_CORE_API void clear_render_item_culling_diagnostics();

} // namespace termin
