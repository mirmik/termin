#include "tcplot/plot_heatmap_item2d.hpp"

#include "tcplot/styles.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <tcbase/tc_log.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

namespace tcplot {
    namespace {
        constexpr const char* kType = "tcplot.PlotHeatmapItem2D";
        constexpr const char* kShader = "termin-engine-tcplot-2d-heatmap";

        bool valid_bounds(PlotRange2D b) {
            return std::isfinite(b.x_min()) && std::isfinite(b.x_max()) && std::isfinite(b.y_min()) &&
                   std::isfinite(b.y_max()) && std::isfinite(b.x_span()) && std::isfinite(b.y_span()) &&
                   b.x_span() > 0 && b.y_span() > 0;
        }
        bool valid_style(tc_plot_heatmap_style2d s) {
            return s.colormap >= TC_PLOT_COLORMAP_JET_2D && s.colormap < TC_PLOT_COLORMAP_SOLID_2D &&
                   std::isfinite(s.scalar_min) && std::isfinite(s.scalar_max) && s.scalar_max > s.scalar_min &&
                   (s.interpolation == TC_PLOT_HEATMAP_NEAREST_2D || s.interpolation == TC_PLOT_HEATMAP_BILINEAR_2D);
        }
        bool valid_data(std::span<const double> values, uint32_t rows, uint32_t columns, PlotRange2D bounds) {
            return rows > 0 && columns > 0 && uint64_t(rows) * columns == values.size() && valid_bounds(bounds) &&
                   std::none_of(values.begin(), values.end(), [](double v) { return std::isinf(v); });
        }
        tc_plot_range2d c_bounds(PlotRange2D b) {
            return {b.x_min(), b.x_max(), b.y_min(), b.y_max()};
        }
        PlotRange2D cpp_bounds(tc_plot_range2d b) {
            return {b.x_min, b.x_max, b.y_min, b.y_max};
        }

        // Keep the upload normalized independently of the display range. The CPU keeps
        // full double values, while GPU palette/range edits never upload the matrix.
        double normalized(double value, double lo, double hi) {
            const double span = hi - lo;
            if (std::isfinite(span)) {
                const double difference = value - lo;
                if (std::isfinite(difference))
                    return difference / span;
            }
            return (value * 0.5 - lo * 0.5) / (hi * 0.5 - lo * 0.5);
        }
        std::pair<double, double> data_range(std::span<const double> values) {
            double lo = std::numeric_limits<double>::infinity(), hi = -lo;
            for (double value : values) {
                if (std::isnan(value))
                    continue;
                lo = std::min(lo, value);
                hi = std::max(hi, value);
            }
            if (!std::isfinite(lo))
                return {0, 1};
            if (lo == hi) {
                const double pad = std::max(std::abs(lo) * 1e-6, 0.5);
                lo = std::max(-std::numeric_limits<double>::max(), lo - pad);
                hi = std::min(std::numeric_limits<double>::max(), hi + pad);
            }
            return {lo, hi};
        }
        void bump(uint64_t& revision) {
            if (++revision == 0)
                revision = 1;
        }

        struct HeatmapPush {
            float matrix[16];
            float range[4];
        };
        static_assert(sizeof(HeatmapPush) == 80);

        struct HeatmapGpu {
            tgfx::IRenderDevice* device = nullptr;
            tgfx::BufferHandle quad{};
            tgfx::TextureHandle data{}, palette{};
            tgfx::SamplerHandle nearest{}, linear{};
            uint32_t rows = 0, columns = 0;
            bool data_dirty = true, palette_dirty = true;
            ~HeatmapGpu() {
                release();
            }
            void release() {
                if (device) {
                    if (quad)
                        device->destroy(quad);
                    if (data)
                        device->destroy(data);
                    if (palette)
                        device->destroy(palette);
                    if (nearest)
                        device->destroy(nearest);
                    if (linear)
                        device->destroy(linear);
                }
                device = nullptr;
                quad = {};
                data = {};
                palette = {};
                nearest = {};
                linear = {};
                rows = columns = 0;
                data_dirty = palette_dirty = true;
            }
        };
    } // namespace

