#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {

void bind_frame_graph_debugger(nb::module_& m) {
    nb::module_ framework = nb::module_::import_("termin.render_framework._render_framework_native");
    nb::module_ engine = nb::module_::import_("termin.engine._engine_native");
    m.attr("HDRStats") = framework.attr("HDRStats");
    m.attr("TextureInfo") = framework.attr("TextureInfo");
    m.attr("FrameGraphCapture") = framework.attr("FrameGraphCapture");
    m.attr("FrameGraphPresenter") = framework.attr("FrameGraphPresenter");
    m.attr("FrameGraphDebugger") = engine.attr("render").attr("FrameGraphDebugger");
}

} // namespace termin
