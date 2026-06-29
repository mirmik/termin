// SWIG interface for the plot-only Termin C# runtime profile.
%module(directors="1") termin

%{
#include "tgfx2/enums.hpp"
#include "tcplot/styles.hpp"
#include "tcplot/orbit_camera.hpp"
#include "tcplot/gpu_host.hpp"
#include "tcplot/plot_view2d.hpp"
#include "tcplot/plot_view2d_multi.hpp"
#include "tcplot/plot_view3d.hpp"
%}

%include "std_string.i"

// Marshal C# strings to UTF-8. Plot labels/titles are rendered by tgfx2's
// UTF-8 text path, so Windows ANSI marshaling corrupts Cyrillic.
%typemap(imtype,
         inattributes="[global::System.Runtime.InteropServices.MarshalAs(global::System.Runtime.InteropServices.UnmanagedType.LPUTF8Str)]")
    const char *, char *
    "string"
%typemap(imtype,
         inattributes="[global::System.Runtime.InteropServices.MarshalAs(global::System.Runtime.InteropServices.UnmanagedType.LPUTF8Str)]")
    std::string, std::string const &, std::string &
    "string"

%include "arrays_csharp.i"

%apply double INPUT[] {
    const double* x, const double* y, const double* z, const double* scalar,
    const double* X, const double* Y, const double* Z
}

%typemap(cstype, out = "out double") double* OUTPUT "out double"
%typemap(csin)   double* OUTPUT "out $csinput"
%typemap(imtype) double* OUTPUT "out double"
%typemap(ctype)  double* OUTPUT "double*"
%typemap(in)     double* OUTPUT "$1 = $input;"
%apply double* OUTPUT {
    double* out_x, double* out_y, double* out_z,
    double* out_screen_dist_px
}

namespace tgfx {
enum class BackendType {
    OpenGL,
    Vulkan,
    Metal,
    D3D11,
    Null
};
}

namespace tcplot {

struct Color4 {
    float r, g, b, a;

    Color4();
    Color4(float r, float g, float b, float a = 1.0f);
};

enum class SurfaceColorMap {
    Jet,
    Viridis,
    Plasma,
    Grayscale,
    CoolWarm,
    Solid
};

enum class LineStyle {
    Solid,
    Dash,
    Dot
};

class OrbitCamera {
public:
    float distance;
    float azimuth;
    float elevation;
    float fov_y;
    float near;
    float far;
    float min_distance;
    float max_distance;
    float min_elevation;
    float max_elevation;

    OrbitCamera();

    void orbit(float d_azimuth, float d_elevation);
    void zoom(float factor);
    void pan(float dx, float dy);
};

class GpuHost {
public:
    GpuHost(const std::string& ttf_path);
    GpuHost(const std::string& ttf_path, tgfx::BackendType backend);
    ~GpuHost();
};

class PlotView3D {
public:
    PlotView3D(GpuHost& host);
    ~PlotView3D();

    void plot(const double* x, const double* y, const double* z,
              size_t n,
              float cr, float cg, float cb, float ca,
              double thickness = 1.5,
              const char* label = "");

    void scatter(const double* x, const double* y, const double* z,
                 size_t n,
                 float cr, float cg, float cb, float ca,
                 double size = 4.0,
                 const char* label = "");

    void surface(const double* X, const double* Y, const double* Z,
                 unsigned int rows, unsigned int cols,
                 float cr, float cg, float cb, float ca,
                 bool wireframe = false,
                 const char* label = "");
    void surface_colormap(const double* X, const double* Y, const double* Z,
                          unsigned int rows, unsigned int cols,
                          SurfaceColorMap colormap,
                          float cr, float cg, float cb, float ca,
                          bool wireframe = false,
                          const char* label = "",
                          bool colormap_reversed = false);

    void clear();
    void set_title(const char* title);
    void set_x_label(const char* label);
    void set_y_label(const char* label);
    void set_z_label(const char* label);
    void set_axis_labels(const char* x_label,
                         const char* y_label,
                         const char* z_label);
    bool set_surface_colormap(int surface_idx, SurfaceColorMap colormap);
    bool set_surface_colormap_reversed(int surface_idx, bool reversed);
    bool set_surface_color(int surface_idx, float r, float g, float b, float a);
    bool set_surface_grid(int surface_idx, bool visible,
                          unsigned int row_step, unsigned int col_step,
                          float r, float g, float b, float a,
                          float width_px = 1.5f);
    void toggle_wireframe();
    void toggle_marker_mode();
    void set_z_scale(float s);
    float get_z_scale() const;
    void set_axis_scale(float x, float y, float z);
    float get_x_scale() const;
    float get_y_scale() const;
    void set_surface_shading(bool enabled, float strength = 0.35f);
    void set_surface_light_dir(float x, float y, float z);

    OrbitCamera& camera();
    void fit_camera();

    bool on_mouse_down(float x, float y, int button);
    void on_mouse_move(float x, float y);
    void on_mouse_up(float x, float y, int button);
    bool on_mouse_wheel(float x, float y, float dy);

    bool pick(float mx, float my,
              double* out_x, double* out_y, double* out_z,
              double* out_screen_dist_px);

