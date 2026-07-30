%extend GpuHost {
    bool measure_plot_text_2d(
        const char* text,
        float font_size_logical_px,
        float pixel_scale,
        float* out_width,
        float* out_height,
        float* out_ascent,
        float* out_descent,
        float* out_line_height) {
        if (!out_width || !out_height || !out_ascent || !out_descent ||
            !out_line_height) {
            return false;
        }
        const auto measured = tcplot::measure_plot_text2d(
            $self->font(),
            text ? std::string_view{text} : std::string_view{},
            font_size_logical_px,
            pixel_scale);
        if (!measured) {
            return false;
        }
        *out_width = measured->width;
        *out_height = measured->height;
        *out_ascent = measured->ascent;
        *out_descent = measured->descent;
        *out_line_height = measured->line_height;
        return true;
    }
}