    struct PlotHeatmapItem2D::State {
        PlotProjection2D projection;
        std::vector<double> values;
        uint32_t rows, columns;
        PlotRange2D bounds;
        tc_plot_heatmap_style2d style;
        double data_min = 0, data_max = 1;
        uint64_t revision = 1;
        HeatmapGpu gpu;
        State(
            PlotProjection2D p, std::vector<double> v, uint32_t r, uint32_t c, PlotRange2D b, tc_plot_heatmap_style2d s)
            : projection(p),
              values(std::move(v)),
              rows(r),
              columns(c),
              bounds(b),
              style(s) {
            update_range();
        }
        void update_range() {
            const auto r = data_range(values);
            data_min = r.first;
            data_max = r.second;
        }
        double scalar_min() const {
            return style.auto_range ? data_min : style.scalar_min;
        }
        double scalar_max() const {
            return style.auto_range ? data_max : style.scalar_max;
        }
    };

    namespace {
        class HeatmapBatch final : public tgfx::RetainedDrawBatch2D {
            std::shared_ptr<PlotHeatmapItem2D::State> state_;

        public:
            explicit HeatmapBatch(std::shared_ptr<PlotHeatmapItem2D::State> state)
                : state_(std::move(state)) {}
            bool draw(tgfx::RenderContext2& context, const tgfx::RetainedDrawState2D& draw) override {
                auto& s = *state_;
                auto& gpu = s.gpu;
                if (draw.unsupported_clip) {
                    tc::Log::error("Heatmap requires rectangular clip");
                    return false;
                }
                const auto projection = s.projection.snapshot();
                if (!projection) {
                    tc::Log::error("Heatmap projection is stale");
                    return false;
                }
                if (gpu.device != &context.device())
                    gpu.release();
                gpu.device = &context.device();
                auto& device = *gpu.device;
                static tc_shader_handle handle = tc_shader_handle_invalid();
                if (!tc_shader_is_valid(handle))
                    handle = tgfx::register_builtin_shader_from_catalog(kShader);
                tc_shader* raw = tc_shader_get(handle);
                tgfx::ShaderHandle vs{}, fs{};
                if (!raw || !termin::tc_shader_ensure_tgfx2(raw, &device, &vs, &fs)) {
                    tc::Log::error("Heatmap failed to prepare shader");
                    return false;
                }
                if (!gpu.quad) {
                    constexpr std::array<float, 12> vertices{0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1};
                    tgfx::BufferDesc desc;
                    desc.size = sizeof(vertices);
                    desc.usage = tgfx::BufferUsage::Vertex | tgfx::BufferUsage::CopyDst;
                    gpu.quad = device.create_buffer(desc);
                    if (gpu.quad)
                        device.upload_buffer(gpu.quad,
                                             {reinterpret_cast<const uint8_t*>(vertices.data()), sizeof(vertices)});
                }
                if (!gpu.nearest || !gpu.linear) {
                    tgfx::SamplerDesc desc;
                    desc.min_filter = desc.mag_filter = desc.mip_filter = tgfx::FilterMode::Nearest;
                    desc.address_u = desc.address_v = desc.address_w = tgfx::AddressMode::ClampToEdge;
                    if (!gpu.nearest)
                        gpu.nearest = device.create_sampler(desc);
                    desc.min_filter = desc.mag_filter = tgfx::FilterMode::Linear;
                    if (!gpu.linear)
                        gpu.linear = device.create_sampler(desc);
                }
                if (!gpu.data || gpu.rows != s.rows || gpu.columns != s.columns) {
                    if (gpu.data)
                        device.destroy(gpu.data);
                    tgfx::TextureDesc desc;
                    desc.width = s.columns;
                    desc.height = s.rows;
                    desc.format = tgfx::PixelFormat::RG32F;
                    desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
                    gpu.data = device.create_texture(desc);
                    gpu.rows = s.rows;
                    gpu.columns = s.columns;
                    gpu.data_dirty = true;
                }
                if (!gpu.palette) {
                    tgfx::TextureDesc desc;
                    desc.width = 257;
                    desc.height = 1;
                    desc.format = tgfx::PixelFormat::RGBA32F;
                    desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
                    gpu.palette = device.create_texture(desc);
                    gpu.palette_dirty = true;
                }
                if (!gpu.data || !gpu.palette || !gpu.quad || !gpu.nearest || !gpu.linear) {
                    tc::Log::error("Heatmap GPU resource allocation failed (%ux%u)", s.columns, s.rows);
                    return false;
                }
                if (gpu.data_dirty) {
                    std::vector<float> values;
                    values.reserve(s.values.size() * 2);
                    for (double v : s.values) {
                        const bool valid = !std::isnan(v);
                        values.push_back(valid ? static_cast<float>(normalized(v, s.data_min, s.data_max)) : 0.0f);
                        values.push_back(valid ? 1.0f : 0.0f);
                    }
                    device.upload_texture(
                        gpu.data, {reinterpret_cast<const uint8_t*>(values.data()), values.size() * sizeof(float)});
                    gpu.data_dirty = false;
                }
                if (gpu.palette_dirty) {
                    std::array<float, 257 * 4> colors{};
                    for (size_t i = 0; i < 257; ++i) {
                        const float t = static_cast<float>(i) / 256.0f;
                        const auto color = termin::srgb_to_linear(styles::colormap(
                            static_cast<SurfaceColorMap>(s.style.colormap), s.style.colormap_reversed ? 1 - t : t));
                        colors[i * 4] = color.r;
                        colors[i * 4 + 1] = color.g;
                        colors[i * 4 + 2] = color.b;
                        colors[i * 4 + 3] = 1;
                    }
                    device.upload_texture(gpu.palette,
                                          {reinterpret_cast<const uint8_t*>(colors.data()), sizeof(colors)});
                    gpu.palette_dirty = false;
                }
                const auto& frame = projection->frame;
                const auto& view = frame.viewport();
                const auto viewport =
                    draw.transform.transform_bounds({view.x(), view.y(), view.right(), view.bottom()});
                const float width = viewport.x1 - viewport.x0, height = viewport.y1 - viewport.y0;
                if (width <= 0 || height <= 0)
                    return true;
                context.set_viewport(static_cast<int>(std::floor(viewport.x0)),
                                     static_cast<int>(std::floor(viewport.y0)),
                                     static_cast<int>(std::ceil(width)),
                                     static_cast<int>(std::ceil(height)));
                const auto clip =
                    draw.has_clip_rect ? draw.clip_rect : termin::Rect2f{viewport.x0, viewport.y0, width, height};
                if (clip.width <= 0 || clip.height <= 0)
                    return true;
                context.set_scissor(static_cast<int>(std::floor(clip.x)),
                                    static_cast<int>(std::floor(clip.y)),
                                    static_cast<int>(std::ceil(clip.width)),
                                    static_cast<int>(std::ceil(clip.height)));
                context.set_depth_test(false);
                context.set_blend(true);
                context.set_blend_func(tgfx::BlendFactor::SrcAlpha, tgfx::BlendFactor::OneMinusSrcAlpha);
                context.set_cull(tgfx::CullMode::None);
                context.bind_shader(vs, fs);
                context.use_shader_resource_layout(raw);
                tgfx::VertexBufferLayout layout;
                layout.stride = sizeof(float) * 2;
                layout.attributes.push_back({0, tgfx::VertexFormat::Float2, 0, "POSITION"});
                context.set_vertex_layout(layout);
                context.set_topology(tgfx::PrimitiveTopology::TriangleList);
                const auto low = frame.data_to_pixel(s.bounds.x_min(), s.bounds.y_min());
                const auto high = frame.data_to_pixel(s.bounds.x_max(), s.bounds.y_max());
                const auto origin = draw.transform.transform_point({low.x, low.y});
                const auto vx = draw.transform.transform_vector({high.x - low.x, 0});
                const auto vy = draw.transform.transform_vector({0, high.y - low.y});
                HeatmapPush push{};
                push.matrix[0] = 2 * vx.x / width;
                push.matrix[1] = 2 * vx.y / height;
                push.matrix[4] = 2 * vy.x / width;
                push.matrix[5] = 2 * vy.y / height;
                push.matrix[10] = push.matrix[15] = 1;
                push.matrix[12] = 2 * (origin.x - viewport.x0) / width - 1;
                push.matrix[13] = 2 * (origin.y - viewport.y0) / height - 1;
                const double lo = normalized(s.scalar_min(), s.data_min, s.data_max);
                const double hi = normalized(s.scalar_max(), s.data_min, s.data_max);
                push.range[0] = static_cast<float>(std::clamp(lo, -1e20, 1e20));
                push.range[1] = static_cast<float>(std::clamp(hi, -1e20, 1e20));
                push.range[2] = draw.opacity;
                context.bind_uniform_data("tcplot2d_heatmap_draw", &push, sizeof(push));
                context.bind_texture("u_values",
                                     gpu.data,
                                     s.style.interpolation == TC_PLOT_HEATMAP_BILINEAR_2D ? gpu.linear : gpu.nearest);
                context.bind_texture("u_palette", gpu.palette, gpu.linear);
                context.draw_arrays(gpu.quad, 6);
                return true;
            }
        };
    } // namespace

