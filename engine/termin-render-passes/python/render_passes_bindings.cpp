#include <nanobind/make_iterator.h>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/array.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/set.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/vector.h>

extern "C" {
#include "render/tc_pass.h"
#include "tc_picking.h"
}

#include <termin/lighting/environment_lighting.hpp>
#include <termin/render/bloom_pass.hpp>
#include <termin/render/color_pass.hpp>
#include <termin/render/debug_geometry_pass.hpp>
#include <termin/render/debug_triangle_pass.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/grayscale_pass.hpp>
#include <termin/render/id_pass.hpp>
#include <termin/render/present_pass.hpp>
#include <termin/render/resolve_pass.hpp>
#include <termin/render/shadow_camera.hpp>
#include <termin/render/shadow_pass.hpp>
#include <termin/render/skybox_pass.hpp>
#include <termin/render/standard_gbuffer_pass.hpp>
#include <termin/render/tonemap_pass.hpp>
#include <termin/render/ui_widget_pass.hpp>
#include <termin/render/world2d_pass.hpp>

namespace nb = nanobind;

namespace termin {
    namespace {

        template <typename T> void init_pass_from_python(T* self, const char* type_name) {
            self->link_to_type_registry(type_name);
            nb::object wrapper = nb::cast(self, nb::rv_policy::reference);
            self->set_language_body(wrapper.ptr(), TC_LANGUAGE_PYTHON);
        }

        using Matrix4dView = nb::ndarray<double, nb::shape<4, 4>, nb::c_contig, nb::device::cpu>;

        Mat44 mat44_from_numpy(const Matrix4dView& values) {
            Mat44 result;
            for (int row = 0; row < 4; ++row) {
                for (int column = 0; column < 4; ++column) {
                    result(column, row) = values(row, column);
                }
            }
            return result;
        }

    } // namespace

