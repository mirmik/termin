// profiler_bindings.cpp - Python bindings for tc_profiler
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "../../core_c/include/tc_profiler.h"

namespace py = pybind11;

namespace termin {

// Python-friendly section timing data
struct PySectionTiming {
    std::string name;
    double cpu_ms;
    int call_count;
    int parent_index;
    int first_child;
    int next_sibling;
};

// Python-friendly frame profile
struct PyFrameProfile {
    int frame_number;
    double total_ms;
    std::vector<PySectionTiming> sections;
};

// Convert C frame to Python-friendly struct
static PyFrameProfile convert_frame(const tc_frame_profile* frame) {
    PyFrameProfile result;
    result.frame_number = frame->frame_number;
    result.total_ms = frame->total_ms;

    for (int i = 0; i < frame->section_count; i++) {
        const tc_section_timing* s = &frame->sections[i];
        PySectionTiming ps;
        ps.name = s->name;
        ps.cpu_ms = s->cpu_ms;
        ps.call_count = s->call_count;
        ps.parent_index = s->parent_index;
        ps.first_child = s->first_child;
        ps.next_sibling = s->next_sibling;
        result.sections.push_back(ps);
    }

    return result;
}

// Wrapper class for tc_profiler
class TcProfiler {
public:
    static TcProfiler& instance() {
        static TcProfiler inst;
        return inst;
    }

    bool enabled() const { return tc_profiler_enabled(); }
    void set_enabled(bool v) { tc_profiler_set_enabled(v); }

    bool profile_components() const { return tc_profiler_profile_components(); }
    void set_profile_components(bool v) { tc_profiler_set_profile_components(v); }

    void begin_frame() { tc_profiler_begin_frame(); }
    void end_frame() { tc_profiler_end_frame(); }

    void begin_section(const std::string& name) { tc_profiler_begin_section(name.c_str()); }
    void end_section() { tc_profiler_end_section(); }

    int frame_count() const { return tc_profiler_frame_count(); }

    int history_count() const { return tc_profiler_history_count(); }

    py::object history_at(int index) {
        tc_frame_profile* frame = tc_profiler_history_at(index);
        if (!frame) return py::none();
        return py::cast(convert_frame(frame));
    }

    std::vector<PyFrameProfile> history() {
        std::vector<PyFrameProfile> result;
        int count = tc_profiler_history_count();
        for (int i = 0; i < count; i++) {
            tc_frame_profile* frame = tc_profiler_history_at(i);
            if (frame) {
                result.push_back(convert_frame(frame));
            }
        }
        return result;
    }

    void clear_history() { tc_profiler_clear_history(); }

    py::object current_frame() {
        tc_frame_profile* frame = tc_profiler_current_frame();
        if (!frame) return py::none();
        return py::cast(convert_frame(frame));
    }

private:
    TcProfiler() = default;
};

void bind_profiler(py::module_& m) {
    // Section timing struct
    py::class_<PySectionTiming>(m, "SectionTiming")
        .def_readonly("name", &PySectionTiming::name)
        .def_readonly("cpu_ms", &PySectionTiming::cpu_ms)
        .def_readonly("call_count", &PySectionTiming::call_count)
        .def_readonly("parent_index", &PySectionTiming::parent_index)
        .def_readonly("first_child", &PySectionTiming::first_child)
        .def_readonly("next_sibling", &PySectionTiming::next_sibling)
        ;

    // Frame profile struct
    py::class_<PyFrameProfile>(m, "FrameProfile")
        .def_readonly("frame_number", &PyFrameProfile::frame_number)
        .def_readonly("total_ms", &PyFrameProfile::total_ms)
        .def_readonly("sections", &PyFrameProfile::sections)
        ;

    // TcProfiler singleton
    py::class_<TcProfiler>(m, "TcProfiler")
        .def_static("instance", &TcProfiler::instance, py::return_value_policy::reference)
        .def_property("enabled", &TcProfiler::enabled, &TcProfiler::set_enabled)
        .def_property("profile_components", &TcProfiler::profile_components, &TcProfiler::set_profile_components)
        .def("begin_frame", &TcProfiler::begin_frame)
        .def("end_frame", &TcProfiler::end_frame)
        .def("begin_section", &TcProfiler::begin_section, py::arg("name"))
        .def("end_section", &TcProfiler::end_section)
        .def_property_readonly("frame_count", &TcProfiler::frame_count)
        .def_property_readonly("history_count", &TcProfiler::history_count)
        .def("history_at", &TcProfiler::history_at, py::arg("index"))
        .def_property_readonly("history", &TcProfiler::history)
        .def("clear_history", &TcProfiler::clear_history)
        .def_property_readonly("current_frame", &TcProfiler::current_frame)
        ;
}

} // namespace termin
