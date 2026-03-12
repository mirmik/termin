#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/set.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/unordered_map.h>

#include <tgfx/tgfx_material_handle.hpp>

#include <termin/bindings/entity_helpers.hpp>
#include <termin/camera/camera_component.hpp>
#include <termin/render/depth_pass.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/material_pass.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/normal_pass.hpp>
#include <tcbase/tc_log.hpp>

namespace nb = nanobind;

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

template<typename T>
nb::object init_pass_from_deserialize(T* pass, const char* type_name) {
    pass->link_to_type_registry(type_name);
    nb::object wrapper = nb::cast(pass, nb::rv_policy::take_ownership);
    pass->set_python_ref(wrapper.ptr(), &g_py_cxx_pass_ref_vtable);
    Py_INCREF(wrapper.ptr());
    return wrapper;
}

static FBOMap dict_to_fbo_map(nb::dict src) {
    FBOMap result;
    for (auto item : src) {
        std::string key = nb::cast<std::string>(nb::str(item.first));
        nb::object val = nb::borrow<nb::object>(item.second);
        if (val.is_none()) {
            continue;
        }
        try {
            result[key] = nb::cast<FramebufferHandle*>(val);
        } catch (const nb::cast_error&) {
            tc::Log::error("[render_components] Expected FBO for key '%s'", key.c_str());
        }
    }
    return result;
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
    tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
    if (!scene_py.is_none() && nb::hasattr(scene_py, "scene_handle")) {
        auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene_py.attr("scene_handle")());
        scene.index = std::get<0>(h);
        scene.generation = std::get<1>(h);
    }
    return scene;
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

static void set_material_from_python(MaterialPass& pass, nb::object material_obj) {
    if (material_obj.is_none()) {
        pass.material = TcMaterial();
        return;
    }

    if (nb::isinstance<nb::str>(material_obj)) {
        try {
            nb::module_ rm_mod = nb::module_::import_("termin.visualization.core.resources");
            nb::object rm = rm_mod.attr("ResourceManager").attr("instance")();
            nb::object material = rm.attr("get_material")(material_obj);
            if (material.is_none()) {
                tc::Log::error("[render_components] Material '%s' not found",
                    nb::cast<std::string>(material_obj).c_str());
                pass.material = TcMaterial();
                return;
            }
            pass.material = nb::cast<TcMaterial>(material);
            return;
        } catch (const std::exception& e) {
            tc::Log::error("[render_components] Failed to resolve material: %s", e.what());
            pass.material = TcMaterial();
            return;
        }
    }

    try {
        pass.material = nb::cast<TcMaterial>(material_obj);
    } catch (const std::exception& e) {
        tc::Log::error("[render_components] Failed to assign material: %s", e.what());
        pass.material = TcMaterial();
    }
}

} // namespace termin

using namespace termin;