    void bind_shadow_camera_helpers(nb::module_& m) {
        nb::class_<ShadowCameraParams>(m, "ShadowCameraParams")
            .def(nb::init<>())
            .def(
                "__init__",
                [](ShadowCameraParams* self,
                   const Vec3& light_direction,
                   std::optional<Bounds2f> ortho_bounds,
                   double ortho_size,
                   double near,
                   double far,
                   std::optional<Vec3> center) {
                    new (self) ShadowCameraParams(light_direction,
                                                  ortho_bounds,
                                                  static_cast<float>(ortho_size),
                                                  static_cast<float>(near),
                                                  static_cast<float>(far),
                                                  center.value_or(Vec3{0.0, 0.0, 0.0}));
                },
                nb::arg("light_direction"),
                nb::arg("ortho_bounds").none() = nb::none(),
                nb::arg("ortho_size") = 20.0,
                nb::arg("near") = 0.1,
                nb::arg("far") = 100.0,
                nb::arg("center").none() = nb::none())
            .def_prop_rw(
                "light_direction",
                [](const ShadowCameraParams& self) { return self.light_direction; },
                [](ShadowCameraParams& self, const Vec3& light_direction) {
                    self.light_direction = light_direction.normalized();
                })
            .def_prop_rw(
                "ortho_bounds",
                [](const ShadowCameraParams& self) { return self.ortho_bounds; },
                [](ShadowCameraParams& self, nb::object bounds) {
                    self.ortho_bounds =
                        bounds.is_none() ? std::nullopt : std::optional<Bounds2f>(nb::cast<Bounds2f>(bounds));
                },
                nb::arg().none())
            .def_rw("ortho_size", &ShadowCameraParams::ortho_size)
            .def_rw("near", &ShadowCameraParams::near)
            .def_rw("far", &ShadowCameraParams::far)
            .def_prop_rw(
                "center",
                [](const ShadowCameraParams& self) { return self.center; },
                [](ShadowCameraParams& self, const Vec3& center) { self.center = center; });

        m.def(
            "build_shadow_view_matrix",
            [](const ShadowCameraParams& params) {
                Mat44f mat = build_shadow_view_matrix(params);
                double* data = new double[16];
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        data[row * 4 + col] = static_cast<double>(mat.data[col * 4 + row]);
                    }
                }
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
                return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, {4, 4}, owner);
            },
            nb::arg("params"),
            "Build view matrix for shadow camera");

        m.def(
            "build_shadow_projection_matrix",
            [](const ShadowCameraParams& params) {
                Mat44f mat = build_shadow_projection_matrix(params);
                double* data = new double[16];
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        data[row * 4 + col] = static_cast<double>(mat.data[col * 4 + row]);
                    }
                }
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
                return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, {4, 4}, owner);
            },
            nb::arg("params"),
            "Build orthographic projection matrix for shadow camera");

        m.def(
            "compute_light_space_matrix",
            [](const ShadowCameraParams& params) {
                Mat44f mat = compute_light_space_matrix(params);
                double* data = new double[16];
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        data[row * 4 + col] = static_cast<double>(mat.data[col * 4 + row]);
                    }
                }
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
                return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, {4, 4}, owner);
            },
            nb::arg("params"),
            "Compute combined light space matrix (projection * view)");

        m.def(
            "compute_frustum_corners",
            [](Matrix4dView view, Matrix4dView proj) {
                const Mat44 view_mat = mat44_from_numpy(view);
                const Mat44 proj_mat = mat44_from_numpy(proj);

                const auto corners = compute_frustum_corners(view_mat, proj_mat);
                if (!corners.has_value()) {
                    throw nb::value_error("view-projection matrix cannot be inverted into finite frustum corners");
                }

                double* data = new double[24];
                for (int i = 0; i < 8; ++i) {
                    data[i * 3 + 0] = (*corners)[i].x;
                    data[i * 3 + 1] = (*corners)[i].y;
                    data[i * 3 + 2] = (*corners)[i].z;
                }
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
                return nb::ndarray<nb::numpy, double, nb::shape<8, 3>>(data, {8, 3}, owner);
            },
            nb::arg("view_matrix"),
            nb::arg("projection_matrix"),
            "Compute 8 corners of view frustum in world space");

        m.def(
            "fit_shadow_frustum_to_camera",
            [](Matrix4dView view,
               Matrix4dView proj,
               const Vec3& light_direction,
               double padding,
               int shadow_map_resolution,
               bool stabilize,
               double caster_offset) {
                const Mat44 view_mat = mat44_from_numpy(view);
                const Mat44 proj_mat = mat44_from_numpy(proj);

                const auto params = fit_shadow_frustum_to_camera(view_mat,
                                                                 proj_mat,
                                                                 light_direction,
                                                                 static_cast<float>(padding),
                                                                 shadow_map_resolution,
                                                                 stabilize,
                                                                 static_cast<float>(caster_offset));
                if (!params.has_value()) {
                    throw nb::value_error(
                        "shadow frustum cannot be fitted from the supplied matrices and parameters");
                }
                return *params;
            },
            nb::arg("view_matrix"),
            nb::arg("projection_matrix"),
            nb::arg("light_direction"),
            nb::arg("padding") = 1.0,
            nb::arg("shadow_map_resolution") = 1024,
            nb::arg("stabilize") = true,
            nb::arg("caster_offset") = 50.0,
            "Fit shadow camera to view frustum");
    }

    void bind_render_passes(nb::module_& m) {
        bind_shadow_camera_helpers(m);

        nb::class_<DebugTrianglePass, CxxFramePass>(m, "DebugTrianglePass")
            .def(
                "__init__",
                [](DebugTrianglePass* self, const std::string& output_res, const std::string& pass_name) {
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
            .def("__repr__",
                 [](const DebugTrianglePass& p) { return "<DebugTrianglePass '" + p.get_pass_name() + "'>"; });

        m.attr("DebugTrianglePass").attr("category") = "Debug";
        m.attr("DebugTrianglePass").attr("node_inputs") = nb::make_tuple();
        m.attr("DebugTrianglePass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));

        nb::class_<DebugGeometryPass, CxxFramePass>(m, "DebugGeometryPass")
            .def(
                "__init__",
                [](DebugGeometryPass* self,
                   const std::string& input_res,
                   const std::string& output_res,
                   const std::string& pass_name) {
                    new (self) DebugGeometryPass(input_res, output_res, pass_name);
                    init_pass_from_python(self, "DebugGeometryPass");
                },
                nb::arg("input_res") = "color",
                nb::arg("output_res") = "color",
                nb::arg("pass_name") = "DebugGeometry")
            .def_rw("input_res", &DebugGeometryPass::input_res)
            .def_rw("output_res", &DebugGeometryPass::output_res)
            .def("compute_reads", &DebugGeometryPass::compute_reads)
            .def("compute_writes", &DebugGeometryPass::compute_writes)
            .def("get_inplace_aliases", &DebugGeometryPass::get_inplace_aliases)
            .def_prop_ro("reads", &DebugGeometryPass::compute_reads)
            .def_prop_ro("writes", &DebugGeometryPass::compute_writes)
            .def("destroy", &DebugGeometryPass::destroy);

        m.attr("DebugGeometryPass").attr("category") = "Debug";
        m.attr("DebugGeometryPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        m.attr("DebugGeometryPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("DebugGeometryPass").attr("node_inplace_pairs") =
            nb::make_tuple(nb::make_tuple("input_res", "output_res"));

        nb::class_<PresentToScreenPass, CxxFramePass>(m, "PresentToScreenPass")
            .def(
                "__init__",
                [](PresentToScreenPass* self,
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

        m.attr("PresentToScreenPass").attr("category") = "Output";
        m.attr("PresentToScreenPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        m.attr("PresentToScreenPass").attr("node_outputs") = nb::make_tuple();

        nb::class_<BlitPass, CxxFramePass>(m, "BlitPass")
            .def(
                "__init__",
                [](BlitPass* self,
                   const std::string& input_res,
                   const std::string& output_res,
                   const std::string& pass_name) {
                    new (self) BlitPass(input_res, output_res, pass_name);
                    init_pass_from_python(self, "BlitPass");
                },
                nb::arg("input_res") = "color",
                nb::arg("output_res") = "blit",
                nb::arg("pass_name") = "Blit")
            .def_rw("input_res", &BlitPass::input_res)
            .def_rw("output_res", &BlitPass::output_res)
            .def_rw("output_res_target", &BlitPass::output_res_target)
            .def("compute_reads", &BlitPass::compute_reads)
            .def("compute_writes", &BlitPass::compute_writes)
            .def("get_inplace_aliases", &BlitPass::get_inplace_aliases)
            .def_prop_ro("reads", &BlitPass::compute_reads)
            .def_prop_ro("writes", &BlitPass::compute_writes)
            .def("destroy", &BlitPass::destroy);

        m.attr("BlitPass").attr("category") = "Output";
        m.attr("BlitPass").attr("node_inputs") =
            nb::make_tuple(nb::make_tuple("input_res", "fbo"), nb::make_tuple("output_res_target", "fbo"));
        m.attr("BlitPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("BlitPass").attr("node_inplace_pairs") =
            nb::make_tuple(nb::make_tuple("output_res_target", "output_res"));

        nb::class_<ResolvePass, CxxFramePass>(m, "ResolvePass")
            .def(
                "__init__",
                [](ResolvePass* self,
                   const std::string& input_res,
                   const std::string& output_res,
                   const std::string& pass_name) {
                    new (self) ResolvePass(input_res, output_res);
                    if (!pass_name.empty()) {
                        self->set_pass_name(pass_name);
                    }
                    init_pass_from_python(self, "ResolvePass");
                },
                nb::arg("input_res") = "color",
                nb::arg("output_res") = "resolved",
                nb::arg("pass_name") = "Resolve")
            .def_rw("input_res", &ResolvePass::input_res)
            .def_rw("output_res", &ResolvePass::output_res)
            .def_rw("output_res_target", &ResolvePass::output_res_target)
            .def("compute_reads", &ResolvePass::compute_reads)
            .def("compute_writes", &ResolvePass::compute_writes)
            .def("get_inplace_aliases", &ResolvePass::get_inplace_aliases)
            .def_prop_ro("reads", &ResolvePass::compute_reads)
            .def_prop_ro("writes", &ResolvePass::compute_writes)
            .def("destroy", &ResolvePass::destroy);

        m.attr("ResolvePass").attr("category") = "Output";
        m.attr("ResolvePass").attr("node_inputs") =
            nb::make_tuple(nb::make_tuple("input_res", "fbo"), nb::make_tuple("output_res_target", "fbo"));
        m.attr("ResolvePass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("ResolvePass").attr("node_inplace_pairs") =
            nb::make_tuple(nb::make_tuple("output_res_target", "output_res"));
        nb::class_<IdPass, CxxFramePass>(m, "IdPass")
            .def(
                "__init__",
                [](IdPass* self,
                   const std::string& input_res,
                   const std::string& output_res,
                   const std::string& pass_name) {
                    new (self) IdPass(input_res, output_res, pass_name);
                    init_pass_from_python(self, "IdPass");
                },
                nb::arg("input_res") = "empty",
                nb::arg("output_res") = "id",
                nb::arg("pass_name") = "IdPass")
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
            .def(
                "__getitem__",
                [](ShadowMapArrayResource& self, size_t index) -> ShadowMapArrayEntry& {
                    if (index >= self.size()) {
                        throw nb::index_error("ShadowMapArrayResource index out of range");
                    }
                    return self[index];
                },
                nb::rv_policy::reference)
            .def(
                "__iter__",
                [](ShadowMapArrayResource& self) {
                    return nb::make_iterator(nb::type<ShadowMapArrayResource>(), "iterator", self.begin(), self.end());
                },
                nb::keep_alive<0, 1>())
            .def("get_by_light_index", &ShadowMapArrayResource::get_by_light_index, nb::rv_policy::reference);

        nb::class_<EnvironmentLightingResource, FrameGraphResource>(m, "EnvironmentLightingResource")
            .def(nb::init<>())
            .def("resource_type", &EnvironmentLightingResource::resource_type)
            .def("ready", &EnvironmentLightingResource::ready)
            .def_ro("specular_mip_count", &EnvironmentLightingResource::specular_mip_count);

        auto environment_lighting_pass =
            nb::class_<EnvironmentLightingPass, CxxFramePass>(m, "EnvironmentLightingPass")
                .def(
                    "__init__",
                    [](EnvironmentLightingPass* self, std::string output_res, std::string pass_name) {
                        new (self) EnvironmentLightingPass(output_res, pass_name);
                        init_pass_from_python(self, "EnvironmentLightingPass");
                    },
                    nb::arg("output_res") = "environment_lighting",
                    nb::arg("pass_name") = "EnvironmentLighting")
                .def_rw("output_res", &EnvironmentLightingPass::output_res)
                .def_prop_ro("reads", &EnvironmentLightingPass::compute_reads)
                .def_prop_ro("writes", &EnvironmentLightingPass::compute_writes)
                .def("get_resource_specs", &EnvironmentLightingPass::get_resource_specs)
                .def("destroy", &EnvironmentLightingPass::destroy);
        environment_lighting_pass.attr("category") = "Lighting";
        environment_lighting_pass.attr("node_inputs") = nb::make_tuple();
        environment_lighting_pass.attr("node_outputs") =
            nb::make_tuple(nb::make_tuple("output_res", "environment_lighting"));

        auto color_pass = nb::class_<ColorPass, CxxFramePass>(m, "ColorPass")
                              .def(
                                  "__init__",
                                  [](ColorPass* self,
                                     std::string input_res,
                                     std::string output_res,
                                     nb::object shadow_res_obj,
                                     nb::object environment_res_obj,
                                     std::string phase_mark,
                                     std::string pass_name,
                                     std::string sort_mode,
                                     bool clear_depth,
                                     std::string camera_name,
                                     bool attachment_barrier_between_draws) {
                                      std::string shadow_res = "shadow_maps";
                                      if (!shadow_res_obj.is_none()) {
                                          shadow_res = nb::cast<std::string>(shadow_res_obj);
                                      } else {
                                          shadow_res = "";
                                      }
                                      ColorPassConfig config;
                                      config.input_res = std::move(input_res);
                                      config.output_res = std::move(output_res);
                                      config.shadow_res = std::move(shadow_res);
                                      config.environment_res = environment_res_obj.is_none()
                                                                   ? std::string{}
                                                                   : nb::cast<std::string>(environment_res_obj);
                                      config.phase_mark = std::move(phase_mark);
                                      config.pass_name = std::move(pass_name);
                                      config.sort_mode = std::move(sort_mode);
                                      config.clear_depth = clear_depth;
                                      config.camera_name = std::move(camera_name);
                                      config.attachment_barrier_between_draws = attachment_barrier_between_draws;
                                      new (self) ColorPass(config);
                                      init_pass_from_python(self, "ColorPass");
                                  },
                                  nb::arg("input_res") = "empty",
                                  nb::arg("output_res") = "color",
                                  nb::arg("shadow_res").none() = nb::none(),
                                  nb::arg("environment_res").none() = "environment_lighting",
                                  nb::arg("phase_mark") = "opaque",
                                  nb::arg("pass_name") = "Color",
                                  nb::arg("sort_mode") = "none",
                                  nb::arg("clear_depth") = false,
                                  nb::arg("camera_name") = "",
                                  nb::arg("attachment_barrier_between_draws") = false)
                              .def_rw("input_res", &ColorPass::input_res)
                              .def_rw("output_res", &ColorPass::output_res)
                              .def_rw("shadow_res", &ColorPass::shadow_res)
                              .def_rw("environment_res", &ColorPass::environment_res)
                              .def_rw("phase_mark", &ColorPass::phase_mark)
                              .def_rw("sort_mode", &ColorPass::sort_mode)
                              .def_rw("clear_depth", &ColorPass::clear_depth)
                              .def_rw("attachment_barrier_between_draws", &ColorPass::attachment_barrier_between_draws)
                              .def_rw("wireframe", &ColorPass::wireframe)
                              .def_rw("camera_name", &ColorPass::camera_name)
                              .def_rw("extra_textures", &ColorPass::extra_textures)
                              .def("add_extra_texture",
                                   &ColorPass::add_extra_texture,
                                   nb::arg("uniform_name"),
                                   nb::arg("resource_name"))
                              .def("set_graph_resource_input",
                                   &ColorPass::set_graph_resource_input,
                                   nb::arg("socket_name"),
                                   nb::arg("resource_name"))
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
        color_pass.attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"),
                                                        nb::make_tuple("shadow_res", "shadow"),
                                                        nb::make_tuple("environment_res", "environment_lighting"));
        color_pass.attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        color_pass.attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("input_res", "output_res"));
        {
            nb::dict visibility;
            nb::dict camera_cond;
            camera_cond["_outside_viewport"] = true;
            visibility["camera_name"] = camera_cond;
            color_pass.attr("node_param_visibility") = visibility;
        }

        auto standard_gbuffer_pass = nb::class_<StandardGBufferPass, CxxFramePass>(m, "StandardGBufferPass")
                                         .def(
                                             "__init__",
                                             [](StandardGBufferPass* self,
                                                std::string base_ao_res,
                                                std::string normal_rough_res,
                                                std::string metal_emit_res,
                                                std::string depth_res,
                                                std::string camera_name,
                                                std::string pass_name) {
                                                 StandardGBufferPassConfig config;
                                                 config.base_ao_res = std::move(base_ao_res);
                                                 config.normal_rough_res = std::move(normal_rough_res);
                                                 config.metal_emit_res = std::move(metal_emit_res);
                                                 config.depth_res = std::move(depth_res);
                                                 config.camera_name = std::move(camera_name);
                                                 config.pass_name = std::move(pass_name);
                                                 new (self) StandardGBufferPass(config);
                                                 init_pass_from_python(self, "StandardGBufferPass");
                                             },
                                             nb::arg("base_ao_res") = "gbuffer_base_ao",
                                             nb::arg("normal_rough_res") = "gbuffer_normal_rough",
                                             nb::arg("metal_emit_res") = "gbuffer_metal_emit",
                                             nb::arg("depth_res") = "scene_depth",
                                             nb::arg("camera_name") = "",
                                             nb::arg("pass_name") = "StandardGBuffer")
                                         .def_rw("base_ao_res", &StandardGBufferPass::base_ao_res)
                                         .def_rw("normal_rough_res", &StandardGBufferPass::normal_rough_res)
                                         .def_rw("metal_emit_res", &StandardGBufferPass::metal_emit_res)
                                         .def_rw("depth_res", &StandardGBufferPass::depth_res)
                                         .def_rw("camera_name", &StandardGBufferPass::camera_name)
                                         .def("compute_reads", &StandardGBufferPass::compute_reads)
                                         .def("compute_writes", &StandardGBufferPass::compute_writes)
                                         .def("get_resource_specs", &StandardGBufferPass::get_resource_specs)
                                         .def_prop_ro("reads", &StandardGBufferPass::compute_reads)
                                         .def_prop_ro("writes", &StandardGBufferPass::compute_writes);
        standard_gbuffer_pass.attr("category") = "Render";
        standard_gbuffer_pass.attr("node_inputs") = nb::make_tuple();
        standard_gbuffer_pass.attr("node_outputs") = nb::make_tuple(nb::make_tuple("base_ao_res", "color_texture"),
                                                                    nb::make_tuple("normal_rough_res", "color_texture"),
                                                                    nb::make_tuple("metal_emit_res", "color_texture"),
                                                                    nb::make_tuple("depth_res", "depth_texture"));
        {
            nb::dict visibility;
            nb::dict camera_cond;
            camera_cond["_outside_viewport"] = true;
            visibility["camera_name"] = camera_cond;
            standard_gbuffer_pass.attr("node_param_visibility") = visibility;
        }

        auto world2d_pass =
            nb::class_<World2DPass, CxxFramePass>(m, "World2DPass")
                .def(
                    "__init__",
                    [](World2DPass* self, std::string input_res, std::string output_res, std::string pass_name) {
                        new (self) World2DPass(input_res, output_res);
                        self->pass_name_set(pass_name);
                        init_pass_from_python(self, "World2DPass");
                    },
                    nb::arg("input_res") = "color",
                    nb::arg("output_res") = "color_world2d",
                    nb::arg("pass_name") = "World2D")
                .def_rw("input_res", &World2DPass::input_res)
                .def_rw("output_res", &World2DPass::output_res)
                .def_prop_ro("reads", &World2DPass::compute_reads)
                .def_prop_ro("writes", &World2DPass::compute_writes)
                .def("destroy", &World2DPass::destroy);
        world2d_pass.attr("category") = "Render";
        world2d_pass.attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        world2d_pass.attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        world2d_pass.attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("input_res", "output_res"));

        auto ui_widget_pass = nb::class_<UIWidgetPass, CxxFramePass>(m, "UIWidgetPass")
                                  .def(
                                      "__init__",
                                      [](UIWidgetPass* self,
                                         std::string input_res,
                                         std::string output_res,
                                         std::string pass_name,
                                         bool include_internal_entities,
                                         bool include_scene_entities) {
                                          new (self) UIWidgetPass(input_res, output_res);
                                          self->pass_name_set(pass_name);
                                          self->include_internal_entities = include_internal_entities;
                                          self->include_scene_entities = include_scene_entities;
                                          init_pass_from_python(self, "UIWidgetPass");
                                      },
                                      nb::arg("input_res") = "color+ui",
                                      nb::arg("output_res") = "color+widgets",
                                      nb::arg("pass_name") = "UIWidgets",
                                      nb::arg("include_internal_entities") = false,
                                      nb::arg("include_scene_entities") = true)
                                  .def_rw("input_res", &UIWidgetPass::input_res)
                                  .def_rw("output_res", &UIWidgetPass::output_res)
                                  .def_rw("include_scene_entities", &UIWidgetPass::include_scene_entities)
                                  .def_rw("include_internal_entities", &UIWidgetPass::include_internal_entities)
                                  .def("compute_reads", &UIWidgetPass::compute_reads)
                                  .def("compute_writes", &UIWidgetPass::compute_writes)
                                  .def("get_inplace_aliases", &UIWidgetPass::get_inplace_aliases)
                                  .def_prop_ro("reads", &UIWidgetPass::compute_reads)
                                  .def_prop_ro("writes", &UIWidgetPass::compute_writes)
                                  .def("destroy", &UIWidgetPass::destroy);
        ui_widget_pass.attr("category") = "UI";
        ui_widget_pass.attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        ui_widget_pass.attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        ui_widget_pass.attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("input_res", "output_res"));

        nb::class_<ShadowMapResult>(m, "ShadowMapResult")
            .def(nb::init<>())
            .def_ro("width", &ShadowMapResult::width)
            .def_ro("height", &ShadowMapResult::height)
            .def_prop_ro(
                "light_space_matrix",
                [](const ShadowMapResult& self) {
                    size_t shape[2] = {4, 4};
                    float* data = new float[16];
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            data[row * 4 + col] = self.light_space_matrix(col, row);
                        }
                    }
                    nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
                    return nb::ndarray<nb::numpy, float, nb::ndim<2>>(data, 2, shape, owner);
                },
                nb::rv_policy::move)
            .def_ro("light_index", &ShadowMapResult::light_index)
            .def_ro("cascade_index", &ShadowMapResult::cascade_index)
            .def_ro("cascade_split_near", &ShadowMapResult::cascade_split_near)
            .def_ro("cascade_split_far", &ShadowMapResult::cascade_split_far);

        nb::class_<ShadowPass, CxxFramePass>(m, "ShadowPass")
            .def(
                "__init__",
                [](ShadowPass* self, const std::string& output_res, const std::string& pass_name, float caster_offset) {
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
            .def("__repr__", [](const ShadowPass& p) { return "<ShadowPass '" + p.get_pass_name() + "'>"; });

        m.attr("ShadowPass").attr("category") = "Render";
        m.attr("ShadowPass").attr("node_inputs") = nb::make_tuple();
        m.attr("ShadowPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "shadow"));

        nb::class_<BloomPass, CxxFramePass>(m, "BloomPass")
            .def(
                "__init__",
                [](BloomPass* self,
                   const std::string& input_res,
                   const std::string& output_res,
                   const std::string& pass_name,
                   float threshold,
                   float soft_threshold,
                   float intensity,
                   int mip_levels,
                   float scatter) {
                    new (self)
                        BloomPass(input_res, output_res, threshold, soft_threshold, intensity, mip_levels, scatter);
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
                nb::arg("mip_levels") = 5,
                nb::arg("scatter") = 0.7f)
            .def_rw("input_res", &BloomPass::input_res)
            .def_rw("output_res", &BloomPass::output_res)
            .def_rw("output_res_target", &BloomPass::output_res_target)
            .def_rw("threshold", &BloomPass::threshold)
            .def_rw("soft_threshold", &BloomPass::soft_threshold)
            .def_rw("intensity", &BloomPass::intensity)
            .def_rw("mip_levels", &BloomPass::mip_levels)
            .def_rw("scatter", &BloomPass::scatter)
            .def("compute_reads", &BloomPass::compute_reads)
            .def("compute_writes", &BloomPass::compute_writes)
            .def("get_inplace_aliases", &BloomPass::get_inplace_aliases)
            .def_prop_ro("reads", &BloomPass::compute_reads)
            .def_prop_ro("writes", &BloomPass::compute_writes)
            .def("destroy", &BloomPass::destroy);

        m.attr("BloomPass").attr("category") = "Effects";
        m.attr("BloomPass").attr("node_inputs") =
            nb::make_tuple(nb::make_tuple("input_res", "fbo"), nb::make_tuple("output_res_target", "fbo"));
        m.attr("BloomPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("BloomPass").attr("node_inplace_pairs") =
            nb::make_tuple(nb::make_tuple("output_res_target", "output_res"));

        nb::class_<GrayscalePass, CxxFramePass>(m, "GrayscalePass")
            .def(
                "__init__",
                [](GrayscalePass* self,
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

        m.attr("GrayscalePass").attr("category") = "Effects";
        m.attr("GrayscalePass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        m.attr("GrayscalePass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("GrayscalePass").attr("node_inplace_pairs") = nb::make_tuple();

        nb::class_<SkyBoxPass, CxxFramePass>(m, "SkyBoxPass")
            .def(
                "__init__",
                [](SkyBoxPass* self,
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

        m.attr("SkyBoxPass").attr("category") = "Render";
        m.attr("SkyBoxPass").attr("node_inputs") = nb::make_tuple(nb::make_tuple("input_res", "fbo"));
        m.attr("SkyBoxPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("SkyBoxPass").attr("node_inplace_pairs") = nb::make_tuple(nb::make_tuple("input_res", "output_res"));

        nb::class_<TonemapPass, CxxFramePass>(m, "TonemapPass")
            .def(
                "__init__",
                [](TonemapPass* self,
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
            .def_rw("output_res_target", &TonemapPass::output_res_target)
            .def_rw("exposure", &TonemapPass::exposure)
            .def_rw("method", &TonemapPass::method)
            .def("compute_reads", &TonemapPass::compute_reads)
            .def("compute_writes", &TonemapPass::compute_writes)
            .def("get_inplace_aliases", &TonemapPass::get_inplace_aliases)
            .def_prop_ro("reads", &TonemapPass::compute_reads)
            .def_prop_ro("writes", &TonemapPass::compute_writes)
            .def("destroy", &TonemapPass::destroy);

        m.attr("TonemapPass").attr("category") = "Effects";
        m.attr("TonemapPass").attr("node_inputs") =
            nb::make_tuple(nb::make_tuple("input_res", "fbo"), nb::make_tuple("output_res_target", "fbo"));
        m.attr("TonemapPass").attr("node_outputs") = nb::make_tuple(nb::make_tuple("output_res", "fbo"));
        m.attr("TonemapPass").attr("node_inplace_pairs") =
            nb::make_tuple(nb::make_tuple("output_res_target", "output_res"));

        m.attr("TONEMAP_ACES") = 0;
        m.attr("TONEMAP_REINHARD") = 1;
        m.attr("TONEMAP_NONE") = 2;

        m.def(
            "tc_picking_id_to_rgb",
            [](int id) {
                int r, g, b;
                tc_picking_id_to_rgb(id, &r, &g, &b);
                return std::make_tuple(r, g, b);
            },
            "Convert entity pick ID to RGB (0-255 range), caches for reverse lookup");

        m.def("tc_picking_rgb_to_id",
              &tc_picking_rgb_to_id,
              "Convert RGB (0-255) back to entity pick ID, returns 0 if not cached");

        m.def("tc_picking_cache_clear", &tc_picking_cache_clear, "Clear the picking cache");
    }

} // namespace termin

NB_MODULE(_render_passes_native, m) {
    nb::module_::import_("termin.render_framework._render_framework_native");
    termin::bind_render_passes(m);
}
