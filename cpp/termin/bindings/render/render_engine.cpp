#include "common.hpp"
#include "termin/render/render_engine.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/tc_scene.hpp"
#include "termin/viewport/tc_viewport_handle.hpp"

#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/optional.h>

namespace termin {

void bind_render_engine(nb::module_& m) {
    // Note: FBOPool is not bound because it contains non-copyable unique_ptr
    // Access FBO pool through RenderEngine if needed

    nb::class_<RenderEngine>(m, "RenderEngine")
        .def(nb::init<>())
        .def(nb::init<GraphicsBackend*>(), nb::arg("graphics"))
        .def_rw("graphics", &RenderEngine::graphics)
        .def("render_view_to_fbo", [](RenderEngine& self,
                                   RenderPipeline& pipeline,
                                   FramebufferHandle* target_fbo,
                                   int width,
                                   int height,
                                   TcSceneRef scene_ref,
                                   CameraComponent* camera,
                                   nb::object viewport_obj,
                                   uint64_t layer_mask) {
            // Convert viewport from Python object to handle
            tc_viewport_handle vh = TC_VIEWPORT_HANDLE_INVALID;
            if (!viewport_obj.is_none()) {
                try {
                    auto attr = viewport_obj.attr("_viewport_handle");
                    auto result = attr();
                    // Extract values directly from Python tuple without casting to std::tuple
                    // This avoids RTTI issues across modules
                    vh.index = nb::cast<uint32_t>(result[nb::int_(0)]);
                    vh.generation = nb::cast<uint32_t>(result[nb::int_(1)]);
                } catch (const std::exception& e) {
                    tc::Log::error("[TRACE BINDING] Exception during viewport conversion: %s", e.what());
                    throw;
                }
            }
            // Use overload that builds lights from scene automatically
            self.render_view_to_fbo(
                &pipeline,
                target_fbo,
                width,
                height,
                scene_ref.handle(),
                camera,
                vh,
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
        .def("render_scene_pipeline_offscreen", [](
            RenderEngine& self,
            RenderPipeline& pipeline,
            TcSceneRef scene_ref,
            const std::unordered_map<std::string, ViewportContext>& viewport_contexts,
            const std::string& default_viewport
        ) {
            // Use overload that builds lights from scene automatically
            self.render_scene_pipeline_offscreen(
                &pipeline,
                scene_ref.handle(),
                viewport_contexts,
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
        .def_rw("output_fbo", &ViewportContext::output_fbo);
}

} // namespace termin
