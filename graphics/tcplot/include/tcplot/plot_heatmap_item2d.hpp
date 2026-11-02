#pragma once

#include "tcplot/plot_projection2d.hpp"
#include "tcplot/tc_plot_heatmap_item2d.h"
#include <memory>
#include <span>
#include <termin_visual_scene/native_graphic_item2d.hpp>
#include <vector>

namespace tgfx {
    class RetainedDrawBatch2D;
}

namespace tcplot {
    class TCPLOT_API PlotHeatmapItem2D final : public termin::visual::NativeGraphicItem2D {
    public:
        struct State;
        PlotHeatmapItem2D(PlotProjection2D projection,
                          std::vector<double> values,
                          uint32_t rows,
                          uint32_t columns,
                          PlotRange2D bounds,
                          tc_plot_heatmap_style2d style);
        ~PlotHeatmapItem2D() override;
        bool set_projection(PlotProjection2D projection);
        bool set_data(std::vector<double> values, uint32_t rows, uint32_t columns, PlotRange2D bounds);
        bool set_style(tc_plot_heatmap_style2d style);
        PlotProjection2D projection() const;
        PlotRange2D bounds() const;
        tc_plot_heatmap_style2d style() const;
        tc_plot_heatmap_snapshot2d snapshot() const;
        std::span<const double> values() const;
        std::optional<tc_plot_heatmap_sample2d> sample(double data_x, double data_y) const;
        std::optional<termin::Bounds2f> local_bounds() const override;
        bool paint(termin::visual::GraphicItemPaintContext2D& context) const override;
        bool hit_test(termin::Vec2f point, float tolerance) const override;

    private:
        std::shared_ptr<State> state_;
        std::shared_ptr<tgfx::RetainedDrawBatch2D> batch_;
    };

    TCPLOT_API PlotHeatmapItem2D* resolve_plot_heatmap_item2d(termin::visual::TcVisualScene& scene,
                                                              termin::visual::GraphicItemHandle handle);
    TCPLOT_API const PlotHeatmapItem2D* resolve_plot_heatmap_item2d(const termin::visual::TcVisualScene& scene,
                                                                    termin::visual::GraphicItemHandle handle);
} // namespace tcplot
