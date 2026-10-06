#include <termin/render/render_item_culling.hpp>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <mutex>

#include <tcbase/tc_log.hpp>
#include <tgfx/resources/tc_mesh.h>

namespace termin {
    namespace {
        std::atomic<bool> culling_enabled{true};
        std::mutex diagnostic_mutex;
        std::vector<RenderItemCullingDiagnostic> diagnostics;

        void log_invalid_bounds_once() {
            static std::atomic<bool> reported{false};
            if (!reported.exchange(true)) {
                tc::Log::error("[RenderItemCulling] invalid mesh bounds or non-affine/non-finite model matrix; "
                               "affected items remain visible (further reports suppressed)");
            }
        }

        void log_invalid_view_once() {
            static std::atomic<bool> reported{false};
            if (!reported.exchange(true)) {
                tc::Log::error("[RenderItemCulling] invalid frustum matrix; "
                               "affected views keep all items visible (further reports suppressed)");
            }
        }
    }

    bool transform_render_item_bounds(const tc_aabb& local, const Mat44f& model, tc_aabb& out_world) {
        if (!tc_aabb_is_valid(local) || !model.is_finite() || model(0, 3) != 0.0f ||
            model(1, 3) != 0.0f || model(2, 3) != 0.0f || model(3, 3) != 1.0f) {
            return false;
        }
        // Half-before-add avoids overflow for finite boxes with large coordinates.
        const double center[3] = {local.min_point.x * 0.5 + local.max_point.x * 0.5,
                                  local.min_point.y * 0.5 + local.max_point.y * 0.5,
                                  local.min_point.z * 0.5 + local.max_point.z * 0.5};
        const double extent[3] = {local.max_point.x * 0.5 - local.min_point.x * 0.5,
                                  local.max_point.y * 0.5 - local.min_point.y * 0.5,
                                  local.max_point.z * 0.5 - local.min_point.z * 0.5};
        double minimum[3], maximum[3];
        for (int row = 0; row < 3; ++row) {
            double c = model(3, row), e = 0.0;
            for (int col = 0; col < 3; ++col) {
                c += double(model(col, row)) * center[col];
                e += std::abs(double(model(col, row))) * extent[col];
            }
            minimum[row] = c - e;
            maximum[row] = c + e;
        }
        const tc_aabb result{{minimum[0], minimum[1], minimum[2]}, {maximum[0], maximum[1], maximum[2]}};
        if (!tc_aabb_is_valid(result)) {
            return false;
        }
        out_world = result;
        return true;
    }

    void update_render_item_world_bounds(tc_render_item& item) {
        item.world_bounds = tc_aabb_zero();
        item.bounds_state = TC_RENDER_ITEM_BOUNDS_UNSUPPORTED;
        if (item.kind != TC_RENDER_ITEM_KIND_MESH ||
            !(item.flags & TC_RENDER_ITEM_FLAG_CONSERVATIVE_MESH_BOUNDS) ||
            (item.flags & TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES)) {
            return;
        }
        item.bounds_state = TC_RENDER_ITEM_BOUNDS_MISSING;
        if (tc_mesh_handle_is_invalid(item.payload.mesh.mesh_handle)) {
            return;
        }
        tc_mesh* mesh = tc_mesh_get(item.payload.mesh.mesh_handle);
        tc_aabb local;
        if (!mesh || !tc_mesh_get_submesh_bounds(mesh, item.payload.mesh.submesh_index, &local)) {
            return;
        }
        const Mat44f model = (item.flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX)
                                ? Mat44f::from_column_major(item.model_matrix) : Mat44f::identity();
        if (!transform_render_item_bounds(local, model, item.world_bounds)) {
            item.bounds_state = TC_RENDER_ITEM_BOUNDS_INVALID;
            log_invalid_bounds_once();
            return;
        }
        item.bounds_state = TC_RENDER_ITEM_BOUNDS_VALID;
    }