    PlotHeatmapItem2D::PlotHeatmapItem2D(
        PlotProjection2D p, std::vector<double> v, uint32_t r, uint32_t c, PlotRange2D b, tc_plot_heatmap_style2d style)
        : NativeGraphicItem2D(kType),
          state_(std::make_shared<State>(p, std::move(v), r, c, b, style)) {
        if (!p.valid() || !valid_data(state_->values, r, c, b) || !valid_style(style))
            throw std::invalid_argument("invalid heatmap state");
        batch_ = std::make_shared<HeatmapBatch>(state_);
    }
    PlotHeatmapItem2D::~PlotHeatmapItem2D() = default;
    bool PlotHeatmapItem2D::set_projection(PlotProjection2D projection) {
        if (!projection.valid() ||
            (!tc_graphic_item_handle_is_invalid(handle()) && projection.handle().scene_id != handle().scene_id)) {
            tc::Log::error("Heatmap rejected stale or cross-scene projection");
            return false;
        }
        state_->projection = projection;
        bump(state_->revision);
        return true;
    }
    bool PlotHeatmapItem2D::set_data(std::vector<double> values, uint32_t rows, uint32_t columns, PlotRange2D bounds) {
        if (!valid_data(values, rows, columns, bounds)) {
            tc::Log::error("Heatmap rejected invalid grid data");
            return false;
        }
        state_->values = std::move(values);
        state_->rows = rows;
        state_->columns = columns;
        state_->bounds = bounds;
        state_->update_range();
        state_->gpu.data_dirty = true;
        bump(state_->revision);
        return true;
    }
    bool PlotHeatmapItem2D::set_style(tc_plot_heatmap_style2d style) {
        if (!valid_style(style)) {
            tc::Log::error("Heatmap rejected invalid style");
            return false;
        }
        if (style.colormap != state_->style.colormap || style.colormap_reversed != state_->style.colormap_reversed)
            state_->gpu.palette_dirty = true;
        state_->style = style;
        bump(state_->revision);
        return true;
    }
    PlotProjection2D PlotHeatmapItem2D::projection() const {
        return state_->projection;
    }
    PlotRange2D PlotHeatmapItem2D::bounds() const {
        return state_->bounds;
    }
    tc_plot_heatmap_style2d PlotHeatmapItem2D::style() const {
        return state_->style;
    }
    std::span<const double> PlotHeatmapItem2D::values() const {
        return state_->values;
    }
    tc_plot_heatmap_snapshot2d PlotHeatmapItem2D::snapshot() const {
        return {state_->projection.handle(),
                state_->rows,
                state_->columns,
                c_bounds(state_->bounds),
                state_->scalar_min(),
                state_->scalar_max(),
                state_->revision};
    }
    std::optional<tc_plot_heatmap_sample2d> PlotHeatmapItem2D::sample(double x, double y) const {
        const auto b = state_->bounds;
        if (!std::isfinite(x) || !std::isfinite(y) || x < b.x_min() || x > b.x_max() || y < b.y_min() || y > b.y_max())
            return std::nullopt;
        const auto column =
            std::min(state_->columns - 1, static_cast<uint32_t>((x - b.x_min()) / b.x_span() * state_->columns));
        const auto row = std::min(state_->rows - 1, static_cast<uint32_t>((y - b.y_min()) / b.y_span() * state_->rows));
        return tc_plot_heatmap_sample2d{row, column, state_->values[size_t(row) * state_->columns + column]};
    }
    std::optional<termin::Bounds2f> PlotHeatmapItem2D::local_bounds() const {
        const auto projection = state_->projection.snapshot();
        if (!projection)
            return std::nullopt;
        const auto& frame = projection->frame;
        const auto lo = frame.data_to_pixel(state_->bounds.x_min(), state_->bounds.y_min());
        const auto hi = frame.data_to_pixel(state_->bounds.x_max(), state_->bounds.y_max());
        const auto& a = frame.plot_area();
        const auto& c = frame.clip_rect();
        const float x0 = std::max({lo.x, a.x(), c.x()}), y0 = std::max({hi.y, a.y(), c.y()});
        const float x1 = std::min({hi.x, a.right(), c.right()}), y1 = std::min({lo.y, a.bottom(), c.bottom()});
        if (x1 <= x0 || y1 <= y0)
            return std::nullopt;
        return termin::Bounds2f{x0, y0, x1, y1};
    }
    bool PlotHeatmapItem2D::paint(termin::visual::GraphicItemPaintContext2D& context) const {
        if (!state_->projection.valid() || (!tc_graphic_item_handle_is_invalid(handle()) &&
                                            handle().scene_id != state_->projection.handle().scene_id)) {
            tc::Log::error("Heatmap cannot paint stale or cross-scene projection");
            return false;
        }
        const auto area = local_bounds();
        if (!area)
            return true;
        if (!context.push_clip_rect({area->x0, area->y0, area->x1 - area->x0, area->y1 - area->y0}))
            return false;
        const bool painted = context.retained_batch(batch_);
        const bool popped = context.pop_clip();
        return painted && popped;
    }
    bool PlotHeatmapItem2D::hit_test(termin::Vec2f point, float) const {
        const auto a = local_bounds();
        if (!a || point.x < a->x0 || point.x > a->x1 || point.y < a->y0 || point.y > a->y1)
            return false;
        const auto p = state_->projection.snapshot();
        if (!p)
            return false;
        const auto data = p->frame.pixel_to_data(point.x, point.y);
        const auto cell = sample(data.x, data.y);
        return cell && !std::isnan(cell->value);
    }
    PlotHeatmapItem2D* resolve_plot_heatmap_item2d(termin::visual::TcVisualScene& scene,
                                                   termin::visual::GraphicItemHandle handle) {
        auto* item = scene.resolve(handle);
        return item && item->body && std::strcmp(tc_graphic_item_type_name(item), kType) == 0
                   ? static_cast<PlotHeatmapItem2D*>(item->body)
                   : nullptr;
    }
    const PlotHeatmapItem2D* resolve_plot_heatmap_item2d(const termin::visual::TcVisualScene& scene,
                                                         termin::visual::GraphicItemHandle handle) {
        const auto* item = scene.resolve(handle);
        return item && item->body && std::strcmp(tc_graphic_item_type_name(item), kType) == 0
                   ? static_cast<const PlotHeatmapItem2D*>(item->body)
                   : nullptr;
    }
} // namespace tcplot

