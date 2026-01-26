#include "common.hpp"
#include "termin/render/render_engine.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/tc_scene_ref.hpp"
#include "termin/viewport/tc_viewport_handle.hpp"

#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/optional.h>

extern "C" {
#include "tc_pipeline.h"
#include "tc_pass.h"
}

namespace termin {

void bind_render_engine(nb::module_& m) {
    // Note: FBOPool is not bound because it contains non-copyable unique_ptr
    // Access FBO pool through RenderEngine if needed

    nb::class_<RenderEngine>(m, "RenderEngine")
        .def(nb::init<>())
        .def(nb::init<GraphicsBackend*>(), nb::arg("graphics"))
        .def_rw("graphics", &RenderEngine::graphics)
        .def("render_view_to_fbo", [](RenderEngine& self,
                                   tc_pipeline* pipeline,
                                   FramebufferHandle* target_fbo,
                                   int width,
                                   int height,
                                   TcSceneRef scene_ref,
                                   CameraComponent* camera,
                                   TcViewport* viewport,
                                   const std::vector<Light>& lights,
                                   uint64_t layer_mask) {
            self.render_view_to_fbo(
                pipeline,
                target_fbo,
                width,
                height,
                scene_ref.ptr(),
                camera,
                viewport ? viewport->ptr_ : nullptr,
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
             nb::arg("lights"),
             nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL)
        .def("clear_fbo_pool", &RenderEngine::clear_fbo_pool)
        .def("get_fbo", [](RenderEngine& self, const std::string& key) -> FramebufferHandle* {
            return self.fbo_pool().get(key);
        }, nb::arg("key"), nb::rv_policy::reference)
        .def("get_fbo_keys", [](RenderEngine& self) -> std::vector<std::string> {
            std::vector<std::string> keys;
            for (const auto& entry : self.fbo_pool().entries) {
                keys.push_back(entry.key);
            }
            return keys;
        })
        .def("render_scene_pipeline_offscreen", [](
            RenderEngine& self,
            tc_pipeline* pipeline,
            TcSceneRef scene_ref,
            const std::unordered_map<std::string, ViewportContext>& viewport_contexts,
            const std::vector<Light>& lights,
            const std::string& default_viewport
        ) {
            self.render_scene_pipeline_offscreen(
                pipeline,
                scene_ref.ptr(),
                viewport_contexts,
                lights,
                default_viewport
            );
        },
             nb::arg("pipeline"),
             nb::arg("scene"),
             nb::arg("viewport_contexts"),
             nb::arg("lights"),
             nb::arg("default_viewport") = "");

    // ViewportContext for multi-viewport rendering
    nb::class_<ViewportContext>(m, "ViewportContext")
        .def(nb::init<>())
        .def_rw("name", &ViewportContext::name)
        .def_rw("camera", &ViewportContext::camera)
        .def_rw("rect", &ViewportContext::rect)
        .def_rw("layer_mask", &ViewportContext::layer_mask)
        .def_rw("output_fbo", &ViewportContext::output_fbo);
}

} // namespace termin