    void set_msaa_samples(int samples);
    int  msaa_samples() const;

    unsigned int render_to_texture_id(int width, int height);
    void release_gpu();
};

class PlotView2D {
public:
    PlotView2D(GpuHost& host);
    ~PlotView2D();

    void plot(const double* x, const double* y, size_t n,
              float cr, float cg, float cb, float ca,
              double thickness = 1.5,
              const char* label = "");

    void plot_colormap(const double* x, const double* y, const double* scalar,
                       size_t n,
                       SurfaceColorMap colormap = SurfaceColorMap::Jet,
                       double scalar_min = 0.0,
                       double scalar_max = 1.0,
                       double thickness = 1.5,
                       const char* label = "",
                       bool colormap_reversed = false);

    void scatter(const double* x, const double* y, size_t n,
                 float cr, float cg, float cb, float ca,
                 double size = 4.0,
                 const char* label = "");

    void clear();
    void fit();
    void set_view(double x_min, double x_max, double y_min, double y_max);

    void set_title(const char* title);
    void set_x_label(const char* label);
    void set_y_label(const char* label);
    bool set_line_color(int idx, float r, float g, float b, float a);
    bool set_scatter_color(int idx, float r, float g, float b, float a);
    bool set_line_style(int idx, LineStyle style,
                        float dash_px = 8.0f,
                        float gap_px = 5.0f);
    bool set_line_colormap_reversed(int idx, bool reversed);

    bool on_mouse_down(float x, float y, int button);
    void on_mouse_move(float x, float y);
    void on_mouse_up(float x, float y, int button);
    bool on_mouse_wheel(float x, float y, float dy);

    void set_msaa_samples(int samples);
    int  msaa_samples() const;

    unsigned int render_to_texture_id(int width, int height);
    void release_gpu();
};

%apply double INPUT[] { const double* x, const double* y }

%extend PlotView3D {
    unsigned int render_to_texture_handle_id(int width, int height) {
        return $self->render_to_texture(width, height).id;
    }
}

%extend PlotView2D {
    unsigned int render_to_texture_handle_id(int width, int height) {
        return $self->render_to_texture(width, height).id;
    }
}

%extend PlotView2DMulti {
    unsigned int render_to_texture_handle_id(int width, int height) {
        return $self->render_to_texture(width, height).id;
    }
}

class PlotView2DMulti {
public:
    PlotView2DMulti(GpuHost& host, int panel_count);
    ~PlotView2DMulti();

    void set_panel_count(int n);
    int panel_count() const;

    int add_line(int panel_idx,
                 const double* x, const double* y, size_t n,
                 float cr, float cg, float cb, float ca,
                 double thickness = 1.5,
                 const char* label = "");

    int add_line_colormap(int panel_idx,
                          const double* x, const double* y,
                          const double* scalar, size_t n,
                          SurfaceColorMap colormap = SurfaceColorMap::Jet,
                          double scalar_min = 0.0,
                          double scalar_max = 1.0,
                          double thickness = 1.5,
                          const char* label = "",
                          bool colormap_reversed = false);

    int add_scatter(int panel_idx,
                    const double* x, const double* y, size_t n,
                    float cr, float cg, float cb, float ca,
                    double size = 4.0,
                    const char* label = "");

    void append_to_line(int panel_idx, int series_idx,
                        const double* x, const double* y, size_t n);

    void clear();

    void set_panel_title(int panel_idx, const char* title);
    void set_panel_y_label(int panel_idx, const char* label);
    void set_x_label(const char* label);

    void set_msaa_samples(int samples);

    void set_autoscroll(bool on, double window_size);
    void set_shared_view_x(double x_min, double x_max);
    void set_panel_view_y(int panel_idx, double y_min, double y_max);

    void set_panel_height(float h);
    void set_scroll_offset(float offset);
    float total_virtual_height() const;

    void set_bg_color       (float r, float g, float b, float a);
    void set_plot_bg_color  (float r, float g, float b, float a);
    void set_grid_color     (float r, float g, float b, float a);
    void set_axis_color     (float r, float g, float b, float a);
    void set_label_color    (float r, float g, float b, float a);
    void set_title_color    (float r, float g, float b, float a);
    void clear_title_color  ();
    void set_line_color     (int panel_idx, int series_idx,
                             float r, float g, float b, float a);
    void set_scatter_color  (int panel_idx, int series_idx,
                             float r, float g, float b, float a);
    void set_line_style     (int panel_idx, int series_idx,
                             LineStyle style,
                             float dash_px = 8.0f,
                             float gap_px = 5.0f);
    void set_line_colormap_reversed(int panel_idx, int series_idx,
                                    bool reversed);
    void set_font_size      (float label_px, float title_px);
    void set_panel_margins  (int left, int right, int top, int bottom);
    void set_title_pad      (float pad);

    unsigned int render_to_texture_id(int width, int height);
    void release_gpu();

    bool on_mouse_down(float x, float y, int button);
    void on_mouse_move(float x, float y);
    void on_mouse_up(float x, float y, int button);
    bool on_mouse_wheel(float x, float y, float dy);
    bool on_mouse_wheel_x(float x, float y, float dy);
};

} // namespace tcplot
