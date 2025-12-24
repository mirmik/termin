#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

#include "scene/scene.hpp"
#include "entity/entity.hpp"
#include "entity/component.hpp"

namespace py = pybind11;

namespace termin {

void bind_scene(py::module_& m) {
    // SkyboxType enum
    py::enum_<SkyboxType>(m, "SkyboxType")
        .value("NONE", SkyboxType::None)
        .value("SOLID", SkyboxType::Solid)
        .value("GRADIENT", SkyboxType::Gradient)
        .export_values();

    // Scene class
    py::class_<Scene>(m, "Scene")
        .def(py::init<const std::string&>(), py::arg("uuid") = "")

        // Identifiable
        .def_readwrite("uuid", &Scene::uuid)
        .def_readwrite("runtime_id", &Scene::runtime_id)

        // Background
        .def_readwrite("background_color", &Scene::background_color)
        .def_readwrite("background_alpha", &Scene::background_alpha)

        // Lighting
        .def_readwrite("lights", &Scene::lights)
        .def_readwrite("ambient_color", &Scene::ambient_color)
        .def_readwrite("ambient_intensity", &Scene::ambient_intensity)
        .def_readwrite("light_direction", &Scene::light_direction)
        .def_readwrite("light_color", &Scene::light_color)
        .def_readwrite("shadow_settings", &Scene::shadow_settings)

        // Skybox
        .def_readwrite("skybox_type", &Scene::skybox_type)
        .def_readwrite("skybox_color", &Scene::skybox_color)
        .def_readwrite("skybox_top_color", &Scene::skybox_top_color)
        .def_readwrite("skybox_bottom_color", &Scene::skybox_bottom_color)

        // Entity management
        .def("add", &Scene::add, py::arg("entity"))
        .def("add_non_recurse", &Scene::add_non_recurse, py::arg("entity"))
        .def("remove", &Scene::remove, py::arg("entity"))
        .def("find_entity_by_uuid", &Scene::find_entity_by_uuid,
             py::arg("uuid"), py::return_value_policy::reference)
        .def_property_readonly("entities", &Scene::get_entities,
                               py::return_value_policy::reference)
        .def("entity_count", &Scene::entity_count)

        // Component registration
        .def("register_component", &Scene::register_component, py::arg("component"))
        .def("unregister_component", &Scene::unregister_component, py::arg("component"))

        // Update
        .def_readwrite("fixed_timestep", &Scene::fixed_timestep)
        .def("update", &Scene::update, py::arg("dt"))

        // Events (Python callables)
        .def_readwrite("on_entity_added", &Scene::on_entity_added)
        .def_readwrite("on_entity_removed", &Scene::on_entity_removed)
        ;
}

} // namespace termin
