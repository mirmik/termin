#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "termin/editor/frame_graph_debugger_core.hpp"
#include "termin/render/frame_pass.hpp"

namespace nb = nanobind;

namespace termin {

void bind_frame_graph_debugger(nb::module_& m) {
    // HDRStats
    nb::class_<HDRStats>(m, "HDRStats")
        .def(nb::init<>())
        .def_ro("min_r", &HDRStats::min_r)
        .def_ro("max_r", &HDRStats::max_r)
        .def_ro("avg_r", &HDRStats::avg_r)
        .def_ro("min_g", &HDRStats::min_g)
        .def_ro("max_g", &HDRStats::max_g)
        .def_ro("avg_g", &HDRStats::avg_g)
        .def_ro("min_b", &HDRStats::min_b)
        .def_ro("max_b", &HDRStats::max_b)
        .def_ro("avg_b", &HDRStats::avg_b)
        .def_ro("hdr_pixel_count", &HDRStats::hdr_pixel_count)
        .def_ro("total_pixels", &HDRStats::total_pixels)
        .def_ro("hdr_percent", &HDRStats::hdr_percent)
        .def_ro("max_value", &HDRStats::max_value);

    // FBOInfo
    nb::class_<FBOInfo>(m, "FBOInfo")
        .def(nb::init<>())
        .def_ro("type_name", &FBOInfo::type_name)
        .def_ro("width", &FBOInfo::width)
        .def_ro("height", &FBOInfo::height)
        .def_ro("samples", &FBOInfo::samples)
        .def_ro("is_msaa", &FBOInfo::is_msaa)
        .def_ro("format", &FBOInfo::format)
        .def_ro("fbo_id", &FBOInfo::fbo_id)
        .def_ro("gl_format", &FBOInfo::gl_format)
        .def_ro("gl_width", &FBOInfo::gl_width)
        .def_ro("gl_height", &FBOInfo::gl_height)
        .def_ro("gl_samples", &FBOInfo::gl_samples)
        .def_ro("filter", &FBOInfo::filter)
        .def_ro("gl_filter", &FBOInfo::gl_filter);

    // FrameGraphCapture
    nb::class_<FrameGraphCapture>(m, "FrameGraphCapture")
        .def(nb::init<>())
        .def("set_target", [](FrameGraphCapture& self, CxxFramePass* pass) {
            self.set_target(pass);
        }, nb::arg("pass"), nb::rv_policy::reference)
        .def("clear_target", &FrameGraphCapture::clear_target)
        .def("capture", &FrameGraphCapture::capture,
             nb::arg("caller"), nb::arg("src"), nb::arg("graphics"))
        .def("capture_direct", &FrameGraphCapture::capture_direct,
             nb::arg("src"), nb::arg("graphics"))
        .def("has_capture", &FrameGraphCapture::has_capture)
        .def("reset_capture", &FrameGraphCapture::reset_capture)
        .def_prop_ro("capture_fbo", &FrameGraphCapture::capture_fbo,
                     nb::rv_policy::reference);

    // FrameGraphPresenter
    nb::class_<FrameGraphPresenter>(m, "FrameGraphPresenter")
        .def(nb::init<>())
        .def("render", &FrameGraphPresenter::render,
             nb::arg("graphics"), nb::arg("capture_fbo"),
             nb::arg("dst_w"), nb::arg("dst_h"),
             nb::arg("channel_mode"), nb::arg("highlight_hdr"))
        .def("compute_hdr_stats", &FrameGraphPresenter::compute_hdr_stats,
             nb::arg("graphics"), nb::arg("fbo"))
        .def("read_depth_normalized", [](FrameGraphPresenter& self,
                                          GraphicsBackend* graphics,
                                          FramebufferHandle* fbo) -> nb::bytes {
            int w = 0, h = 0;
            auto data = self.read_depth_normalized(graphics, fbo, &w, &h);
            if (data.empty()) {
                return nb::bytes(nullptr, 0);
            }
            return nb::bytes(reinterpret_cast<const char*>(data.data()), data.size());
        }, nb::arg("graphics"), nb::arg("fbo"))
        .def("read_depth_normalized_with_size", [](FrameGraphPresenter& self,
                                                    GraphicsBackend* graphics,
                                                    FramebufferHandle* fbo) -> nb::tuple {
            int w = 0, h = 0;
            auto data = self.read_depth_normalized(graphics, fbo, &w, &h);
            if (data.empty()) {
                return nb::make_tuple(nb::bytes(nullptr, 0), 0, 0);
            }
            return nb::make_tuple(
                nb::bytes(reinterpret_cast<const char*>(data.data()), data.size()),
                w, h
            );
        }, nb::arg("graphics"), nb::arg("fbo"))
        .def_static("get_fbo_info", &FrameGraphPresenter::get_fbo_info,
                     nb::arg("fbo"));

    // FrameGraphDebuggerCore
    nb::class_<FrameGraphDebuggerCore>(m, "FrameGraphDebuggerCore")
        .def(nb::init<>())
        .def_prop_ro("capture_fbo", &FrameGraphDebuggerCore::capture_fbo,
                     nb::rv_policy::reference)
        .def_prop_ro("capture", [](FrameGraphDebuggerCore& self) -> FrameGraphCapture& {
            return self.capture;
        }, nb::rv_policy::reference_internal)
        .def_prop_ro("presenter", [](FrameGraphDebuggerCore& self) -> FrameGraphPresenter& {
            return self.presenter;
        }, nb::rv_policy::reference_internal);
}

} // namespace termin
