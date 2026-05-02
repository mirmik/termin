#include "common.hpp"
#include <nanobind/make_iterator.h>
#include <nanobind/stl/set.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/vector.h>

extern "C" {
#include "render/tc_pass.h"
}

#include "termin/render/frame_pass.hpp"
#include "termin/render/render.hpp"
#include "termin/render/color_pass.hpp"
#include "termin/render/id_pass.hpp"
#include "termin/render/collider_gizmo_pass.hpp"
#include "termin/render/debug_triangle_pass.hpp"
#include "termin/render/shadow_pass.hpp"
#include "termin/render/present_pass.hpp"
#include "termin/render/bloom_pass.hpp"
#include "termin/render/grayscale_pass.hpp"
#include "termin/render/skybox_pass.hpp"
#include "termin/render/tonemap_pass.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/lighting/shadow_settings.hpp"
#include <termin/render/frame_graph_debugger_core.hpp>
#include <termin/render/light.hpp>
#include <termin/tc_scene.hpp>
#include <tcbase/tc_log.hpp>

#include <cstdint>
#include <memory>
#include <unordered_map>

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

static Rect4i tuple_to_rect(nb::tuple rect_py) {
    Rect4i rect;
    rect.x = nb::cast<int>(rect_py[0]);
    rect.y = nb::cast<int>(rect_py[1]);
    rect.width = nb::cast<int>(rect_py[2]);
    rect.height = nb::cast<int>(rect_py[3]);
    return rect;
}

static tc_scene_handle object_to_scene_handle(nb::object scene_py) {
    if (!scene_py.is_none() && nb::hasattr(scene_py, "scene_handle")) {
        return nb::cast<tc_scene_handle>(scene_py.attr("scene_handle")());
    }
    return TC_SCENE_HANDLE_INVALID;
}

static Mat44f ndarray_to_mat44f(const nb::ndarray<nb::numpy, float, nb::shape<4, 4>>& src) {
    Mat44f result;
    for (int row = 0; row < 4; ++row) {
        for (int col = 0; col < 4; ++col) {
            result(col, row) = src(row, col);
        }
    }
    return result;
}

