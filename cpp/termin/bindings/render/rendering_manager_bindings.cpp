// rendering_manager_bindings.cpp - Python bindings for RenderingManager scene pipelines

#include "common.hpp"
#include "termin/render/rendering_manager.hpp"
#include "termin/render/render_pipeline.hpp"
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/vector.h>

extern "C" {
#include "tc_scene.h"
}

namespace termin {

// Helper to extract tc_scene_handle from Python Scene object
static tc_scene_handle get_scene_handle(nb::object scene_py) {
    tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
    if (!scene_py.is_none() && nb::hasattr(scene_py, "_tc_scene")) {
        nb::object tc_scene_obj = scene_py.attr("_tc_scene");
        if (nb::hasattr(tc_scene_obj, "scene_handle")) {
            auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(tc_scene_obj.attr("scene_handle")());
            scene.index = std::get<0>(h);
            scene.generation = std::get<1>(h);
        }
    }
    return scene;
}

void bind_rendering_manager(nb::module_& m) {
    // RenderingManager singleton with scene pipeline methods
    nb::class_<RenderingManager>(m, "RenderingManager")
        .def_static("instance", &RenderingManager::instance, nb::rv_policy::reference)

        // Scene pipeline management - accepts Python Scene object
        .def("add_scene_pipeline", [](RenderingManager& self,
                                       nb::object scene_py,
                                       const std::string& name,
                                       RenderPipeline* pipeline) {
            tc_scene_handle scene = get_scene_handle(scene_py);
            self.add_scene_pipeline(scene, name, pipeline);
        }, nb::arg("scene"), nb::arg("name"), nb::arg("pipeline"))

        .def("remove_scene_pipeline", [](RenderingManager& self,
                                          nb::object scene_py,
                                          const std::string& name) {
            tc_scene_handle scene = get_scene_handle(scene_py);
            self.remove_scene_pipeline(scene, name);
        }, nb::arg("scene"), nb::arg("name"))

        .def("get_scene_pipeline", [](RenderingManager& self,
                                       nb::object scene_py,
                                       const std::string& name) -> RenderPipeline* {
            tc_scene_handle scene = get_scene_handle(scene_py);
            return self.get_scene_pipeline(scene, name);
        }, nb::arg("scene"), nb::arg("name"), nb::rv_policy::reference)

        .def("get_scene_pipeline", [](RenderingManager& self,
                                       const std::string& name) -> RenderPipeline* {
            return self.get_scene_pipeline(name);
        }, nb::arg("name"), nb::rv_policy::reference)

        .def("clear_scene_pipelines", [](RenderingManager& self,
                                          nb::object scene_py) {
            tc_scene_handle scene = get_scene_handle(scene_py);
            self.clear_scene_pipelines(scene);
        }, nb::arg("scene"))

        .def("clear_all_scene_pipelines", &RenderingManager::clear_all_scene_pipelines)

        // Pipeline targets
        .def("set_pipeline_targets", &RenderingManager::set_pipeline_targets,
             nb::arg("pipeline_name"), nb::arg("targets"))
        .def("get_pipeline_targets", &RenderingManager::get_pipeline_targets,
             nb::arg("pipeline_name"), nb::rv_policy::reference)

        // Get pipeline names for scene
        .def("get_pipeline_names", [](RenderingManager& self, nb::object scene_py) {
            tc_scene_handle scene = get_scene_handle(scene_py);
            return self.get_pipeline_names(scene);
        }, nb::arg("scene"))
    ;
}

} // namespace termin
