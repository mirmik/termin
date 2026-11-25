#include "termin_visual_scene/annotation_geometry3d.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <numbers>
#include <termin/geom/color.hpp>
#include <termin/geom/vec2.hpp>

namespace termin::visual {
    namespace {

        // Clip in homogeneous coordinates before dividing by W. Only the two
        // depth planes matter here: a marker centered outside a side plane can
        // still cover pixels inside the viewport.
        double depth_distance(const Vec4& p, int plane) {
            return plane == 0 ? p.z : p.w - p.z;
        }

        bool clip_line(Vec4& a, Vec4& b) {
            for (int plane = 0; plane < 2; ++plane) {
                const double da = depth_distance(a, plane), db = depth_distance(b, plane);
                if (da < 0 && db < 0)
                    return false;
                if ((da < 0) != (db < 0)) {
                    const Vec4 intersection = a + (b - a) * (da / (da - db));
                    (da < 0 ? a : b) = intersection;
                }
            }
            return a.w > 0 && b.w > 0;
        }

        // A convex quad clipped by two planes has at most six vertices. Allow
        // both stages to double their input for unordered application corners.
        using Polygon = std::array<Vec4, 16>;
        size_t clip_polygon(Polygon& points, size_t count, int plane) {
            Polygon clipped;
            size_t n = 0;
            for (size_t i = 0; i < count; ++i) {
                const Vec4& a = points[(i + count - 1) % count];
                const Vec4& b = points[i];
                const double da = depth_distance(a, plane), db = depth_distance(b, plane);
                if ((da < 0) != (db < 0))
                    clipped[n++] = a + (b - a) * (da / (da - db));
                if (db >= 0)
                    clipped[n++] = b;
            }
            std::copy_n(clipped.begin(), n, points.begin());
            return n;
        }

        struct TriangleStream {
            std::vector<float>& vertices;
            double half_width, half_height;
            LinearColor color{};

            // Centered screen pixels, Y down, matching Termin clip space.
            Vec2 pixel(Vec4 p) const {
                return {half_width * p.x / p.w, half_height * p.y / p.w};
            }

            void vertex(Vec2 p, double coverage) {
                vertices.insert(vertices.end(),
                                {static_cast<float>(p.x / half_width),
                                 static_cast<float>(p.y / half_height),
                                 0.5f,
                                 color.r,
                                 color.g,
                                 color.b,
                                 color.a * static_cast<float>(coverage)});
            }

            void strip(Vec2 a, Vec2 b, Vec2 c, Vec2 d, double ab_coverage, double cd_coverage) {
                vertex(a, ab_coverage);
                vertex(b, ab_coverage);
                vertex(c, cd_coverage);
                vertex(a, ab_coverage);
                vertex(c, cd_coverage);
                vertex(d, cd_coverage);
            }

            void line(Vec2 a, Vec2 b, double width) {
                const auto delta = b - a;
                const double length = std::hypot(delta.x, delta.y);
                if (length <= 1e-8)
                    return;
                const Vec2 normal{-delta.y / length, delta.x / length};
                const auto outer = normal * (0.5 * (width + 1));
                const auto inner = normal * (0.5 * std::abs(width - 1));
                const double coverage = std::min(1.0, width);
                strip(a - outer, b - outer, b - inner, a - inner, 0, coverage);
                strip(a - inner, b - inner, b + inner, a + inner, coverage, coverage);
                strip(a + inner, b + inner, b + outer, a + outer, coverage, 0);
            }

