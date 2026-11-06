#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <string>
#include <utility>
#include <vector>

#include "orbit_camera_state.hpp"
#include "tcplot/plot_scene3d_render_item_source.hpp"

namespace tcplot::detail {

    using GridPoint3D = std::array<double, 3>;

    inline std::array<bool, 3> cartesian_grid_back_high(const PlotScene3DFrameRenderState& frame) {
        const auto camera = camera_from_state(frame.camera);
        const auto eye = camera.eye();
        const auto direction = eye - camera.target;
        std::array<bool, 3> result{};
        for (size_t axis = 0; axis < 3; ++axis) {
            const double center = (frame.bounds_min[axis] + frame.bounds_max[axis]) * 0.5 * frame.axis_scale[axis];
            const double toward_eye = camera.projection_type == termin::CameraProjection::Orthographic
                ? direction[axis] : eye[axis] - center;
            result[axis] = toward_eye * frame.axis_scale[axis] < 0.0;
        }
        return result;
    }

    struct GridScreenPoint {
        double x = 0.0, y = 0.0;
    };

    struct CartesianAxisEdge {
        GridPoint3D start{}, end{};
        GridScreenPoint outward{};
        bool visible = false;
    };

    inline termin::Vec3 grid_world_point(const PlotScene3DFrameRenderState& frame, const GridPoint3D& point) {
        return {point[0] * frame.axis_scale[0], point[1] * frame.axis_scale[1], point[2] * frame.axis_scale[2]};
    }

    // Pick actual silhouette edges in projection. This also handles panning,
    // negative legacy axis scales and views from below the coordinate box.
    inline std::array<CartesianAxisEdge, 3> cartesian_axis_edges(const PlotScene3DFrameRenderState& frame) {
        const auto camera = camera_from_state(frame.camera);
        const termin::Rect2 viewport{0, 0, 100, 100};
        std::array<GridScreenPoint, 8> corners{};
        for (size_t corner = 0; corner < 8; ++corner) {
            GridPoint3D point{};
            for (size_t axis = 0; axis < 3; ++axis)
                point[axis] = (corner & (1u << axis)) ? frame.bounds_max[axis] : frame.bounds_min[axis];
            const auto projected = camera.try_project_world_point(grid_world_point(frame, point), viewport);
            if (!projected)
                return {};
            corners[corner] = {projected->screen.x, projected->screen.y};
        }
        std::array<CartesianAxisEdge, 3> result{};
        for (size_t axis = 0; axis < 3; ++axis) {
            double best = -1e30;
            for (size_t corner = 0; corner < 8; ++corner) {
                if (corner & (1u << axis))
                    continue;
                const auto a = corners[corner];
                const auto b = corners[corner | (1u << axis)];
                const double length = std::hypot(b.x - a.x, b.y - a.y);
                if (length < 1e-5)
                    continue;
                GridScreenPoint normal{-(b.y - a.y) / length, (b.x - a.x) / length};
                double low = 0.0, high = 0.0;
                for (const auto& point : corners) {
                    const double distance = normal.x * (point.x - a.x) + normal.y * (point.y - a.y);
                    low = std::min(low, distance);
                    high = std::max(high, distance);
                }
                if (low < -1e-5 && high > 1e-5)
                    continue;
                if (high > 1e-5) {
                    normal.x = -normal.x;
                    normal.y = -normal.y;
                }
                // Horizontal axes prefer the lower contour; Z prefers the left.
                const double score = axis == 2 ? -(a.x + b.x) * 0.5 : (a.y + b.y) * 0.5;
                if (score <= best)
                    continue;
                best = score;
                auto& edge = result[axis];
                edge.visible = true;
                edge.outward = normal;
                for (size_t coordinate = 0; coordinate < 3; ++coordinate)
                    edge.start[coordinate] = (corner & (1u << coordinate))
                        ? frame.bounds_max[coordinate] : frame.bounds_min[coordinate];
                edge.end = edge.start;
                edge.end[axis] = frame.bounds_max[axis];
            }
        }
        return result;
    }

    inline std::array<int, 3> cartesian_grid_axis_edge_key(const PlotScene3DFrameRenderState& frame) {
        const auto edges = cartesian_axis_edges(frame);
        std::array<int, 3> key{-1, -1, -1};
        for (size_t axis = 0; axis < 3; ++axis) {
            if (!edges[axis].visible)
                continue;
            key[axis] = 0;
            for (size_t coordinate = 0; coordinate < 3; ++coordinate)
                if (edges[axis].start[coordinate] == frame.bounds_max[coordinate])
                    key[axis] |= 1 << coordinate;
        }
        return key;
    }

