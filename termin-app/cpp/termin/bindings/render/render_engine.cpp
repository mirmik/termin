#include "common.hpp"
#include "termin/render/render_engine.hpp"
#include <tgfx2/i_render_device.hpp>
#include "termin/render/render_pipeline.hpp"
#include "tgfx/graphics_backend.hpp"
#include "tgfx2/render_context.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/camera/render_camera_utils.hpp"
#include <termin/tc_scene.hpp>
#include "termin/tc_scene_render_ext.hpp"

#include <algorithm>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/optional.h>

namespace termin {

void bind_render_engine(nb::module_& m) {
    // Note: FBOPool is not bound because it contains non-copyable unique_ptr
    // Access FBO pool through RenderEngine if needed

    nb::class_<RenderEngine>(m, "RenderEngine")
        .def(nb::init<>())
        .def("ensure_tgfx2", &RenderEngine::ensure_tgfx2)
        .def_prop_ro("tgfx2_ctx", &RenderEngine::tgfx2_ctx,
                     nb::rv_policy::reference_internal)
        .def_prop_ro("tgfx2_device", &RenderEngine::tgfx2_device,
                     nb::rv_policy::reference_internal)
        .def("render_view_to_fbo", [](RenderEngine& self,
                                   RenderPipeline& pipeline,
                                   FramebufferHandle* target_fbo,
                                   int width,
                                   int height,
                                   TcSceneRef scene_ref,
                                   CameraComponent* camera,
                                   nb::object viewport_obj,
                                   uint64_t layer_mask) {
            std::string viewport_name;
            tc_entity_handle internal_entities = TC_ENTITY_HANDLE_INVALID;
            if (!viewport_obj.is_none()) {
                try {
                    viewport_name = nb::cast<std::string>(viewport_obj.attr("name"));
                    nb::object internal_entities_obj = viewport_obj.attr("internal_entities");
                    if (!internal_entities_obj.is_none()) {
                        internal_entities = nb::cast<Entity>(internal_entities_obj).handle();
                    }
                } catch (const std::exception& e) {
                    tc::Log::error("[RenderEngine binding] viewport conversion failed: %s", e.what());
                    throw;
                }
            }
            std::vector<Light> lights;
            RenderCamera render_camera = camera
                ? make_render_camera(*camera, static_cast<double>(width) / std::max(1, height))
                : RenderCamera();
            self.render_view_to_fbo(
                pipeline,
                target_fbo,
                width,
                height,
                scene_ref.handle(),
                render_camera,
                viewport_name,
                internal_entities,
                lights,
                layer_mask
            );
        },
             nb::arg("pipeline"),
             nb::arg("target_fbo"),
             nb::arg("width"),
             nb::arg("height"),
             nb::arg("scene"),
             nb::arg("camera"),
             nb::arg("viewport").none(),
             nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL)
        .def("render_view_to_fbo_id", [](RenderEngine& self,
                                      RenderPipeline& pipeline,
                                      uint32_t target_fbo_id,
                                      int width,
                                      int height,
                                      TcSceneRef scene_ref,
                                      CameraComponent* camera,
                                      nb::object viewport_obj,
                                      uint64_t layer_mask) {
            std::string viewport_name;
            tc_entity_handle internal_entities = TC_ENTITY_HANDLE_INVALID;
            if (!viewport_obj.is_none()) {
                try {
                    viewport_name = nb::cast<std::string>(viewport_obj.attr("name"));
                    nb::object internal_entities_obj = viewport_obj.attr("internal_entities");
                    if (!internal_entities_obj.is_none()) {
                        internal_entities = nb::cast<Entity>(internal_entities_obj).handle();
                    }
                } catch (const std::exception& e) {
                    tc::Log::error("[RenderEngine binding] viewport conversion failed: %s", e.what());
                    throw;
                }
            }
            std::vector<Light> lights;
            RenderCamera render_camera = camera
                ? make_render_camera(*camera, static_cast<double>(width) / std::max(1, height))
                : RenderCamera();
            self.render_view_to_fbo_id(
                pipeline,
                target_fbo_id,
                width,
                height,
                scene_ref.handle(),
                render_camera,
                viewport_name,
                internal_entities,
                lights,
                layer_mask
            );
        },
             nb::arg("pipeline"),
             nb::arg("target_fbo_id"),
             nb::arg("width"),
             nb::arg("height"),
             nb::arg("scene"),
             nb::arg("camera"),
             nb::arg("viewport").none(),
             nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL)
        .def("render_scene_pipeline_offscreen", [](
            RenderEngine& self,
            RenderPipeline& pipeline,
            TcSceneRef scene_ref,
            const std::unordered_map<std::string, ViewportContext>& viewport_contexts,
            const std::string& default_viewport
        ) {
            std::vector<Light> lights;
            self.render_scene_pipeline_offscreen(
                pipeline,
                scene_ref.handle(),
                viewport_contexts,
                lights,
                default_viewport
            );
        },
             nb::arg("pipeline"),
             nb::arg("scene"),
             nb::arg("viewport_contexts"),
             nb::arg("default_viewport") = "");

    // ViewportContext for multi-viewport rendering
    nb::class_<ViewportContext>(m, "ViewportContext")
        .def(nb::init<>())
        .def_rw("name", &ViewportContext::name)
        .def_rw("camera", &ViewportContext::camera)
        .def_rw("rect", &ViewportContext::rect)
        .def_rw("layer_mask", &ViewportContext::layer_mask)
        .def_rw("output_color_tex", &ViewportContext::output_color_tex)
        .def_rw("output_depth_tex", &ViewportContext::output_depth_tex);
}

} // namespace termin