NB_MODULE(_components_render_native, m) {
    m.doc() = "Native render components bindings";

    nb::module_::import_("tgfx._tgfx_native");
    nb::module_::import_("termin.entity._entity_native");
    nb::module_::import_("termin.render_framework._render_framework_native");
    nb::module_::import_("termin.viewport._viewport_native");

    nb::class_<CameraComponent, CxxComponent>(m, "CameraComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<CameraComponent>(self);
        })
        .def_prop_rw("projection_type",
            &CameraComponent::get_projection_type_str,
            &CameraComponent::set_projection_type_str)
        .def_rw("near", &CameraComponent::near_clip)
        .def_rw("far", &CameraComponent::far_clip)
        .def_prop_rw("near_clip",
            [](CameraComponent& c) { return c.near_clip; },
            [](CameraComponent& c, double v) { c.near_clip = v; })
        .def_prop_rw("far_clip",
            [](CameraComponent& c) { return c.far_clip; },
            [](CameraComponent& c, double v) { c.far_clip = v; })
        .def_prop_rw("fov_mode",
            &CameraComponent::get_fov_mode_str,
            &CameraComponent::set_fov_mode_str)
        .def_rw("fov_x", &CameraComponent::fov_x)
        .def_rw("fov_y", &CameraComponent::fov_y)
        .def_prop_rw("fov_x_degrees",
            &CameraComponent::get_fov_x_degrees,
            &CameraComponent::set_fov_x_degrees)
        .def_prop_rw("fov_y_degrees",
            &CameraComponent::get_fov_y_degrees,
            &CameraComponent::set_fov_y_degrees)
        .def_rw("aspect", &CameraComponent::aspect)
        .def("set_aspect", &CameraComponent::set_aspect, nb::arg("aspect"))
        .def_rw("ortho_size", &CameraComponent::ortho_size)
        .def("get_view_matrix", &CameraComponent::get_view_matrix)
        .def("get_projection_matrix", &CameraComponent::get_projection_matrix)
        .def("view_matrix", &CameraComponent::get_view_matrix)
        .def("projection_matrix", &CameraComponent::get_projection_matrix)
        .def("get_position", &CameraComponent::get_position)
        .def("add_viewport", [](CameraComponent& c, nb::object viewport) {
            auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(viewport.attr("_viewport_handle")());
            tc_viewport_handle handle;
            handle.index = std::get<0>(h);
            handle.generation = std::get<1>(h);
            c.add_viewport(TcViewport(handle));
        }, nb::arg("viewport"))
        .def("remove_viewport", [](CameraComponent& c, nb::object viewport) {
            auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(viewport.attr("_viewport_handle")());
            tc_viewport_handle handle;
            handle.index = std::get<0>(h);
            handle.generation = std::get<1>(h);
            c.remove_viewport(TcViewport(handle));
        }, nb::arg("viewport"))
        .def("has_viewport", [](CameraComponent& c, nb::object viewport) {
            auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(viewport.attr("_viewport_handle")());
            tc_viewport_handle handle;
            handle.index = std::get<0>(h);
            handle.generation = std::get<1>(h);
            return c.has_viewport(TcViewport(handle));
        }, nb::arg("viewport"))
        .def_prop_ro("viewport_count", &CameraComponent::viewport_count)
        .def("clear_viewports", &CameraComponent::clear_viewports)
        .def_prop_ro("viewport", [](CameraComponent& c) -> nb::object {
            if (c.viewport_count() == 0) {
                return nb::none();
            }
            TcViewport vp = c.viewport_at(0);
            if (!vp.is_valid()) {
                return nb::none();
            }
            nb::module_ vp_native = nb::module_::import_("termin.viewport._viewport_native");
            nb::object vp_class = vp_native.attr("Viewport");
            auto h = std::make_tuple(vp.handle_.index, vp.handle_.generation);
            return vp_class.attr("_from_handle")(h);
        })
        .def("screen_point_to_ray", [](CameraComponent& c, double x, double y, nb::object viewport_rect) {
            auto rect = nb::cast<std::tuple<int, int, int, int>>(viewport_rect);
            int vp_x = std::get<0>(rect);
            int vp_y = std::get<1>(rect);
            int vp_w = std::get<2>(rect);
            int vp_h = std::get<3>(rect);
            auto [origin, direction] = c.screen_point_to_ray(x, y, vp_x, vp_y, vp_w, vp_h);
            nb::module_ geombase = nb::module_::import_("termin.geombase");
            nb::object Ray3 = geombase.attr("Ray3");
            nb::object Vec3 = geombase.attr("Vec3");
            nb::object py_origin = Vec3(origin.x, origin.y, origin.z);
            nb::object py_direction = Vec3(direction.x, direction.y, direction.z);
            return Ray3(py_origin, py_direction);
        }, nb::arg("x"), nb::arg("y"), nb::arg("viewport_rect"))
        .def("c_component_ptr", [](CameraComponent& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(c.c_component());
        })
        .def("_cxx_component_ptr", [](CameraComponent& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(&c);
        })
        .def_static("_from_c_component_ptr", [](uintptr_t ptr) -> nb::object {
            if (ptr == 0) {
                return nb::none();
            }

            tc_component* tc = reinterpret_cast<tc_component*>(ptr);
            if (tc->native_language == TC_LANGUAGE_PYTHON && tc->body) {
                return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(tc->body));
            }
            if (tc->kind != TC_CXX_COMPONENT) {
                return nb::none();
            }

            CxxComponent* cxx = CxxComponent::from_tc(tc);
            if (!cxx) {
                return nb::none();
            }

            return nb::cast(static_cast<CameraComponent*>(cxx), nb::rv_policy::reference);
        })
        .def_static("_from_cxx_component_ptr", [](uintptr_t ptr) -> nb::object {
            if (ptr == 0) {
                return nb::none();
            }
            auto* cxx = reinterpret_cast<CameraComponent*>(ptr);
            return nb::cast(cxx, nb::rv_policy::reference);
        });

    m.def("PerspectiveCameraComponent", [](double fov_degrees, double aspect, double near, double far) {
        auto* cam = new CameraComponent();
        cam->set_fov_x_degrees(fov_degrees);
        cam->fov_mode = FovMode::FixHorizontal;
        cam->aspect = aspect;
        cam->near_clip = near;
        cam->far_clip = far;
        cam->projection_type = CameraProjection::Perspective;
        return cam;
    },
    nb::arg("fov_degrees") = 60.0,
    nb::arg("aspect") = 1.0,
    nb::arg("near") = 0.1,
    nb::arg("far") = 100.0,
    nb::rv_policy::take_ownership);

    m.def("OrthographicCameraComponent", [](double ortho_size, double aspect, double near, double far) {
        auto* cam = new CameraComponent();
        cam->ortho_size = ortho_size;
        cam->aspect = aspect;
        cam->near_clip = near;
        cam->far_clip = far;
        cam->projection_type = CameraProjection::Orthographic;
        return cam;
    },
    nb::arg("ortho_size") = 5.0,
    nb::arg("aspect") = 1.0,
    nb::arg("near") = 0.1,
    nb::arg("far") = 100.0,
    nb::rv_policy::take_ownership);

    nb::class_<MeshRenderer, Component>(m, "MeshRenderer")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<MeshRenderer>(self);
        })
        .def("__init__", [](nb::handle self, nb::object mesh_arg, nb::object material_arg, bool cast_shadow) {
            cxx_component_init<MeshRenderer>(self);
            auto* cpp = nb::inst_ptr<MeshRenderer>(self);
            cpp->cast_shadow = cast_shadow;

            if (!mesh_arg.is_none()) {
                if (nb::isinstance<TcMesh>(mesh_arg)) {
                    cpp->mesh = nb::cast<TcMesh>(mesh_arg);
                } else if (nb::hasattr(mesh_arg, "mesh_data")) {
                    nb::object res = mesh_arg.attr("mesh_data");
                    if (nb::isinstance<TcMesh>(res)) {
                        cpp->mesh = nb::cast<TcMesh>(res);
                    }
                } else if (nb::isinstance<nb::str>(mesh_arg)) {
                    cpp->set_mesh_by_name(nb::cast<std::string>(mesh_arg));
                }
            }

            if (!material_arg.is_none()) {
                if (nb::isinstance<TcMaterial>(material_arg)) {
                    cpp->material = nb::cast<TcMaterial>(material_arg);
                } else if (nb::isinstance<nb::str>(material_arg)) {
                    cpp->set_material_by_name(nb::cast<std::string>(material_arg));
                }
            }
        }, nb::arg("mesh") = nb::none(), nb::arg("material") = nb::none(), nb::arg("cast_shadow") = true)
        .def_prop_rw("mesh",
            [](MeshRenderer& self) -> TcMesh& { return self.mesh; },
            [](MeshRenderer& self, const TcMesh& v) { self.mesh = v; },
            nb::rv_policy::reference_internal)
        .def_prop_rw("material",
            [](MeshRenderer& self) -> TcMaterial& { return self.material; },
            [](MeshRenderer& self, const TcMaterial& v) { self.set_material(v); },
            nb::rv_policy::reference_internal)
        .def_rw("cast_shadow", &MeshRenderer::cast_shadow)
        .def_prop_rw("_override_material",
            [](MeshRenderer& self) { return self._override_material; },
            [](MeshRenderer& self, bool v) {
                self._override_material = v;
                if (v && !self._overridden_material.is_valid()) {
                    self.try_create_override_material();
                } else if (!v) {
                    self._overridden_material = TcMaterial();
                }
            })
        .def("get_mesh", [](MeshRenderer& self) -> TcMesh& { return self.get_mesh(); }, nb::rv_policy::reference_internal)
        .def("set_mesh", &MeshRenderer::set_mesh)
        .def("set_mesh_by_name", &MeshRenderer::set_mesh_by_name)
        .def("get_material", &MeshRenderer::get_material)
        .def("get_base_material", &MeshRenderer::get_base_material)
        .def("set_material", &MeshRenderer::set_material)
        .def("set_material_by_name", &MeshRenderer::set_material_by_name)
        .def_prop_rw("override_material", &MeshRenderer::override_material, &MeshRenderer::set_override_material)
        .def("set_override_material", &MeshRenderer::set_override_material)
        .def("get_overridden_material", &MeshRenderer::get_overridden_material)
        .def_prop_ro("phase_marks", [](MeshRenderer& self) {
            nb::set marks;
            for (const auto& mark : self.phase_marks()) {
                marks.add(nb::str(mark.c_str()));
            }
            return marks;
        })
        .def("draw_geometry", &MeshRenderer::draw_geometry, nb::arg("context"), nb::arg("geometry_id") = 0)
        .def("get_phases_for_mark", &MeshRenderer::get_phases_for_mark, nb::arg("phase_mark"))
        .def("get_geometry_draws", [](MeshRenderer& self, nb::object phase_mark) {
            if (phase_mark.is_none()) {
                return self.get_geometry_draws(nullptr);
            }
            std::string pm = nb::cast<std::string>(phase_mark);
            return self.get_geometry_draws(&pm);
        }, nb::arg("phase_mark") = nb::none());

    nb::class_<DepthPass, CxxFramePass>(m, "DepthPass")
        .def("__init__", [](DepthPass* self, const std::string& input_res, const std::string& output_res, const std::string& pass_name) {
            new (self) DepthPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "DepthPass");
        }, nb::arg("input_res") = "empty_depth", nb::arg("output_res") = "depth", nb::arg("pass_name") = "Depth")
        .def_rw("input_res", &DepthPass::input_res)
        .def_rw("output_res", &DepthPass::output_res)
        .def_rw("camera_name", &DepthPass::camera_name)
        .def("get_internal_symbols", &DepthPass::get_internal_symbols)
        .def("execute_with_data", [](DepthPass& self, GraphicsBackend* graphics, nb::dict reads_fbos_py, nb::dict writes_fbos_py, nb::tuple rect_py, nb::object scene_py, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view_py, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> projection_py, float near_plane, float far_plane, uint64_t layer_mask) {
            self.execute_with_data(graphics, dict_to_fbo_map(reads_fbos_py), dict_to_fbo_map(writes_fbos_py), tuple_to_rect(rect_py), object_to_scene_handle(scene_py), ndarray_to_mat44f(view_py), ndarray_to_mat44f(projection_py), near_plane, far_plane, layer_mask);
        }, nb::arg("graphics"), nb::arg("reads_fbos"), nb::arg("writes_fbos"), nb::arg("rect"), nb::arg("scene"), nb::arg("view"), nb::arg("projection"), nb::arg("near_plane"), nb::arg("far_plane"), nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            (void)resource_manager;
            std::string pass_name = "Depth";
            std::string camera_name;
            std::string input_res = "empty_depth";
            std::string output_res = "depth";
            if (data.contains("pass_name")) pass_name = nb::cast<std::string>(data["pass_name"]);
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("camera_name")) camera_name = nb::cast<std::string>(d["camera_name"]);
                if (d.contains("input_res")) input_res = nb::cast<std::string>(d["input_res"]);
                if (d.contains("output_res")) output_res = nb::cast<std::string>(d["output_res"]);
            }
            auto* p = new DepthPass(input_res, output_res, pass_name);
            p->camera_name = camera_name;
            return init_pass_from_deserialize(p, "DepthPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &DepthPass::compute_reads)
        .def_prop_ro("writes", &DepthPass::compute_writes)
        .def("destroy", &DepthPass::destroy);

    {
        nb::dict visibility;
        nb::dict camera_cond;
        camera_cond["_outside_viewport"] = true;
        visibility["camera_name"] = camera_cond;
        m.attr("DepthPass").attr("node_param_visibility") = visibility;
        m.attr("DepthPass").attr("category") = "Render";
        m.attr("DepthPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        m.attr("DepthPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("DepthPass").attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("input_res", "output_res"));
    }

    nb::class_<NormalPass, CxxFramePass>(m, "NormalPass")
        .def("__init__", [](NormalPass* self, const std::string& input_res, const std::string& output_res, const std::string& pass_name) {
            new (self) NormalPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "NormalPass");
        }, nb::arg("input_res") = "empty_normal", nb::arg("output_res") = "normal", nb::arg("pass_name") = "Normal")
        .def_rw("input_res", &NormalPass::input_res)
        .def_rw("output_res", &NormalPass::output_res)
        .def_rw("camera_name", &NormalPass::camera_name)
        .def("get_resource_specs", &NormalPass::get_resource_specs)
        .def("get_internal_symbols", &NormalPass::get_internal_symbols)
        .def("execute_with_data", [](NormalPass& self, GraphicsBackend* graphics, nb::dict reads_fbos_py, nb::dict writes_fbos_py, nb::tuple rect_py, nb::object scene_py, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view_py, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> projection_py, uint64_t layer_mask) {
            self.execute_with_data(graphics, dict_to_fbo_map(reads_fbos_py), dict_to_fbo_map(writes_fbos_py), tuple_to_rect(rect_py), object_to_scene_handle(scene_py), ndarray_to_mat44f(view_py), ndarray_to_mat44f(projection_py), layer_mask);
        }, nb::arg("graphics"), nb::arg("reads_fbos"), nb::arg("writes_fbos"), nb::arg("rect"), nb::arg("scene"), nb::arg("view"), nb::arg("projection"), nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            (void)resource_manager;
            std::string pass_name = "Normal";
            std::string camera_name;
            std::string input_res = "empty_normal";
            std::string output_res = "normal";
            if (data.contains("pass_name")) pass_name = nb::cast<std::string>(data["pass_name"]);
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("camera_name")) camera_name = nb::cast<std::string>(d["camera_name"]);
                if (d.contains("input_res")) input_res = nb::cast<std::string>(d["input_res"]);
                if (d.contains("output_res")) output_res = nb::cast<std::string>(d["output_res"]);
            }
            auto* p = new NormalPass(input_res, output_res, pass_name);
            p->camera_name = camera_name;
            return init_pass_from_deserialize(p, "NormalPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &NormalPass::compute_reads)
        .def_prop_ro("writes", &NormalPass::compute_writes)
        .def("destroy", &NormalPass::destroy);

    {
        nb::dict visibility;
        nb::dict camera_cond;
        camera_cond["_outside_viewport"] = true;
        visibility["camera_name"] = camera_cond;
        m.attr("NormalPass").attr("node_param_visibility") = visibility;
        m.attr("NormalPass").attr("category") = "Render";
        m.attr("NormalPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        m.attr("NormalPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("NormalPass").attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("input_res", "output_res"));
    }

    nb::class_<MaterialPass, CxxFramePass>(m, "MaterialPass")
        .def("__init__", [](MaterialPass* self, const std::string& input_res, const std::string& output_res, nb::object material, const std::string& pass_name) {
            new (self) MaterialPass();
            self->output_res = output_res;
            self->set_pass_name(pass_name);
            if (!input_res.empty()) {
                self->add_resource(input_res, "input");
            }
            set_material_from_python(*self, material);
            init_pass_from_python(self, "MaterialPass");
        }, nb::arg("input_res") = "input", nb::arg("output_res") = "output", nb::arg("material") = nb::none(), nb::arg("pass_name") = "MaterialPass")
        .def_prop_rw("input_res",
            [](MaterialPass& self) -> std::string {
                auto it = self.texture_resources.find("u_input");
                if (it != self.texture_resources.end()) {
                    return it->second;
                }
                auto extra_it = self.extra_resources.find("input");
                if (extra_it != self.extra_resources.end()) {
                    return "input";
                }
                return "";
            },
            [](MaterialPass& self, const std::string& value) {
                self.texture_resources.erase("u_input");
                self.extra_resources.erase("input");
                if (!value.empty()) {
                    self.add_resource(value, "input");
                }
            })
        .def_rw("output_res", &MaterialPass::output_res)
        .def_prop_rw("material",
            [](MaterialPass& self) -> TcMaterial {
                return self.material;
            },
            [](MaterialPass& self, nb::object material) {
                set_material_from_python(self, material);
            })
        .def_rw("texture_resources", &MaterialPass::texture_resources)
        .def_rw("extra_resources", &MaterialPass::extra_resources)
        .def("set_texture_resource", &MaterialPass::set_texture_resource,
            nb::arg("uniform_name"), nb::arg("resource_name"))
        .def("add_resource", &MaterialPass::add_resource,
            nb::arg("resource_name"), nb::arg("uniform_name") = "")
        .def("remove_resource", &MaterialPass::remove_resource,
            nb::arg("resource_name"))
        .def("get_internal_symbols", &MaterialPass::get_internal_symbols)
        .def("execute_with_data", [](MaterialPass& self, GraphicsBackend* graphics, nb::dict reads_fbos_py, nb::dict writes_fbos_py, nb::tuple rect_py) {
            ExecuteContext ctx;
            ctx.graphics = graphics;
            ctx.reads_fbos = dict_to_fbo_map(reads_fbos_py);
            ctx.writes_fbos = dict_to_fbo_map(writes_fbos_py);
            ctx.rect = tuple_to_rect(rect_py);
            self.execute(ctx);
        }, nb::arg("graphics"), nb::arg("reads_fbos"), nb::arg("writes_fbos"), nb::arg("rect"))
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            (void)resource_manager;
            std::string pass_name = "MaterialPass";
            std::string input_res = "input";
            std::string output_res = "output";
            nb::object material = nb::none();
            if (data.contains("pass_name")) pass_name = nb::cast<std::string>(data["pass_name"]);
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("input_res")) input_res = nb::cast<std::string>(d["input_res"]);
                if (d.contains("output_res")) output_res = nb::cast<std::string>(d["output_res"]);
                if (d.contains("material")) material = nb::borrow<nb::object>(d["material"]);
            }
            auto* p = new MaterialPass();
            p->output_res = output_res;
            p->set_pass_name(pass_name);
            if (!input_res.empty()) {
                p->add_resource(input_res, "input");
            }
            set_material_from_python(*p, material);
            return init_pass_from_deserialize(p, "MaterialPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &MaterialPass::compute_reads)
        .def_prop_ro("writes", &MaterialPass::compute_writes)
        .def("destroy", &MaterialPass::destroy);

    {
        m.attr("MaterialPass").attr("category") = "Render";
        m.attr("MaterialPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        m.attr("MaterialPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("MaterialPass").attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("input_res", "output_res"));
        m.attr("MaterialPass").attr("has_dynamic_inputs") = true;
    }
}
