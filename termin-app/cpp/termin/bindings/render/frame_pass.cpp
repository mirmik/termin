#include "common.hpp"
#include <nanobind/stl/set.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/vector.h>

extern "C" {
#include "render/tc_pass.h"
}

#include "termin/render/frame_pass.hpp"
#include "termin/render/render.hpp"
#include "termin/render/id_pass.hpp"
#include "termin/render/collider_gizmo_pass.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/lighting/shadow.hpp"
#include <termin/lighting/shadow_settings.hpp>
#include <termin/render/frame_graph_debugger_core.hpp>
#include <termin/lighting/light.hpp>
#include <termin/tc_scene.hpp>
#include <tcbase/tc_log.hpp>

#include <cstdint>
#include <memory>

namespace termin {

static void py_cxx_pass_ref_retain(tc_pass* p) {
    if (p && p->body) {
        Py_INCREF(reinterpret_cast<PyObject*>(p->body));
    }
}

static void py_cxx_pass_ref_release(tc_pass* p) {
    if (p && p->body) {
        Py_DECREF(reinterpret_cast<PyObject*>(p->body));
    }
}

static const tc_pass_ref_vtable g_py_cxx_pass_ref_vtable = {
    py_cxx_pass_ref_retain,
    py_cxx_pass_ref_release,
    nullptr,
};

template<typename T>
void init_pass_from_python(T* self, const char* type_name) {
    self->link_to_type_registry(type_name);
    nb::object wrapper = nb::cast(self, nb::rv_policy::reference);
    self->set_python_ref(wrapper.ptr(), &g_py_cxx_pass_ref_vtable);
    Py_INCREF(wrapper.ptr());
}

void bind_frame_pass(nb::module_& m) {
    nb::class_<IdPass, CxxFramePass>(m, "IdPass")
        .def("__init__", [](IdPass* self, const std::string& input_res, const std::string& output_res, const std::string& pass_name) {
            new (self) IdPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "IdPass");
        }, nb::arg("input_res") = "empty", nb::arg("output_res") = "id", nb::arg("pass_name") = "IdPass")
        .def_rw("input_res", &IdPass::input_res)
        .def_rw("output_res", &IdPass::output_res)
        .def_rw("camera_name", &IdPass::camera_name)
        .def("get_internal_symbols", &IdPass::get_internal_symbols)
        .def_prop_ro("reads", &IdPass::compute_reads)
        .def_prop_ro("writes", &IdPass::compute_writes)
        .def("destroy", &IdPass::destroy);

    {
        nb::dict visibility;
        nb::dict camera_cond;
        camera_cond["_outside_viewport"] = true;
        visibility["camera_name"] = camera_cond;
        m.attr("IdPass").attr("node_param_visibility") = visibility;
        m.attr("IdPass").attr("category") = "Render";
        m.attr("IdPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        m.attr("IdPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("IdPass").attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("input_res", "output_res"));
    }

    nb::class_<ColliderGizmoPass, CxxFramePass>(m, "ColliderGizmoPass")
        .def("__init__", [](ColliderGizmoPass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name,
                            bool depth_test) {
            new (self) ColliderGizmoPass(input_res, output_res, pass_name, depth_test);
            init_pass_from_python(self, "ColliderGizmoPass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "ColliderGizmo",
             nb::arg("depth_test") = false)
        .def_rw("input_res", &ColliderGizmoPass::input_res)
        .def_rw("output_res", &ColliderGizmoPass::output_res)
        .def_rw("depth_test", &ColliderGizmoPass::depth_test)
        .def("compute_reads", &ColliderGizmoPass::compute_reads)
        .def("compute_writes", &ColliderGizmoPass::compute_writes)
        .def("get_inplace_aliases", &ColliderGizmoPass::get_inplace_aliases)
        .def_prop_ro("reads", &ColliderGizmoPass::compute_reads)
        .def_prop_ro("writes", &ColliderGizmoPass::compute_writes)
        .def("destroy", &ColliderGizmoPass::destroy)
        .def("__repr__", [](const ColliderGizmoPass& p) {
            return "<ColliderGizmoPass '" + p.get_pass_name() + "'>";
        });

    {
        m.attr("ColliderGizmoPass").attr("category") = "Debug";
        m.attr("ColliderGizmoPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("ColliderGizmoPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("ColliderGizmoPass").attr("node_inplace_pairs") = nb::make_tuple(
            nb::make_tuple("input_res", "output_res")
        );
    }

}

} // namespace termin
