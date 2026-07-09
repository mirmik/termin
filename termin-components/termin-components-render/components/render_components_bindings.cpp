#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/set.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/vector.h>

#include <tgfx/tgfx_material_handle.hpp>

#include <algorithm>
#include <tc_inspect_cpp.hpp>
#include <termin/bindings/entity_helpers.hpp>
#include <termin/camera/camera.hpp>
#include <termin/camera/camera_component.hpp>
#include <termin/lighting/light_component.hpp>
#include <termin/render/depth_pass.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/line_renderer.hpp>
#include <termin/render/material_pass.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/normal_pass.hpp>
#include <termin/render/skeleton_controller.hpp>
#include <termin/render/skinned_mesh_renderer.hpp>
#include <termin/render/world_text_component.hpp>
#include <termin/xr/xr_origin_component.hpp>
#include <termin/xr/xr_thumbstick_locomotion_component.hpp>
#include <tcbase/tc_log.hpp>

#include "orbit_camera_bindings.hpp"

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

static Rect2i tuple_to_rect(nb::tuple rect_py) {
    Rect2i rect;
    rect.x = nb::cast<int>(rect_py[0]);
    rect.y = nb::cast<int>(rect_py[1]);
    rect.width = nb::cast<int>(rect_py[2]);
    rect.height = nb::cast<int>(rect_py[3]);
    return rect;
}

static tc_scene_handle object_to_scene_handle(nb::object scene_py) {
    if (scene_py.is_none()) return TC_SCENE_HANDLE_INVALID;
    return nb::cast<tc_scene_handle>(scene_py.attr("scene_handle")());
}

