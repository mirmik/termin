#pragma once

#include "tcplot/tc_plot_series_item2d.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum tc_plot_heatmap_interpolation2d {
    TC_PLOT_HEATMAP_NEAREST_2D = 0,
    TC_PLOT_HEATMAP_BILINEAR_2D = 1,
} tc_plot_heatmap_interpolation2d;

typedef struct tc_plot_heatmap_style2d {
    tc_plot_colormap2d colormap;
    bool colormap_reversed;
    bool auto_range;
    double scalar_min;
    double scalar_max;
    tc_plot_heatmap_interpolation2d interpolation;
} tc_plot_heatmap_style2d;

typedef struct tc_plot_heatmap_snapshot2d {
    tc_plot_projection_handle2d projection;
    uint32_t rows;
    uint32_t columns;
    tc_plot_range2d bounds;
    double scalar_min;
    double scalar_max;
    uint64_t revision;
} tc_plot_heatmap_snapshot2d;

typedef struct tc_plot_heatmap_sample2d {
    uint32_t row;
    uint32_t column;
    double value;
} tc_plot_heatmap_sample2d;

// Bounds describe the OUTER cell edges. Values are row-major: row zero is
// adjacent to y_min, column zero to x_min. NaN cells are transparent; infinities
// are rejected. Sampling includes the maximum outer edges in the last cell.
// Bilinear rendering interpolates scalars between cell centers and clamps at
// the outer edges. Missing neighbors are excluded from the scalar average;
// their missing weight reduces opacity. sample() always returns the raw cell.
TCPLOT_API tc_plot_heatmap_style2d tc_plot_heatmap_item2d_default_style(void);
TCPLOT_API tc_graphic_item_handle tc_plot_heatmap_item2d_create(tc_visual_scene_handle owner_scene,
                                                                tc_plot_projection_handle2d projection,
                                                                const double* values,
                                                                size_t count,
                                                                uint32_t rows,
                                                                uint32_t columns,
                                                                tc_plot_range2d bounds,
                                                                tc_plot_heatmap_style2d style);
TCPLOT_API bool tc_plot_heatmap_item2d_set_projection(tc_visual_scene_handle owner_scene,
                                                      tc_graphic_item_handle item,
                                                      tc_plot_projection_handle2d projection);
TCPLOT_API bool tc_plot_heatmap_item2d_set_data(tc_visual_scene_handle owner_scene,
                                                tc_graphic_item_handle item,
                                                const double* values,
                                                size_t count,
                                                uint32_t rows,
                                                uint32_t columns,
                                                tc_plot_range2d bounds);
TCPLOT_API bool tc_plot_heatmap_item2d_set_style(tc_visual_scene_handle owner_scene,
                                                 tc_graphic_item_handle item,
                                                 tc_plot_heatmap_style2d style);
TCPLOT_API bool tc_plot_heatmap_item2d_snapshot(tc_visual_scene_handle owner_scene,
                                                tc_graphic_item_handle item,
                                                tc_plot_heatmap_snapshot2d* out_snapshot,
                                                tc_plot_heatmap_style2d* out_style);
TCPLOT_API size_t tc_plot_heatmap_item2d_copy_data(tc_visual_scene_handle owner_scene,
                                                   tc_graphic_item_handle item,
                                                   double* out_values,
                                                   size_t capacity);
TCPLOT_API bool tc_plot_heatmap_item2d_sample(tc_visual_scene_handle owner_scene,
                                              tc_graphic_item_handle item,
                                              double data_x,
                                              double data_y,
                                              tc_plot_heatmap_sample2d* out_sample);

#ifdef __cplusplus
}
#endif