void bind_frame_pass(nb::module_& m) {
    nb::class_<ShadowMapArrayEntry>(m, "ShadowMapArrayEntry")
        .def(nb::init<>())
        .def_rw("light_space_matrix", &ShadowMapArrayEntry::light_space_matrix)
        .def_rw("light_index", &ShadowMapArrayEntry::light_index)
        .def_rw("cascade_index", &ShadowMapArrayEntry::cascade_index)
        .def_rw("cascade_split_near", &ShadowMapArrayEntry::cascade_split_near)
        .def_rw("cascade_split_far", &ShadowMapArrayEntry::cascade_split_far);

    nb::class_<ShadowMapArrayResource, FrameGraphResource>(m, "ShadowMapArrayResource")
        .def(nb::init<>())
        .def(nb::init<int>(), nb::arg("resolution"))
        .def("resource_type", &ShadowMapArrayResource::resource_type)
        .def("size", &ShadowMapArrayResource::size)
        .def("empty", &ShadowMapArrayResource::empty)
        .def("clear", &ShadowMapArrayResource::clear)
        .def_rw("resolution", &ShadowMapArrayResource::resolution)
        .def_rw("entries", &ShadowMapArrayResource::entries)
        .def("__len__", &ShadowMapArrayResource::__len__)
        .def("__getitem__", [](ShadowMapArrayResource& self, size_t index) -> ShadowMapArrayEntry& {
            if (index >= self.size()) {
                throw nb::index_error("ShadowMapArrayResource index out of range");
            }
            return self[index];
        }, nb::rv_policy::reference)
        .def("__iter__", [](ShadowMapArrayResource& self) {
            return nb::make_iterator(nb::type<ShadowMapArrayResource>(), "iterator",
                                     self.begin(), self.end());
        }, nb::keep_alive<0, 1>())
        .def("get_by_light_index", &ShadowMapArrayResource::get_by_light_index, nb::rv_policy::reference);

    auto color_pass = nb::class_<ColorPass, CxxFramePass>(m, "ColorPass")
        .def("__init__", [](ColorPass* self,
                            std::string input_res, std::string output_res,
                            nb::object shadow_res_obj, std::string phase_mark,
                            std::string pass_name, std::string sort_mode, bool clear_depth,
                            std::string camera_name) {
            std::string shadow_res = "shadow_maps";
            if (!shadow_res_obj.is_none()) {
                shadow_res = nb::cast<std::string>(shadow_res_obj);
            } else {
                shadow_res = "";
            }
            new (self) ColorPass(input_res, output_res, shadow_res, phase_mark, pass_name, sort_mode, clear_depth, camera_name);
            init_pass_from_python(self, "ColorPass");
        },
             nb::arg("input_res") = "empty",
             nb::arg("output_res") = "color",
             nb::arg("shadow_res").none() = nb::none(),
             nb::arg("phase_mark") = "opaque",
             nb::arg("pass_name") = "Color",
             nb::arg("sort_mode") = "none",
             nb::arg("clear_depth") = false,
             nb::arg("camera_name") = "")
        .def_rw("input_res", &ColorPass::input_res)
        .def_rw("output_res", &ColorPass::output_res)
        .def_rw("shadow_res", &ColorPass::shadow_res)
        .def_rw("phase_mark", &ColorPass::phase_mark)
        .def_rw("sort_mode", &ColorPass::sort_mode)
        .def_rw("clear_depth", &ColorPass::clear_depth)
        .def_rw("wireframe", &ColorPass::wireframe)
        .def_rw("camera_name", &ColorPass::camera_name)
        .def_rw("extra_textures", &ColorPass::extra_textures)
        .def("add_extra_texture", &ColorPass::add_extra_texture,
             nb::arg("uniform_name"), nb::arg("resource_name"))
        .def("compute_reads", &ColorPass::compute_reads)
        .def("compute_writes", &ColorPass::compute_writes)
        .def("get_inplace_aliases", &ColorPass::get_inplace_aliases)
        .def("get_resource_specs", &ColorPass::get_resource_specs)
        .def("get_internal_symbols", &ColorPass::get_internal_symbols)
        .def("get_internal_symbols_with_timing", &ColorPass::get_internal_symbols_with_timing)
        .def_prop_ro("reads", &ColorPass::compute_reads)
        .def_prop_ro("writes", &ColorPass::compute_writes)
        .def("destroy", &ColorPass::destroy)
        .def("__repr__", [](const ColorPass& p) {
            return "<ColorPass '" + p.get_pass_name() + "' phase='" + p.phase_mark + "'>";
        });

    color_pass.attr("category") = "Render";
    color_pass.attr("has_dynamic_inputs") = true;
    color_pass.attr("node_inputs") = nb::make_tuple(
        nb::make_tuple("input_res", "fbo"),
        nb::make_tuple("shadow_res", "shadow")
    );
    color_pass.attr("node_outputs") = nb::make_tuple(
        nb::make_tuple("output_res", "fbo")
    );
    color_pass.attr("node_inplace_pairs") = nb::make_tuple(
        nb::make_tuple("input_res", "output_res")
    );
    {
        nb::dict visibility;
        nb::dict camera_cond;
        camera_cond["_outside_viewport"] = true;
        visibility["camera_name"] = camera_cond;
        color_pass.attr("node_param_visibility") = visibility;
    }

    nb::class_<ShadowMapResult>(m, "ShadowMapResult")
        .def(nb::init<>())
        .def_ro("width", &ShadowMapResult::width)
        .def_ro("height", &ShadowMapResult::height)
        .def_prop_ro("light_space_matrix", [](const ShadowMapResult& self) {
            size_t shape[2] = {4, 4};
            float* data = new float[16];
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    data[row * 4 + col] = self.light_space_matrix(col, row);
                }
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            return nb::ndarray<nb::numpy, float, nb::ndim<2>>(data, 2, shape, owner);
        }, nb::rv_policy::move)
        .def_ro("light_index", &ShadowMapResult::light_index)
        .def_ro("cascade_index", &ShadowMapResult::cascade_index)
        .def_ro("cascade_split_near", &ShadowMapResult::cascade_split_near)
        .def_ro("cascade_split_far", &ShadowMapResult::cascade_split_far);

    nb::class_<ShadowPass, CxxFramePass>(m, "ShadowPass")
        .def("__init__", [](ShadowPass* self, const std::string& output_res,
                            const std::string& pass_name, float caster_offset) {
            new (self) ShadowPass(output_res, pass_name, caster_offset);
            init_pass_from_python(self, "ShadowPass");
        },
             nb::arg("output_res") = "shadow_maps",
             nb::arg("pass_name") = "Shadow",
             nb::arg("caster_offset") = 50.0f)
        .def_rw("output_res", &ShadowPass::output_res)
        .def_rw("caster_offset", &ShadowPass::caster_offset)
        .def("get_internal_symbols", &ShadowPass::get_internal_symbols)
        .def_prop_ro("reads", &ShadowPass::compute_reads)
        .def_prop_ro("writes", &ShadowPass::compute_writes)
        .def("destroy", &ShadowPass::destroy)
        .def("__repr__", [](const ShadowPass& p) {
            return "<ShadowPass '" + p.get_pass_name() + "'>";
        });

    {
        m.attr("ShadowPass").attr("category") = "Render";
        m.attr("ShadowPass").attr("node_inputs") = nb::make_tuple();
        m.attr("ShadowPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "shadow")
        );
    }

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

    nb::class_<DebugTrianglePass, CxxFramePass>(m, "DebugTrianglePass")
        .def("__init__", [](DebugTrianglePass* self,
                            const std::string& output_res,
                            const std::string& pass_name) {
            new (self) DebugTrianglePass(output_res, pass_name);
            init_pass_from_python(self, "DebugTrianglePass");
        },
             nb::arg("output_res") = "OUTPUT",
             nb::arg("pass_name") = "DebugTriangle")
        .def_rw("output_res", &DebugTrianglePass::output_res)
        .def("compute_reads", &DebugTrianglePass::compute_reads)
        .def("compute_writes", &DebugTrianglePass::compute_writes)
        .def("get_inplace_aliases", &DebugTrianglePass::get_inplace_aliases)
        .def_prop_ro("reads", &DebugTrianglePass::compute_reads)
        .def_prop_ro("writes", &DebugTrianglePass::compute_writes)
        .def("destroy", &DebugTrianglePass::destroy)
        .def("__repr__", [](const DebugTrianglePass& p) {
            return "<DebugTrianglePass '" + p.get_pass_name() + "'>";
        });

    {
        m.attr("DebugTrianglePass").attr("category") = "Debug";
        m.attr("DebugTrianglePass").attr("node_inputs") = nb::make_tuple();
        m.attr("DebugTrianglePass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
    }

    nb::class_<PresentToScreenPass, CxxFramePass>(m, "PresentToScreenPass")
        .def("__init__", [](PresentToScreenPass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name) {
            new (self) PresentToScreenPass(input_res, output_res);
            if (!pass_name.empty()) {
                self->set_pass_name(pass_name);
            }
            init_pass_from_python(self, "PresentToScreenPass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "OUTPUT",
             nb::arg("pass_name") = "PresentToScreen")
        .def_rw("input_res", &PresentToScreenPass::input_res)
        .def_rw("output_res", &PresentToScreenPass::output_res)
        .def("compute_reads", &PresentToScreenPass::compute_reads)
        .def("compute_writes", &PresentToScreenPass::compute_writes)
        .def("get_inplace_aliases", &PresentToScreenPass::get_inplace_aliases)
        .def_prop_ro("reads", &PresentToScreenPass::compute_reads)
        .def_prop_ro("writes", &PresentToScreenPass::compute_writes)
        .def("destroy", &PresentToScreenPass::destroy);

    {
        m.attr("PresentToScreenPass").attr("category") = "Output";
        m.attr("PresentToScreenPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("PresentToScreenPass").attr("node_outputs") = nb::make_tuple();
    }

    nb::class_<BloomPass, CxxFramePass>(m, "BloomPass")
        .def("__init__", [](BloomPass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name,
                            float threshold,
                            float soft_threshold,
                            float intensity,
                            int mip_levels) {
            new (self) BloomPass(input_res, output_res, threshold, soft_threshold, intensity, mip_levels);
            if (!pass_name.empty()) {
                self->set_pass_name(pass_name);
            }
            init_pass_from_python(self, "BloomPass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "Bloom",
             nb::arg("threshold") = 1.0f,
             nb::arg("soft_threshold") = 0.5f,
             nb::arg("intensity") = 1.0f,
             nb::arg("mip_levels") = 5)
        .def_rw("input_res", &BloomPass::input_res)
        .def_rw("output_res", &BloomPass::output_res)
        .def_rw("threshold", &BloomPass::threshold)
        .def_rw("soft_threshold", &BloomPass::soft_threshold)
        .def_rw("intensity", &BloomPass::intensity)
        .def_rw("mip_levels", &BloomPass::mip_levels)
        .def("compute_reads", &BloomPass::compute_reads)
        .def("compute_writes", &BloomPass::compute_writes)
        .def("get_inplace_aliases", &BloomPass::get_inplace_aliases)
        .def_prop_ro("reads", &BloomPass::compute_reads)
        .def_prop_ro("writes", &BloomPass::compute_writes)
        .def("destroy", &BloomPass::destroy);

    {
        m.attr("BloomPass").attr("category") = "Effects";
        m.attr("BloomPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("BloomPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("BloomPass").attr("node_inplace_pairs") = nb::make_tuple();
    }

    nb::class_<GrayscalePass, CxxFramePass>(m, "GrayscalePass")
        .def("__init__", [](GrayscalePass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name,
                            float strength) {
            new (self) GrayscalePass(input_res, output_res, strength);
            if (!pass_name.empty()) {
                self->set_pass_name(pass_name);
            }
            init_pass_from_python(self, "GrayscalePass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "Grayscale",
             nb::arg("strength") = 1.0f)
        .def_rw("input_res", &GrayscalePass::input_res)
        .def_rw("output_res", &GrayscalePass::output_res)
        .def_rw("strength", &GrayscalePass::strength)
        .def("compute_reads", &GrayscalePass::compute_reads)
        .def("compute_writes", &GrayscalePass::compute_writes)
        .def("get_inplace_aliases", &GrayscalePass::get_inplace_aliases)
        .def_prop_ro("reads", &GrayscalePass::compute_reads)
        .def_prop_ro("writes", &GrayscalePass::compute_writes)
        .def("destroy", &GrayscalePass::destroy);

    {
        m.attr("GrayscalePass").attr("category") = "Effects";
        m.attr("GrayscalePass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("GrayscalePass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("GrayscalePass").attr("node_inplace_pairs") = nb::make_tuple();
    }

    nb::class_<SkyBoxPass, CxxFramePass>(m, "SkyBoxPass")
        .def("__init__", [](SkyBoxPass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name) {
            new (self) SkyBoxPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "SkyBoxPass");
        },
             nb::arg("input_res") = "empty",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "Skybox")
        .def_rw("input_res", &SkyBoxPass::input_res)
        .def_rw("output_res", &SkyBoxPass::output_res)
        .def("compute_reads", &SkyBoxPass::compute_reads)
        .def("compute_writes", &SkyBoxPass::compute_writes)
        .def("get_inplace_aliases", &SkyBoxPass::get_inplace_aliases)
        .def_prop_ro("reads", &SkyBoxPass::compute_reads)
        .def_prop_ro("writes", &SkyBoxPass::compute_writes)
        .def("destroy", &SkyBoxPass::destroy);

    {
        m.attr("SkyBoxPass").attr("category") = "Render";
        m.attr("SkyBoxPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("SkyBoxPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("SkyBoxPass").attr("node_inplace_pairs") = nb::make_tuple(
            nb::make_tuple("input_res", "output_res")
        );
    }

    nb::class_<TonemapPass, CxxFramePass>(m, "TonemapPass")
        .def("__init__", [](TonemapPass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name,
                            float exposure,
                            int method) {
            new (self) TonemapPass(input_res, output_res, exposure, method);
            if (!pass_name.empty()) {
                self->set_pass_name(pass_name);
            }
            init_pass_from_python(self, "TonemapPass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "Tonemap",
             nb::arg("exposure") = 1.0f,
             nb::arg("method") = 0)
        .def_rw("input_res", &TonemapPass::input_res)
        .def_rw("output_res", &TonemapPass::output_res)
        .def_rw("exposure", &TonemapPass::exposure)
        .def_rw("method", &TonemapPass::method)
        .def("compute_reads", &TonemapPass::compute_reads)
        .def("compute_writes", &TonemapPass::compute_writes)
        .def("get_inplace_aliases", &TonemapPass::get_inplace_aliases)
        .def_prop_ro("reads", &TonemapPass::compute_reads)
        .def_prop_ro("writes", &TonemapPass::compute_writes)
        .def("destroy", &TonemapPass::destroy);

    {
        m.attr("TonemapPass").attr("category") = "Effects";
        m.attr("TonemapPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("TonemapPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("TonemapPass").attr("node_inplace_pairs") = nb::make_tuple();
    }

    m.attr("TONEMAP_ACES") = 0;
    m.attr("TONEMAP_REINHARD") = 1;
    m.attr("TONEMAP_NONE") = 2;
}

} // namespace termin