static void set_material_from_python(MaterialPass& pass, nb::object material_obj) {
    if (material_obj.is_none()) {
        pass.material = TcMaterial();
        return;
    }

    if (nb::isinstance<nb::dict>(material_obj)) {
        nb::dict material_ref = nb::cast<nb::dict>(material_obj);
        std::string uuid;
        std::string name;

        if (material_ref.contains("uuid")) {
            nb::object uuid_obj = nb::borrow<nb::object>(material_ref["uuid"]);
            if (nb::isinstance<nb::str>(uuid_obj)) {
                uuid = nb::cast<std::string>(uuid_obj);
                TcMaterial material = TcMaterial::from_uuid(uuid);
                if (material.is_valid()) {
                    pass.material = material;
                    return;
                }
            }
        }

        if (material_ref.contains("name")) {
            nb::object name_obj = nb::borrow<nb::object>(material_ref["name"]);
            if (nb::isinstance<nb::str>(name_obj)) {
                name = nb::cast<std::string>(name_obj);
                TcMaterial material = TcMaterial::from_name(name);
                if (material.is_valid()) {
                    pass.material = material;
                    return;
                }
            }
        }

        tc::Log::error(
            "[render_components] Material reference not found: uuid=%s name=%s",
            uuid.c_str(),
            name.c_str()
        );
        pass.material = TcMaterial();
        return;
    }

    if (nb::isinstance<nb::str>(material_obj)) {
        try {
            nb::module_ assets_mod = nb::module_::import_("termin_assets");
            nb::object rm = assets_mod.attr("get_resource_manager")();
            if (rm.is_none()) {
                tc::Log::error("[render_components] Resource manager is not configured");
                pass.material = TcMaterial();
                return;
            }
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

static tc_vec3 tc_vec3_from_vec3(const Vec3& value) {
    return tc_vec3{
        value.x,
        value.y,
        value.z,
    };
}

static std::vector<tc_vec3> tc_vec3_list_from_vec3_list(const std::vector<Vec3>& points) {
    std::vector<tc_vec3> result;
    result.reserve(points.size());
    for (const Vec3& point : points) {
        result.push_back(tc_vec3_from_vec3(point));
    }
    return result;
}

static nb::list tc_vec3_list_to_python(const std::vector<tc_vec3>& points) {
    nb::list result;
    for (const tc_vec3& point : points) {
        result.append(Vec3{point.x, point.y, point.z});
    }
    return result;
}

} // namespace termin

using namespace termin;

NB_MODULE(_components_render_native, m) {
    m.doc() = "Native render components bindings";

    nb::module_::import_("tgfx._tgfx_native");
    nb::module_::import_("tmesh._tmesh_native");
    nb::module_::import_("termin.scene._scene_native");
    nb::module_::import_("termin.lighting._lighting_native");
    nb::module_::import_("termin.materials._materials_native");
    nb::module_::import_("termin.render._render_native");
    nb::module_::import_("termin.render_framework._render_framework_native");
    nb::module_::import_("termin.skeleton._components_skeleton_native");
    nb::module_::import_("termin.display._display_native");
    nb::module_::import_("termin.viewport._viewport_native");
    nb::module_::import_("tcbase._tcbase_native");

    tc::init_cpp_inspect_vtable();

    nb::enum_<CameraProjection>(m, "CameraProjection")
        .value("Perspective", CameraProjection::Perspective)
        .value("Orthographic", CameraProjection::Orthographic);

    nb::class_<Camera>(m, "Camera")
        .def(nb::init<>())
        .def_rw("projection_type", &Camera::projection_type)
        .def_rw("near", &Camera::near)
        .def_rw("far", &Camera::far)
        .def_rw("fov_y", &Camera::fov_y)
        .def_rw("aspect", &Camera::aspect)
        .def_rw("ortho_left", &Camera::ortho_left)
        .def_rw("ortho_right", &Camera::ortho_right)
        .def_rw("ortho_bottom", &Camera::ortho_bottom)
        .def_rw("ortho_top", &Camera::ortho_top)
        .def_static("perspective", &Camera::perspective,
            nb::arg("fov_y_rad"), nb::arg("aspect"),
            nb::arg("near") = 0.1, nb::arg("far") = 100.0)
        .def_static("perspective_deg", &Camera::perspective_deg,
            nb::arg("fov_y_deg"), nb::arg("aspect"),
            nb::arg("near") = 0.1, nb::arg("far") = 100.0)
        .def_static("orthographic", &Camera::orthographic,
            nb::arg("left"), nb::arg("right"),
            nb::arg("bottom"), nb::arg("top"),
            nb::arg("near") = 0.1, nb::arg("far") = 100.0)
        .def("projection_matrix", &Camera::projection_matrix)
        .def_static("view_matrix", &Camera::view_matrix,
            nb::arg("position"), nb::arg("rotation"))
        .def_static("view_matrix_look_at", &Camera::view_matrix_look_at,
            nb::arg("eye"), nb::arg("target"),
            nb::arg("up") = Vec3::unit_z())
        .def("set_aspect", &Camera::set_aspect, nb::arg("aspect"))
        .def("set_fov", &Camera::set_fov, nb::arg("fov_rad"))
        .def("set_fov_deg", &Camera::set_fov_deg, nb::arg("fov_deg"))
        .def("get_fov_deg", &Camera::get_fov_deg)
        .def("__repr__", [](const Camera& cam) -> std::string {
            if (cam.projection_type == CameraProjection::Perspective) {
                return "<Camera perspective fov=" + std::to_string(cam.get_fov_deg()) + "deg>";
            }
            return "<Camera orthographic>";
        });

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
        .def_rw("layer_mask", &CameraComponent::layer_mask)
        .def_rw("render_category_mask", &CameraComponent::render_category_mask)
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
            nb::module_ geom = nb::module_::import_("tcbase._geom_native");
            nb::module_ colliders = nb::module_::import_("termin.colliders._colliders_native");
            nb::object Vec3 = geom.attr("Vec3");
            nb::object Ray3 = colliders.attr("Ray3");
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

    bind_orbit_camera_controller(m);

    nb::class_<XrOriginComponent, CxxComponent>(m, "XrOriginComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<XrOriginComponent>(self);
        })
        .def_prop_rw("reference_space",
            &XrOriginComponent::get_reference_space_str,
            &XrOriginComponent::set_reference_space_str)
        .def_prop_rw("reference_alignment",
            &XrOriginComponent::get_reference_alignment_str,
            &XrOriginComponent::set_reference_alignment_str)
        .def_rw("near", &XrOriginComponent::near_clip)
        .def_rw("far", &XrOriginComponent::far_clip)
        .def_prop_rw("near_clip",
            [](XrOriginComponent& c) { return c.near_clip; },
            [](XrOriginComponent& c, double v) { c.near_clip = v; })
        .def_prop_rw("far_clip",
            [](XrOriginComponent& c) { return c.far_clip; },
            [](XrOriginComponent& c, double v) { c.far_clip = v; })
        .def_rw("layer_mask", &XrOriginComponent::layer_mask)
        .def("c_component_ptr", [](XrOriginComponent& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(c.c_component());
        })
        .def("_cxx_component_ptr", [](XrOriginComponent& c) -> uintptr_t {
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

            return nb::cast(static_cast<XrOriginComponent*>(cxx), nb::rv_policy::reference);
        })
        .def_static("_from_cxx_component_ptr", [](uintptr_t ptr) -> nb::object {
            if (ptr == 0) {
                return nb::none();
            }
            auto* cxx = reinterpret_cast<XrOriginComponent*>(ptr);
            return nb::cast(cxx, nb::rv_policy::reference);
        });

    nb::class_<XrThumbstickLocomotionComponent, CxxComponent>(m, "XrThumbstickLocomotionComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<XrThumbstickLocomotionComponent>(self);
        })
        .def_rw("input_device_id", &XrThumbstickLocomotionComponent::input_device_id)
        .def_prop_rw("move_hand",
            &XrThumbstickLocomotionComponent::get_move_hand_str,
            &XrThumbstickLocomotionComponent::set_move_hand_str)
        .def_prop_rw("move_frame",
            &XrThumbstickLocomotionComponent::get_move_frame_str,
            &XrThumbstickLocomotionComponent::set_move_frame_str)
        .def_rw("move_speed", &XrThumbstickLocomotionComponent::move_speed)
        .def_rw("speed_multiplier", &XrThumbstickLocomotionComponent::speed_multiplier)
        .def_rw("deadzone", &XrThumbstickLocomotionComponent::deadzone)
        .def_rw("normalize_diagonal", &XrThumbstickLocomotionComponent::normalize_diagonal)
        .def_rw("scale_after_deadzone", &XrThumbstickLocomotionComponent::scale_after_deadzone)
        .def_rw("invert_x", &XrThumbstickLocomotionComponent::invert_x)
        .def_rw("invert_y", &XrThumbstickLocomotionComponent::invert_y)
        .def_rw("continuous_turn_enabled", &XrThumbstickLocomotionComponent::continuous_turn_enabled)
        .def_prop_rw("turn_hand",
            &XrThumbstickLocomotionComponent::get_turn_hand_str,
            &XrThumbstickLocomotionComponent::set_turn_hand_str)
        .def_rw("turn_speed_degrees", &XrThumbstickLocomotionComponent::turn_speed_degrees)
        .def_rw("turn_deadzone", &XrThumbstickLocomotionComponent::turn_deadzone)
        .def("c_component_ptr", [](XrThumbstickLocomotionComponent& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(c.c_component());
        })
        .def("_cxx_component_ptr", [](XrThumbstickLocomotionComponent& c) -> uintptr_t {
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

            return nb::cast(static_cast<XrThumbstickLocomotionComponent*>(cxx), nb::rv_policy::reference);
        })
        .def_static("_from_cxx_component_ptr", [](uintptr_t ptr) -> nb::object {
            if (ptr == 0) {
                return nb::none();
            }
            auto* cxx = reinterpret_cast<XrThumbstickLocomotionComponent*>(ptr);
            return nb::cast(cxx, nb::rv_policy::reference);
        });

    nb::class_<MeshRenderer, Component>(m, "MeshRenderer")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<MeshRenderer>(self);
        })
        .def("__init__", [](nb::handle self, nb::object material_arg, bool cast_shadow) {
            cxx_component_init<MeshRenderer>(self);
            auto* cpp = nb::inst_ptr<MeshRenderer>(self);
            cpp->cast_shadow = cast_shadow;

            if (!material_arg.is_none()) {
                if (nb::isinstance<TcMaterial>(material_arg)) {
                    cpp->material = nb::cast<TcMaterial>(material_arg);
                } else if (nb::isinstance<nb::str>(material_arg)) {
                    cpp->set_material_by_name(nb::cast<std::string>(material_arg));
                }
            }
        }, nb::arg("material") = nb::none(), nb::arg("cast_shadow") = true)
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
        .def("get_material", &MeshRenderer::get_material)
        .def("get_base_material", &MeshRenderer::get_base_material)
        .def_prop_ro("material_slot_count", &MeshRenderer::material_slot_count)
        .def_prop_ro("materials", [](MeshRenderer& self) {
            return self.materials;
        })
        .def("get_material_for_slot", &MeshRenderer::get_material_for_slot, nb::arg("slot"))
        .def("get_material_for_submesh", &MeshRenderer::get_material_for_submesh, nb::arg("submesh_index"))
        .def("set_material_slot", &MeshRenderer::set_material_slot, nb::arg("slot"), nb::arg("material"))
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
        });

    nb::class_<SkinnedMeshRenderer, MeshRenderer>(m, "SkinnedMeshRenderer")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<SkinnedMeshRenderer>(self);
        })
        .def("__init__", [](nb::handle self,
                            nb::object material_arg,
                            SkeletonController* skeleton_controller,
                            bool cast_shadow) {
            cxx_component_init<SkinnedMeshRenderer>(self);
            auto* cpp = nb::inst_ptr<SkinnedMeshRenderer>(self);
            cpp->cast_shadow = cast_shadow;

            if (!material_arg.is_none()) {
                if (nb::isinstance<TcMaterial>(material_arg)) {
                    cpp->material = nb::cast<TcMaterial>(material_arg);
                } else if (nb::isinstance<nb::str>(material_arg)) {
                    cpp->set_material_by_name(nb::cast<std::string>(material_arg));
                }
            }

            if (skeleton_controller != nullptr) {
                cpp->set_skeleton_controller(skeleton_controller);
            }
        },
            nb::arg("material") = nb::none(),
            nb::arg("skeleton_controller") = nullptr,
            nb::arg("cast_shadow") = true)
        .def_rw("_skeleton_controller", &SkinnedMeshRenderer::_skeleton_controller)
        .def_prop_rw("skeleton_controller",
            &SkinnedMeshRenderer::skeleton_controller,
            &SkinnedMeshRenderer::set_skeleton_controller,
            nb::rv_policy::reference)
        .def_prop_ro("skeleton_instance",
            &SkinnedMeshRenderer::skeleton_instance,
            nb::rv_policy::reference)
        .def("update_bone_matrices", &SkinnedMeshRenderer::update_bone_matrices)
        .def_ro("_bone_count", &SkinnedMeshRenderer::_bone_count)
        .def("get_bone_matrices_flat", [](SkinnedMeshRenderer& self) {
            if (self._bone_count == 0) {
                size_t shape[3] = {0, 4, 4};
                return nb::ndarray<nb::numpy, float>(nullptr, 3, shape);
            }

            size_t data_size = self._bone_count * 16;
            float* buf = new float[data_size];
            std::copy(self._bone_matrices_flat.data(),
                      self._bone_matrices_flat.data() + data_size,
                      buf);
            nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            size_t shape[3] = {static_cast<size_t>(self._bone_count), 4, 4};
            return nb::ndarray<nb::numpy, float>(buf, 3, shape, owner);
        });

    nb::enum_<LineRenderMode>(m, "LineRenderMode")
        .value("WorldBillboard", LineRenderMode::WorldBillboard)
        .value("ScreenSpace", LineRenderMode::ScreenSpace)
        .value("WorldMesh", LineRenderMode::WorldMesh)
        .value("RawLines", LineRenderMode::RawLines)
        .value("WorldTube", LineRenderMode::WorldTube)
        .export_values();

    nb::class_<LineRenderer, Component>(m, "LineRenderer")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<LineRenderer>(self);
        })
        .def("__init__", [](nb::handle self,
                            const std::vector<Vec3>& points,
                            float width,
                            bool raw_lines,
                            nb::object material_arg,
                            LineRenderMode render_mode,
                            bool cast_shadow,
                            int tube_sides) {
            cxx_component_init<LineRenderer>(self);
            auto* cpp = nb::inst_ptr<LineRenderer>(self);
            cpp->set_points(tc_vec3_list_from_vec3_list(points));
            cpp->set_width(width);
            cpp->set_render_mode(render_mode);
            cpp->set_raw_lines(raw_lines);
            cpp->set_cast_shadow(cast_shadow);
            cpp->set_tube_sides(tube_sides);
            if (!material_arg.is_none()) {
                if (nb::isinstance<TcMaterial>(material_arg)) {
                    cpp->set_material(nb::cast<TcMaterial>(material_arg));
                } else if (nb::isinstance<nb::str>(material_arg)) {
                    cpp->set_material_by_name(nb::cast<std::string>(material_arg));
                }
            }
        },
        nb::arg("points") = std::vector<Vec3>{},
        nb::arg("width") = 0.1f,
        nb::arg("raw_lines") = false,
        nb::arg("material") = nb::none(),
        nb::arg("render_mode") = LineRenderMode::WorldBillboard,
        nb::arg("cast_shadow") = false,
        nb::arg("tube_sides") = 6)
        .def_prop_rw("points",
            [](LineRenderer& self) { return tc_vec3_list_to_python(self.points()); },
            [](LineRenderer& self, const std::vector<Vec3>& value) {
                self.set_points(tc_vec3_list_from_vec3_list(value));
            })
        .def_prop_rw("width", [](LineRenderer& self) { return self.width; }, &LineRenderer::set_width)
        .def_prop_rw("render_mode",
            [](LineRenderer& self) { return self.render_mode; },
            &LineRenderer::set_render_mode)
        .def_prop_rw("raw_lines", [](LineRenderer& self) { return self.raw_lines; }, &LineRenderer::set_raw_lines)
        .def_prop_rw("cast_shadow", [](LineRenderer& self) { return self.cast_shadow; }, &LineRenderer::set_cast_shadow)
        .def_prop_rw("material",
            [](LineRenderer& self) -> TcMaterial& { return self.material; },
            [](LineRenderer& self, const TcMaterial& value) { self.set_material(value); },
            nb::rv_policy::reference_internal)
        .def_prop_rw("up_hint",
            [](LineRenderer& self) {
                return Vec3{self.up_hint.x, self.up_hint.y, self.up_hint.z};
            },
            [](LineRenderer& self, const Vec3& value) {
                self.set_up_hint(tc_vec3_from_vec3(value));
            })
        .def_prop_rw("tube_sides", [](LineRenderer& self) { return self.tube_sides; }, &LineRenderer::set_tube_sides)
        .def_prop_ro("is_drawable", [](LineRenderer&) { return true; })
        .def("set_points", [](LineRenderer& self, const std::vector<Vec3>& value) {
            self.set_points(tc_vec3_list_from_vec3_list(value));
        })
        .def("clear_points", &LineRenderer::clear_points)
        .def("add_point", [](LineRenderer& self, const Vec3& value) {
            self.add_point(tc_vec3_from_vec3(value));
        })
        .def("set_width", &LineRenderer::set_width)
        .def("set_render_mode", &LineRenderer::set_render_mode)
        .def("set_raw_lines", &LineRenderer::set_raw_lines)
        .def("set_cast_shadow", &LineRenderer::set_cast_shadow)
        .def("set_tube_sides", &LineRenderer::set_tube_sides)
        .def("set_material", &LineRenderer::set_material)
        .def("set_material_by_name", &LineRenderer::set_material_by_name)
        .def("get_material", [](LineRenderer& self) { return self.material; })
        .def("get_mesh", &LineRenderer::get_mesh)
        .def("_get_mesh", &LineRenderer::get_mesh)
        .def_prop_ro("phase_marks", [](LineRenderer& self) {
            nb::set marks;
            for (const auto& mark : self.phase_marks()) {
                marks.add(nb::str(mark.c_str()));
            }
            return marks;
        });

    nb::enum_<WorldTextAnchor>(m, "WorldTextAnchor")
        .value("Left", WorldTextAnchor::Left)
        .value("Center", WorldTextAnchor::Center)
        .value("Right", WorldTextAnchor::Right)
        .export_values();

    nb::enum_<WorldTextOrientation>(m, "WorldTextOrientation")
        .value("Billboard", WorldTextOrientation::Billboard)
        .value("Fixed", WorldTextOrientation::Fixed)
        .export_values();

    nb::class_<WorldTextComponent, Component>(m, "WorldTextComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<WorldTextComponent>(self);
        })
        .def("__init__", [](nb::handle self,
                            const std::string& text,
                            float size,
                            std::optional<Vec4> color,
                            WorldTextAnchor anchor,
                            WorldTextOrientation orientation,
                            const std::string& phase_mark,
                            const std::string& font_path) {
            cxx_component_init<WorldTextComponent>(self);
            auto* cpp = nb::inst_ptr<WorldTextComponent>(self);
            cpp->set_text(text);
            cpp->set_size(size);
            cpp->set_anchor(anchor);
            cpp->set_orientation(orientation);
            cpp->set_phase_mark(phase_mark);
            cpp->set_font_path(font_path);
            if (color.has_value()) {
                cpp->set_color(*color);
            }
        },
        nb::arg("text") = "",
        nb::arg("size") = 0.35f,
        nb::arg("color") = nb::none(),
        nb::arg("anchor") = WorldTextAnchor::Center,
        nb::arg("orientation") = WorldTextOrientation::Billboard,
        nb::arg("phase_mark") = "transparent",
        nb::arg("font_path") = "")
        .def_prop_rw("text", [](WorldTextComponent& self) { return self.text; }, &WorldTextComponent::set_text)
        .def_prop_rw("font_path", [](WorldTextComponent& self) { return self.font_path; }, &WorldTextComponent::set_font_path)
        .def_prop_rw("phase_mark", [](WorldTextComponent& self) { return self.phase_mark; }, &WorldTextComponent::set_phase_mark)
        .def_prop_rw("local_offset",
            [](WorldTextComponent& self) {
                return self.local_offset;
            },
            [](WorldTextComponent& self, const Vec3& value) {
                self.set_local_offset(value);
            })
        .def_prop_rw("plane_normal",
            [](WorldTextComponent& self) {
                return self.plane_normal;
            },
            [](WorldTextComponent& self, const Vec3& value) {
                self.set_plane_normal(value);
            })
        .def_prop_rw("text_up",
            [](WorldTextComponent& self) {
                return self.text_up;
            },
            [](WorldTextComponent& self, const Vec3& value) {
                self.set_text_up(value);
            })
        .def_prop_rw("color",
            [](WorldTextComponent& self) {
                return self.color;
            },
            [](WorldTextComponent& self, const Vec4& value) {
                self.set_color(value);
            })
        .def_prop_rw("size", [](WorldTextComponent& self) { return self.size; }, &WorldTextComponent::set_size)
        .def_prop_rw("anchor", [](WorldTextComponent& self) { return self.anchor; }, &WorldTextComponent::set_anchor)
        .def_prop_rw("anchor_name", &WorldTextComponent::anchor_name, &WorldTextComponent::set_anchor_name)
        .def_prop_rw("orientation",
            [](WorldTextComponent& self) { return self.orientation; },
            &WorldTextComponent::set_orientation)
        .def_prop_rw("orientation_name",
            &WorldTextComponent::orientation_name,
            &WorldTextComponent::set_orientation_name)
        .def_prop_rw("priority", [](WorldTextComponent& self) { return self.priority; }, &WorldTextComponent::set_priority)
        .def_prop_rw("depth_test", [](WorldTextComponent& self) { return self.depth_test; }, &WorldTextComponent::set_depth_test)
        .def_prop_rw("depth_write", [](WorldTextComponent& self) { return self.depth_write; }, &WorldTextComponent::set_depth_write)
        .def_prop_rw("blend", [](WorldTextComponent& self) { return self.blend; }, &WorldTextComponent::set_blend)
        .def_prop_rw("cull", [](WorldTextComponent& self) { return self.cull; }, &WorldTextComponent::set_cull)
        .def_prop_ro("is_drawable", [](WorldTextComponent&) { return true; })
        .def_prop_ro("phase_marks", [](WorldTextComponent& self) {
            nb::set marks;
            for (const auto& mark : self.phase_marks()) {
                marks.add(nb::str(mark.c_str()));
            }
            return marks;
        });

    nb::class_<LightComponent, CxxComponent>(m, "LightComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<LightComponent>(self);
        })
        .def_prop_rw("light_type",
            &LightComponent::get_light_type_str,
            &LightComponent::set_light_type_str)
        .def_prop_rw("color",
            [](const LightComponent& c) { return c.color; },
            [](LightComponent& c, const Vec3& v) {
                c.color = v;
            })
        .def_rw("intensity", &LightComponent::intensity)
        .def_prop_rw("shadows_enabled",
            &LightComponent::get_shadows_enabled,
            &LightComponent::set_shadows_enabled)
        .def_prop_rw("shadows_bias",
            &LightComponent::get_shadows_bias,
            &LightComponent::set_shadows_bias)
        .def_prop_rw("shadows_normal_bias",
            &LightComponent::get_shadows_normal_bias,
            &LightComponent::set_shadows_normal_bias)
        .def_prop_rw("shadows_map_resolution",
            &LightComponent::get_shadows_map_resolution,
            &LightComponent::set_shadows_map_resolution)
        .def_prop_rw("cascade_count",
            &LightComponent::get_cascade_count,
            &LightComponent::set_cascade_count)
        .def_prop_rw("max_distance",
            &LightComponent::get_max_distance,
            &LightComponent::set_max_distance)
        .def_prop_rw("split_lambda",
            &LightComponent::get_split_lambda,
            &LightComponent::set_split_lambda)
        .def_prop_rw("cascade_blend",
            &LightComponent::get_cascade_blend,
            &LightComponent::set_cascade_blend)
        .def_rw("shadows", &LightComponent::shadows)
        .def("to_light", &LightComponent::to_light)
        .def("c_component_ptr", [](LightComponent& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(c.c_component());
        });

    nb::class_<DepthPass, CxxFramePass>(m, "DepthPass")
        .def("__init__", [](DepthPass* self, const std::string& input_res, const std::string& output_res, const std::string& pass_name) {
            new (self) DepthPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "DepthPass");
        }, nb::arg("input_res") = "empty_depth", nb::arg("output_res") = "depth", nb::arg("pass_name") = "Depth")
        .def_rw("input_res", &DepthPass::input_res)
        .def_rw("output_res", &DepthPass::output_res)
        .def_rw("camera_name", &DepthPass::camera_name)
        .def_prop_rw("phase_mark",
            [](DepthPass& self) { return self.pass_phase_mark; },
            [](DepthPass& self, const std::string& value) { self.pass_phase_mark = value; })
        .def_rw("depth_encoding", &DepthPass::depth_encoding)
        .def_rw("clear", &DepthPass::clear)
        .def("get_internal_symbols", &DepthPass::get_internal_symbols)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            (void)resource_manager;
            std::string pass_name = "Depth";
            std::string camera_name;
            std::string input_res = "empty_depth";
            std::string output_res = "depth";
            std::string phase_mark = "depth";
            std::string depth_encoding = "linear";
            bool clear = true;
            if (data.contains("pass_name")) pass_name = nb::cast<std::string>(data["pass_name"]);
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("camera_name")) camera_name = nb::cast<std::string>(d["camera_name"]);
                if (d.contains("input_res")) input_res = nb::cast<std::string>(d["input_res"]);
                if (d.contains("output_res")) output_res = nb::cast<std::string>(d["output_res"]);
                if (d.contains("phase_mark")) phase_mark = nb::cast<std::string>(d["phase_mark"]);
                else if (d.contains("material_phase_mark")) phase_mark = nb::cast<std::string>(d["material_phase_mark"]);
                if (d.contains("depth_encoding")) depth_encoding = nb::cast<std::string>(d["depth_encoding"]);
                if (d.contains("clear")) clear = nb::cast<bool>(d["clear"]);
            }
            auto* p = new DepthPass(input_res, output_res, pass_name);
            p->camera_name = camera_name;
            p->pass_phase_mark = phase_mark;
            p->depth_encoding = depth_encoding;
            p->clear = clear;
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

    nb::class_<DepthOnlyPass, CxxFramePass>(m, "DepthOnlyPass")
        .def("__init__", [](DepthOnlyPass* self, const std::string& output_res, const std::string& pass_name) {
            new (self) DepthOnlyPass(output_res, pass_name);
            init_pass_from_python(self, "DepthOnlyPass");
        }, nb::arg("output_res") = "depth_texture", nb::arg("pass_name") = "DepthOnly")
        .def_rw("output_res", &DepthOnlyPass::output_res)
        .def_rw("output_res_target", &DepthOnlyPass::output_res_target)
        .def_rw("camera_name", &DepthOnlyPass::camera_name)
        .def_prop_rw("phase_mark",
            [](DepthOnlyPass& self) { return self.pass_phase_mark; },
            [](DepthOnlyPass& self, const std::string& value) { self.pass_phase_mark = value; })
        .def("get_internal_symbols", &DepthOnlyPass::get_internal_symbols)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            (void)resource_manager;
            std::string pass_name = "DepthOnly";
            std::string camera_name;
            std::string output_res = "depth_texture";
            std::string output_res_target;
            std::string phase_mark = "depth";
            if (data.contains("pass_name")) pass_name = nb::cast<std::string>(data["pass_name"]);
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("camera_name")) camera_name = nb::cast<std::string>(d["camera_name"]);
                if (d.contains("output_res")) output_res = nb::cast<std::string>(d["output_res"]);
                if (d.contains("output_res_target")) output_res_target = nb::cast<std::string>(d["output_res_target"]);
                if (d.contains("phase_mark")) phase_mark = nb::cast<std::string>(d["phase_mark"]);
                else if (d.contains("material_phase_mark")) phase_mark = nb::cast<std::string>(d["material_phase_mark"]);
            }
            auto* p = new DepthOnlyPass(output_res, pass_name);
            p->camera_name = camera_name;
            p->output_res_target = output_res_target;
            p->pass_phase_mark = phase_mark;
            return init_pass_from_deserialize(p, "DepthOnlyPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &DepthOnlyPass::compute_reads)
        .def_prop_ro("writes", &DepthOnlyPass::compute_writes)
        .def("destroy", &DepthOnlyPass::destroy);

    {
        nb::dict visibility;
        nb::dict camera_cond;
        camera_cond["_outside_viewport"] = true;
        visibility["camera_name"] = camera_cond;
        m.attr("DepthOnlyPass").attr("node_param_visibility") = visibility;
        m.attr("DepthOnlyPass").attr("category") = "Render";
        m.attr("DepthOnlyPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("output_res_target", "depth_texture"));
        m.attr("DepthOnlyPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "depth_texture"));
        m.attr("DepthOnlyPass").attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("output_res_target", "output_res"));
    }

    nb::class_<DepthToColorPass, CxxFramePass>(m, "DepthToColorPass")
        .def("__init__", [](DepthToColorPass* self, const std::string& input_res, const std::string& output_res, const std::string& pass_name) {
            new (self) DepthToColorPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "DepthToColorPass");
        }, nb::arg("input_res") = "depth_texture", nb::arg("output_res") = "depth_color", nb::arg("pass_name") = "DepthToColor")
        .def_rw("input_res", &DepthToColorPass::input_res)
        .def_rw("output_res", &DepthToColorPass::output_res)
        .def_rw("output_res_target", &DepthToColorPass::output_res_target)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            (void)resource_manager;
            std::string pass_name = "DepthToColor";
            std::string input_res = "depth_texture";
            std::string output_res = "depth_color";
            std::string output_res_target;
            if (data.contains("pass_name")) pass_name = nb::cast<std::string>(data["pass_name"]);
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("input_res")) input_res = nb::cast<std::string>(d["input_res"]);
                if (d.contains("output_res")) output_res = nb::cast<std::string>(d["output_res"]);
                if (d.contains("output_res_target")) output_res_target = nb::cast<std::string>(d["output_res_target"]);
            }
            auto* p = new DepthToColorPass(input_res, output_res, pass_name);
            p->output_res_target = output_res_target;
            return init_pass_from_deserialize(p, "DepthToColorPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &DepthToColorPass::compute_reads)
        .def_prop_ro("writes", &DepthToColorPass::compute_writes)
        .def("destroy", &DepthToColorPass::destroy);

    {
        m.attr("DepthToColorPass").attr("category") = "Render";
        m.attr("DepthToColorPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "depth_texture"), nb::make_tuple("output_res_target", "color_texture"));
        m.attr("DepthToColorPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "color_texture"));
        m.attr("DepthToColorPass").attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("output_res_target", "output_res"));
    }

    nb::class_<ColorToDepthPass, CxxFramePass>(m, "ColorToDepthPass")
        .def("__init__", [](ColorToDepthPass* self, const std::string& input_res, const std::string& output_res, const std::string& pass_name) {
            new (self) ColorToDepthPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "ColorToDepthPass");
        }, nb::arg("input_res") = "color_texture", nb::arg("output_res") = "depth_texture", nb::arg("pass_name") = "ColorToDepth")
        .def_rw("input_res", &ColorToDepthPass::input_res)
        .def_rw("output_res", &ColorToDepthPass::output_res)
        .def_rw("output_res_target", &ColorToDepthPass::output_res_target)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            (void)resource_manager;
            std::string pass_name = "ColorToDepth";
            std::string input_res = "color_texture";
            std::string output_res = "depth_texture";
            std::string output_res_target;
            if (data.contains("pass_name")) pass_name = nb::cast<std::string>(data["pass_name"]);
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("input_res")) input_res = nb::cast<std::string>(d["input_res"]);
                if (d.contains("output_res")) output_res = nb::cast<std::string>(d["output_res"]);
                if (d.contains("output_res_target")) output_res_target = nb::cast<std::string>(d["output_res_target"]);
            }
            auto* p = new ColorToDepthPass(input_res, output_res, pass_name);
            p->output_res_target = output_res_target;
            return init_pass_from_deserialize(p, "ColorToDepthPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &ColorToDepthPass::compute_reads)
        .def_prop_ro("writes", &ColorToDepthPass::compute_writes)
        .def("destroy", &ColorToDepthPass::destroy);

    {
        m.attr("ColorToDepthPass").attr("category") = "Render";
        m.attr("ColorToDepthPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "color_texture"), nb::make_tuple("output_res_target", "depth_texture"));
        m.attr("ColorToDepthPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "depth_texture"));
        m.attr("ColorToDepthPass").attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("output_res_target", "output_res"));
    }

    nb::class_<NormalPass, CxxFramePass>(m, "NormalPass")
        .def("__init__", [](NormalPass* self, const std::string& input_res, const std::string& output_res, const std::string& pass_name) {
            new (self) NormalPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "NormalPass");
        }, nb::arg("input_res") = "empty_normal", nb::arg("output_res") = "normal", nb::arg("pass_name") = "Normal")
        .def_rw("input_res", &NormalPass::input_res)
        .def_rw("output_res", &NormalPass::output_res)
        .def_rw("camera_name", &NormalPass::camera_name)
        .def_prop_rw("phase_mark",
            [](NormalPass& self) { return self.pass_phase_mark; },
            [](NormalPass& self, const std::string& value) { self.pass_phase_mark = value; })
        .def("get_resource_specs", &NormalPass::get_resource_specs)
        .def("get_internal_symbols", &NormalPass::get_internal_symbols)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            (void)resource_manager;
            std::string pass_name = "Normal";
            std::string camera_name;
            std::string input_res = "empty_normal";
            std::string output_res = "normal";
            std::string phase_mark = "normal";
            if (data.contains("pass_name")) pass_name = nb::cast<std::string>(data["pass_name"]);
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("camera_name")) camera_name = nb::cast<std::string>(d["camera_name"]);
                if (d.contains("input_res")) input_res = nb::cast<std::string>(d["input_res"]);
                if (d.contains("output_res")) output_res = nb::cast<std::string>(d["output_res"]);
                if (d.contains("phase_mark")) phase_mark = nb::cast<std::string>(d["phase_mark"]);
                else if (d.contains("material_phase_mark")) phase_mark = nb::cast<std::string>(d["material_phase_mark"]);
            }
            auto* p = new NormalPass(input_res, output_res, pass_name);
            p->camera_name = camera_name;
            p->pass_phase_mark = phase_mark;
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
        .def("__init__", [](MaterialPass* self, const std::string& output_res, nb::object material, const std::string& pass_name) {
            new (self) MaterialPass();
            self->output_res = output_res;
            self->set_pass_name(pass_name);
            set_material_from_python(*self, material);
            init_pass_from_python(self, "MaterialPass");
        }, nb::arg("output_res") = "output", nb::arg("material") = nb::none(), nb::arg("pass_name") = "MaterialPass")
        .def_rw("output_res", &MaterialPass::output_res)
        .def_rw("output_res_target", &MaterialPass::output_res_target)
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
        .def("execute_with_data", [](MaterialPass& self, nb::tuple rect_py) {
            ExecuteContext ctx;
            ctx.render_rect = tuple_to_rect(rect_py);
            self.execute(ctx);
        }, nb::arg("rect"))
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            (void)resource_manager;
            std::string pass_name = "MaterialPass";
            std::string output_res = "output";
            std::string output_res_target;
            nb::object material = nb::none();
            if (data.contains("pass_name")) pass_name = nb::cast<std::string>(data["pass_name"]);
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("output_res")) output_res = nb::cast<std::string>(d["output_res"]);
                if (d.contains("output_res_target")) output_res_target = nb::cast<std::string>(d["output_res_target"]);
                if (d.contains("material")) material = nb::borrow<nb::object>(d["material"]);
            }
            auto* p = new MaterialPass();
            p->output_res = output_res;
            p->output_res_target = output_res_target;
            p->set_pass_name(pass_name);
            set_material_from_python(*p, material);
            return init_pass_from_deserialize(p, "MaterialPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &MaterialPass::compute_reads)
        .def_prop_ro("writes", &MaterialPass::compute_writes)
        .def("get_inplace_aliases", &MaterialPass::get_inplace_aliases)
        .def("destroy", &MaterialPass::destroy);

    {
        m.attr("MaterialPass").attr("category") = "Render";
        m.attr("MaterialPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("output_res_target", "fbo")
        );
        m.attr("MaterialPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("MaterialPass").attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("output_res_target", "output_res"));
        m.attr("MaterialPass").attr("has_dynamic_inputs") = true;
    }
}