    template<class Emit>
    void for_each_cartesian_grid_line(const PlotScene3DFrameRenderState& frame, Emit emit) {
        const auto back = cartesian_grid_back_high(frame);
        for (size_t face = 0; face < 3; ++face) {
            for (size_t axis = 0; axis < 3; ++axis) {
                if (axis == face)
                    continue;
                const size_t along = 3 - face - axis;
                for (double tick : axes::nice_ticks(frame.bounds_min[axis], frame.bounds_max[axis], 8)) {
                    GridPoint3D a = frame.bounds_min;
                    a[face] = back[face] ? frame.bounds_max[face] : frame.bounds_min[face];
                    a[axis] = tick;
                    auto b = a;
                    b[along] = frame.bounds_max[along];
                    emit(a, b, -1);
                }
            }
        }
        const auto edges = cartesian_axis_edges(frame);
        for (size_t axis = 0; axis < 3; ++axis) {
            if (edges[axis].visible)
                emit(edges[axis].start, edges[axis].end, static_cast<int>(axis));
        }
    }

    struct CartesianGridLabel {
        std::string text;
        double x = 0.0, y = 0.0, width = 0.0, height = 0.0;
        float size = 14.0f;
    };

    // Measurement is supplied by the renderer; layout can be tested without GPU.
    template<class Measure>
    std::vector<CartesianGridLabel> cartesian_grid_labels(
        const PlotScene3DFrameRenderState& frame, int width, int height, Measure measure) {
        std::vector<CartesianGridLabel> labels;
        if (width <= 0 || height <= 0)
            return labels;
        const auto camera = camera_from_state(frame.camera);
        const termin::Rect2 viewport{0, 0, static_cast<double>(width), static_cast<double>(height)};
        const auto edges = cartesian_axis_edges(frame);
        const std::string* titles[] = {&frame.x_label, &frame.y_label, &frame.z_label};
        for (size_t axis = 0; axis < 3; ++axis) {
            const auto& edge = edges[axis];
            if (!edge.visible)
                continue;
            const auto a = camera.try_project_world_point(grid_world_point(frame, edge.start), viewport);
            const auto b = camera.try_project_world_point(grid_world_point(frame, edge.end), viewport);
            if (!a || !b)
                continue;
            const double length = (b->screen - a->screen).norm();
            if (length < 24.0)
                continue;
            // Recompute the perpendicular for the actual viewport aspect ratio.
            GridScreenPoint normal{-(b->screen.y - a->screen.y) / length,
                                    (b->screen.x - a->screen.x) / length};
            if (normal.x * edge.outward.x + normal.y * edge.outward.y < 0.0) {
                normal.x = -normal.x;
                normal.y = -normal.y;
            }
            double spacing = 28.0;
            for (const auto& tick : plot_axis3d_display_ticks(frame.axis_display[axis],
                     frame.bounds_min[axis], frame.bounds_max[axis], 6)) {
                const auto size = measure(tick.label, 14.0f);
                const double along_edge = std::abs(b->screen.x - a->screen.x) / length * size.x +
                                          std::abs(b->screen.y - a->screen.y) / length * size.y;
                spacing = std::max(spacing, along_edge + 14.0);
            }
            const int count = std::clamp(static_cast<int>(length / spacing), 2, 8);
            const auto ticks = plot_axis3d_display_ticks(frame.axis_display[axis],
                frame.bounds_min[axis], frame.bounds_max[axis], count);
            double tick_extent = 0.0;
            for (const auto& tick : ticks) {
                const auto size = measure(tick.label, 14.0f);
                tick_extent = std::max(tick_extent, std::abs(normal.x) * size.x + std::abs(normal.y) * size.y);
            }
            const auto place = [&](const std::string& text, const GridPoint3D& point, float size, double gap) {
                if (text.empty())
                    return;
                const auto projected = camera.try_project_world_point(grid_world_point(frame, point), viewport);
                if (!projected)
                    return;
                const auto extent = measure(text, size);
                const double distance = gap + (std::abs(normal.x) * extent.x + std::abs(normal.y) * extent.y) * 0.5;
                CartesianGridLabel label{text, projected->screen.x + normal.x * distance - extent.x * 0.5,
                    projected->screen.y + normal.y * distance - extent.y * 0.5, extent.x, extent.y, size};
                if (label.x < 3 || label.y < 3 || label.x + label.width > width - 3 || label.y + label.height > height - 3)
                    return;
                for (const auto& placed : labels) {
                    if (label.x < placed.x + placed.width + 5 && label.x + label.width + 5 > placed.x &&
                        label.y < placed.y + placed.height + 4 && label.y + label.height + 4 > placed.y)
                        return;
                }
                labels.push_back(std::move(label));
            };
            auto middle = edge.start;
            middle[axis] = (frame.bounds_min[axis] + frame.bounds_max[axis]) * 0.5;
            place(*titles[axis], middle, 16.0f, 16.0 + tick_extent);
            for (const auto& tick : ticks) {
                auto point = edge.start;
                point[axis] = tick.value;
                place(tick.label, point, 14.0f, 7.0);
            }
        }
        return labels;
    }

} // namespace tcplot::detail
