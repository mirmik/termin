#include <nanobind/nanobind.h>
#include <nanobind/stl/function.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "termin/editor/frame_graph_debugger_view.hpp"
#include <termin/gui_native/status_bar.hpp>
#include <termin/render/frame_graph_debugger.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>

namespace nb = nanobind;

namespace termin {

void bind_frame_graph_debugger(nb::module_& m) {
    nb::module_::import_("termin.gui_native");
    nb::module_::import_("tgfx");
    nb::module_ framework = nb::module_::import_("termin.render_framework._render_framework_native");
    nb::module_ engine = nb::module_::import_("termin.engine._engine_native");
    m.attr("HDRStats") = framework.attr("HDRStats");
    m.attr("TextureInfo") = framework.attr("TextureInfo");
    m.attr("FrameGraphCapture") = framework.attr("FrameGraphCapture");
    m.attr("FrameGraphPresenter") = framework.attr("FrameGraphPresenter");
    m.attr("FrameGraphDebugger") = engine.attr("render").attr("FrameGraphDebugger");

    nb::class_<FrameGraphDebuggerView>(m, "FrameGraphDebuggerView")
        .def(nb::init<gui_native::TcDocument, FrameGraphDebugger&, std::function<void()>>(),
             nb::arg("document"), nb::arg("debugger"),
             nb::arg("request_render") = std::function<void()>{},
             nb::keep_alive<1, 3>())
        .def("activate", &FrameGraphDebuggerView::activate)
        .def("deactivate", &FrameGraphDebuggerView::deactivate)
        .def("update", &FrameGraphDebuggerView::update)
        .def("show_resource", &FrameGraphDebuggerView::show_resource,
             nb::arg("resource"))
        .def("render_previews", &FrameGraphDebuggerView::render_previews,
             nb::arg("context"))
        .def("refresh_depth", &FrameGraphDebuggerView::refresh_depth,
             nb::arg("device"))
        .def("close", &FrameGraphDebuggerView::close)
        .def_prop_ro("active", &FrameGraphDebuggerView::active)
        .def_prop_ro("closed", &FrameGraphDebuggerView::closed)
        .def_prop_ro("document", &FrameGraphDebuggerView::document)
        .def_prop_ro("pass_indices", &FrameGraphDebuggerView::pass_indices)
        .def_prop_ro("state_status_text", [](const FrameGraphDebuggerView& self) {
            const auto* status = self.state_status();
            return status ? status->text() : std::string{};
        })
        .def_prop_ro("root_stable_id", [](const FrameGraphDebuggerView& self) {
            const auto* root = self.root_widget();
            return root ? std::string(root->stable_id()) : std::string{};
        });
}

} // namespace termin