            void marker(Vec2 center, double radius, double stroke, bool ring) {
                const double outer = ring ? radius + stroke * 0.5 : radius;
                const double hole = ring ? radius - stroke * 0.5 : 0;
                const double inner = hole > 0 ? hole : -outer;
                // Filter the radial interval by one physical pixel. Its
                // coverage is piecewise linear, even for subpixel rings.
                const double radii[] = {std::max(0.0, inner - 0.5),
                                        std::max(0.0, std::min(inner + 0.5, outer - 0.5)),
                                        std::max(0.0, std::max(inner + 0.5, outer - 0.5)),
                                        outer + 0.5};
                double coverage[4];
                for (int j = 0; j < 4; ++j)
                    coverage[j] = std::max(0.0, std::min(outer, radii[j] + 0.5) - std::max(inner, radii[j] - 0.5));
                const int segments = static_cast<int>(std::clamp(std::ceil(8 * std::sqrt(outer)), 12.0, 256.0));
                Vec2 from{1, 0};
                for (int i = 1; i <= segments; ++i) {
                    const double theta = 2 * std::numbers::pi * i / segments;
                    const Vec2 to{std::cos(theta), std::sin(theta)};
                    for (int j = 0; j < 3; ++j) {
                        if (radii[j + 1] <= radii[j])
                            continue;
                        strip(center + from * radii[j],
                              center + to * radii[j],
                              center + to * radii[j + 1],
                              center + from * radii[j + 1],
                              coverage[j],
                              coverage[j + 1]);
                    }
                    from = to;
                }
            }
        };
    } // namespace

    void append_annotation_triangles(std::vector<float>& vertices,
                                     const tc_visual_annotation_packet3d& packet,
                                     const tc_affine3d& world_from_local,
                                     const Mat44& view_projection,
                                     uint32_t width,
                                     uint32_t height,
                                     float pixels_per_dip) {
        if (width == 0 || height == 0)
            return;
        TriangleStream stream{vertices, width * 0.5, height * 0.5};
        for (size_t i = 0; i < packet.count; ++i) {
            const auto& command = packet.commands[i];
            const auto rgba = command.rgba;
            stream.color = srgb_to_linear({(rgba >> 24) / 255.f,
                                           ((rgba >> 16) & 255) / 255.f,
                                           ((rgba >> 8) & 255) / 255.f,
                                           (rgba & 255) / 255.f});
            auto clip_point = [&](int index) {
                const auto& p = command.points[index];
                const Vec3 world = tc_affine3d_transform_point(world_from_local, {p[0], p[1], p[2]});
                return view_projection.transform_homogeneous({world.x, world.y, world.z, 1});
            };
            const double stroke = static_cast<double>(command.width_dip) * pixels_per_dip;
            Vec4 first = clip_point(0);
            if (command.kind == TC_VISUAL_ANNOTATION_QUAD) {
                Polygon points{first, clip_point(1), clip_point(2), clip_point(3)};
                size_t count = clip_polygon(points, 4, 0);
                count = clip_polygon(points, count, 1);
                if (std::any_of(points.begin(), points.begin() + count, [](Vec4 p) { return p.w <= 0; }))
                    continue;
                for (size_t j = 2; j < count; ++j) {
                    stream.vertex(stream.pixel(points[0]), 1);
                    stream.vertex(stream.pixel(points[j - 1]), 1);
                    stream.vertex(stream.pixel(points[j]), 1);
                }
            } else if (command.kind == TC_VISUAL_ANNOTATION_DISC || command.kind == TC_VISUAL_ANNOTATION_RING) {
                if (first.w > 0 && first.z >= 0 && first.z <= first.w)
                    stream.marker(stream.pixel(first),
                                  command.radius_dip * double(pixels_per_dip),
                                  stroke,
                                  command.kind == TC_VISUAL_ANNOTATION_RING);
            } else {
                Vec4 second = clip_point(1);
                const bool visible_tip = second.w > 0 && second.z >= 0 && second.z <= second.w;
                if (!clip_line(first, second))
                    continue;
                const auto a = stream.pixel(first), b = stream.pixel(second);
                stream.line(a, b, stroke);
                if (command.kind == TC_VISUAL_ANNOTATION_ARROW && visible_tip) {
                    const auto delta = b - a;
                    const double length = std::hypot(delta.x, delta.y);
                    if (length < 2 * pixels_per_dip)
                        continue;
                    const double head = std::min(length * 0.38, command.head_dip * double(pixels_per_dip));
                    const Vec2 shaft = delta * (head / length);
                    const Vec2 side{-shaft.y * 0.45, shaft.x * 0.45};
                    stream.line(b, b - shaft + side, stroke);
                    stream.line(b, b - shaft - side, stroke);
                }
            }
        }
    }
} // namespace termin::visual