    bool RenderItemCullingView::initialize_view(uint32_t index, const Mat44f& view, const Mat44f& projection) {
        const Mat44f clip = projection * view;
        if (!clip.is_finite()) {
            log_invalid_view_once();
            return false;
        }
        // left/right, bottom/top, near/far: row3 +/- row0/1, row2, row3-row2.
        for (int p = 0; p < 6; ++p) {
            double values[4];
            for (int col = 0; col < 4; ++col) {
                values[col] = p == 4 ? clip(col, 2)
                    : double(clip(col, 3)) + (p % 2 ? -1.0 : 1.0) * clip(col, p < 4 ? p / 2 : 2);
            }
            const double length = std::hypot(values[0], values[1], values[2]);
            if (!std::isfinite(length) || length == 0.0) {
                log_invalid_view_once();
                return false;
            }
            planes_[index][p] = {values[0] / length, values[1] / length, values[2] / length, values[3] / length};
        }
        return true;
    }

    RenderItemCullingView::RenderItemCullingView(const Mat44f& view, const Mat44f& projection) : view_count_(1) {
        valid_ = initialize_view(0, view, projection);
    }

    RenderItemCullingView::RenderItemCullingView(const RenderCamera& camera)
        : RenderItemCullingView(camera.view.to_float(), camera.projection.to_float()) {}

    RenderItemCullingView::RenderItemCullingView(const StereoRenderViews& stereo) : view_count_(2) {
        const bool left = initialize_view(0, stereo.left.view.to_float(), stereo.left.projection.to_float());
        const bool right = initialize_view(1, stereo.right.view.to_float(), stereo.right.projection.to_float());
        valid_ = left && right;
    }

    bool RenderItemCullingView::visible(const tc_render_item& item,
                                       RenderItemCullingCounters& counters,
                                       bool bounds_supported) const {
        ++counters.candidates;
        if (!render_item_culling_enabled()) {
            return true;
        }
        if (!valid_ || !bounds_supported || item.bounds_state != TC_RENDER_ITEM_BOUNDS_VALID ||
            !tc_aabb_is_valid(item.world_bounds)) {
            ++counters.without_bounds;
            return true;
        }
        ++counters.tested;
        for (uint32_t v = 0; v < view_count_; ++v) {
            bool intersects = true;
            for (const Plane& plane : planes_[v]) {
                const tc_aabb& box = item.world_bounds;
                const double x = plane.x >= 0 ? box.max_point.x : box.min_point.x;
                const double y = plane.y >= 0 ? box.max_point.y : box.min_point.y;
                const double z = plane.z >= 0 ? box.max_point.z : box.min_point.z;
                const double px = plane.x * x, py = plane.y * y, pz = plane.z * z;
                const double distance = px + py + pz + plane.w;
                // Covers float camera arithmetic and boxes touching a plane.
                const double epsilon = 1e-5 + 2e-6 * (std::abs(px) + std::abs(py) + std::abs(pz) + std::abs(plane.w));
                if (distance < -epsilon) {
                    intersects = false;
                    break;
                }
            }
            if (intersects) {
                return true;
            }
        }
        ++counters.culled;
        return false;
    }

    void set_render_item_culling_enabled(bool enabled) {
        culling_enabled.store(enabled, std::memory_order_relaxed);
    }

    bool render_item_culling_enabled() {
        return culling_enabled.load(std::memory_order_relaxed);
    }

    void publish_render_item_culling_counters(const char* target, const char* pass, int view_index,
                                              const RenderItemCullingCounters& counters) {
        const char* target_name = target ? target : "";
        const char* pass_name = pass ? pass : "";
        std::lock_guard<std::mutex> lock(diagnostic_mutex);
        for (auto& record : diagnostics) {
            if (record.view_index == view_index && record.target == target_name && record.pass == pass_name) {
                record.counters = counters;
                return;
            }
        }
        diagnostics.push_back({target_name, pass_name, view_index, counters});
    }

    std::vector<RenderItemCullingDiagnostic> get_render_item_culling_diagnostics() {
        std::lock_guard<std::mutex> lock(diagnostic_mutex);
        return diagnostics;
    }

    void clear_render_item_culling_diagnostics() {
        std::lock_guard<std::mutex> lock(diagnostic_mutex);
        diagnostics.clear();
    }
} // namespace termin