namespace {
    template <typename R, typename F> R logged(const char* operation, R failure, F action) {
        try {
            return action();
        } catch (const std::exception& error) {
            tc::Log::error("Heatmap %s failed: %s", operation, error.what());
        } catch (...) {
            tc::Log::error("Heatmap %s failed with unknown exception", operation);
        }
        return failure;
    }
    tcplot::PlotHeatmapItem2D* checked(termin::visual::TcVisualScene& scene, tc_graphic_item_handle item) {
        auto* result = tcplot::resolve_plot_heatmap_item2d(scene, item);
        if (!result)
            tc::Log::error("Heatmap operation received stale, wrong-type or cross-scene item");
        return result;
    }
    bool grid_input(const double* values, size_t count, uint32_t rows, uint32_t columns) {
        if (!values || !rows || !columns || uint64_t(rows) * columns != count) {
            tc::Log::error("Heatmap grid requires rows*columns values");
            return false;
        }
        return true;
    }
} // namespace

extern "C" {
tc_plot_heatmap_style2d tc_plot_heatmap_item2d_default_style(void) {
    return {TC_PLOT_COLORMAP_VIRIDIS_2D, false, true, 0, 1, TC_PLOT_HEATMAP_NEAREST_2D};
}
tc_graphic_item_handle tc_plot_heatmap_item2d_create(tc_visual_scene_handle owner_scene,
                                                     tc_plot_projection_handle2d projection,
                                                     const double* values,
                                                     size_t count,
                                                     uint32_t rows,
                                                     uint32_t columns,
                                                     tc_plot_range2d bounds,
                                                     tc_plot_heatmap_style2d style) {
    return logged("create", tc_graphic_item_handle_invalid(), [&] {
        termin::visual::TcVisualScene scene{owner_scene};
        tcplot::PlotProjection2D p{projection};
        if (!grid_input(values, count, rows, columns) || !p.matches_scene(scene)) {
            tc::Log::error("Heatmap create requires valid grid and matching projection scene");
            return tc_graphic_item_handle_invalid();
        }
        const auto result = scene.adopt(std::make_unique<tcplot::PlotHeatmapItem2D>(
            p, std::vector<double>(values, values + count), rows, columns, tcplot::cpp_bounds(bounds), style));
        return result.value_or(tc_graphic_item_handle_invalid());
    });
}
bool tc_plot_heatmap_item2d_set_projection(tc_visual_scene_handle owner_scene,
                                           tc_graphic_item_handle item,
                                           tc_plot_projection_handle2d projection) {
    return logged("set_projection", false, [&] {
        termin::visual::TcVisualScene scene{owner_scene};
        auto* h = checked(scene, item);
        return h && h->set_projection(tcplot::PlotProjection2D{projection});
    });
}
bool tc_plot_heatmap_item2d_set_data(tc_visual_scene_handle owner_scene,
                                     tc_graphic_item_handle item,
                                     const double* values,
                                     size_t count,
                                     uint32_t rows,
                                     uint32_t columns,
                                     tc_plot_range2d bounds) {
    return logged("set_data", false, [&] {
        if (!grid_input(values, count, rows, columns))
            return false;
        termin::visual::TcVisualScene scene{owner_scene};
        auto* h = checked(scene, item);
        return h && h->set_data(std::vector<double>(values, values + count), rows, columns, tcplot::cpp_bounds(bounds));
    });
}
bool tc_plot_heatmap_item2d_set_style(tc_visual_scene_handle owner_scene,
                                      tc_graphic_item_handle item,
                                      tc_plot_heatmap_style2d style) {
    return logged("set_style", false, [&] {
        termin::visual::TcVisualScene scene{owner_scene};
        auto* h = checked(scene, item);
        return h && h->set_style(style);
    });
}
bool tc_plot_heatmap_item2d_snapshot(tc_visual_scene_handle owner_scene,
                                     tc_graphic_item_handle item,
                                     tc_plot_heatmap_snapshot2d* out_snapshot,
                                     tc_plot_heatmap_style2d* out_style) {
    return logged("snapshot", false, [&] {
        if (!out_snapshot || !out_style) {
            tc::Log::error("Heatmap snapshot requires output pointers");
            return false;
        }
        termin::visual::TcVisualScene scene{owner_scene};
        auto* h = checked(scene, item);
        if (!h)
            return false;
        *out_snapshot = h->snapshot();
        *out_style = h->style();
        return true;
    });
}
size_t tc_plot_heatmap_item2d_copy_data(tc_visual_scene_handle owner_scene,
                                        tc_graphic_item_handle item,
                                        double* out_values,
                                        size_t capacity) {
    return logged("copy_data", size_t(0), [&] {
        termin::visual::TcVisualScene scene{owner_scene};
        auto* h = checked(scene, item);
        if (!h)
            return size_t(0);
        const auto values = h->values();
        if (!out_values)
            return values.size();
        if (capacity < values.size()) {
            tc::Log::error("Heatmap copy_data buffer is too small");
            return size_t(0);
        }
        std::copy(values.begin(), values.end(), out_values);
        return values.size();
    });
}
bool tc_plot_heatmap_item2d_sample(tc_visual_scene_handle owner_scene,
                                   tc_graphic_item_handle item,
                                   double x,
                                   double y,
                                   tc_plot_heatmap_sample2d* out_sample) {
    return logged("sample", false, [&] {
        if (!out_sample) {
            tc::Log::error("Heatmap sample requires output pointer");
            return false;
        }
        termin::visual::TcVisualScene scene{owner_scene};
        auto* h = checked(scene, item);
        if (!h)
            return false;
        const auto result = h->sample(x, y);
        if (!result)
            return false;
        *out_sample = *result;
        return true;
    });
}
}
