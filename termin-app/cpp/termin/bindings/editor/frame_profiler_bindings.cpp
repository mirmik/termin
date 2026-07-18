#include <nanobind/nanobind.h>
#include <nanobind/stl/shared_ptr.h>

#include "termin/editor/frame_profiler_controller.hpp"
#include <termin/engine/engine_core.hpp>

namespace nb = nanobind;

namespace termin {

void bind_frame_profiler(nb::module_& m) {
    // Register the native model types before this module exposes shared_ptrs
    // to them.  This stays in the binding boundary; the controller itself has
    // no Python dependency.
    nb::module_::import_("termin.gui_native");
    nb::class_<FrameProfilerController>(m, "FrameProfilerController")
        .def(nb::init<EngineCore&, int, double>(),
             nb::arg("engine"), nb::arg("capacity") = 3600,
             nb::arg("hitch_ratio") = 1.25,
             nb::keep_alive<1, 2>())
        .def_prop_ro("command_model", &FrameProfilerController::command_model)
        .def_prop_ro("timeline_model", &FrameProfilerController::timeline_model)
        .def_prop_ro("section_model", &FrameProfilerController::section_model)
        .def_prop_ro("summary_model", &FrameProfilerController::summary_model)
        .def_prop_ro("detail_model", &FrameProfilerController::detail_model)
        .def_prop_ro("status_model", &FrameProfilerController::status_model)
        .def_prop_ro("capacity", &FrameProfilerController::capacity)
        .def_prop_ro("hitch_ratio", &FrameProfilerController::hitch_ratio)
        .def_prop_ro("capturing", &FrameProfilerController::capturing)
        .def_prop_ro("profiling", &FrameProfilerController::profiling)
        .def_prop_ro("follow_latest", &FrameProfilerController::follow_latest)
        .def_prop_ro("selected_frame_number", &FrameProfilerController::selected_frame_number)
        .def("start_capture", &FrameProfilerController::start_capture)
        .def("pause", &FrameProfilerController::pause)
        .def("set_profiling", &FrameProfilerController::set_profiling,
             nb::arg("enabled"))
        .def("clear", &FrameProfilerController::clear)
        .def("close", &FrameProfilerController::close)
        .def("update", &FrameProfilerController::update)
        .def("activate", &FrameProfilerController::activate, nb::arg("command"))
        .def("select_frame", &FrameProfilerController::select_frame,
             nb::arg("frame_number"))
        .def("show_section_details", &FrameProfilerController::show_section_details,
             nb::arg("node"));
}

} // namespace termin
