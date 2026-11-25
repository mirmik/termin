// SWIG interface for the plot-only Termin C# runtime profile.
%module(directors="1") termin

%{
#include "tgfx2/enums.hpp"
#include "termin/geom/rect2.hpp"
#include "termin/geom/vec2.hpp"
#include "tcplot/gpu_host.hpp"
#include "tcplot/plot_layout2d.hpp"
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

%typemap(cstype, out = "out float") float* OUTPUT "out float"
%typemap(csin)   float* OUTPUT "out $csinput"
%typemap(imtype) float* OUTPUT "out float"
%typemap(ctype)  float* OUTPUT "float*"
%typemap(in)     float* OUTPUT "$1 = $input;"
%apply float* OUTPUT {
    float* out_width, float* out_height, float* out_ascent,
    float* out_descent, float* out_line_height
}

namespace tgfx {
enum class BackendType {
    OpenGL,
    Vulkan,
    Metal,
    D3D11,
    WebGPU,
    Null
};
}

namespace termin {
enum class CameraProjection {
    Perspective,
    Orthographic
};

struct Vec2 {
    double x, y;

    Vec2();
    Vec2(double x, double y);
};

struct Rect2 {
    double x, y, width, height;

    Rect2();
    Rect2(double x, double y, double width, double height);
};
}

namespace tcplot {

class GpuHost {
public:
    GpuHost(const std::string& ttf_path);
    GpuHost(const std::string& ttf_path, tgfx::BackendType backend);
    ~GpuHost();
};

%include "termin_plot_retained.i"

} // namespace tcplot

%include "termin_document_host.i"
