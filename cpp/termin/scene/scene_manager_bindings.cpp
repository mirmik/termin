// scene_manager_bindings.cpp - Python bindings for SceneManager
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/trampoline.h>

#include "scene_manager.hpp"

extern "C" {
#include "../../../core_c/include/tc_scene.h"
#include "../../../core_c/include/tc_scene_pool.h"
}

namespace nb = nanobind;

namespace termin {

// Trampoline class for Python inheritance
class PySceneManager : public SceneManager {
public:
    NB_TRAMPOLINE(SceneManager, 1);

    bool tick(double dt) override {
        NB_OVERRIDE(tick, dt);
    }
};

void bind_scene_manager(nb::module_& m) {
    // Bind SceneMode enum
    nb::enum_<tc_scene_mode>(m, "SceneMode")
        .value("INACTIVE", TC_SCENE_MODE_INACTIVE, "Loaded but not updated")
        .value("STOP", TC_SCENE_MODE_STOP, "Editor update (gizmos, selection)")
        .value("PLAY", TC_SCENE_MODE_PLAY, "Full simulation")
        .export_values();

    // Bind SceneManager class
    nb::class_<SceneManager, PySceneManager>(m, "SceneManager")
        .def(nb::init<>())

        // Scene registration - takes handle as tuple (index, generation)
        .def("register_scene", [](SceneManager& self, const std::string& name, std::tuple<uint32_t, uint32_t> handle_tuple) {
            tc_scene_handle h;
            h.index = std::get<0>(handle_tuple);
            h.generation = std::get<1>(handle_tuple);
            self.register_scene(name, h);
        }, nb::arg("name"), nb::arg("handle"),
           "Register a scene by name. handle is (index, generation) tuple.")

        .def("unregister_scene", &SceneManager::unregister_scene, nb::arg("name"),
             "Unregister a scene by name.")

        // Mode management
        .def("get_mode", [](const SceneManager& self, const std::string& name) {
            return self.get_mode(name);
        }, nb::arg("name"), "Get scene mode.")

        .def("set_mode", [](SceneManager& self, const std::string& name, tc_scene_mode mode) {
            self.set_mode(name, mode);
        }, nb::arg("name"), nb::arg("mode"), "Set scene mode.")

        // Scene access
        .def("has_scene", &SceneManager::has_scene, nb::arg("name"),
             "Check if scene exists.")

        .def("scene_names", &SceneManager::scene_names,
             "Get list of all scene names.")

        .def("has_play_scenes", &SceneManager::has_play_scenes,
             "Check if any scene is in PLAY mode.")

        // Update cycle
        .def("tick", &SceneManager::tick, nb::arg("dt"),
             "Update all scenes based on their mode. Returns true if render needed.")

        .def("before_render", &SceneManager::before_render,
             "Call before_render on all active scenes.")

        // Render request
        .def("request_render", &SceneManager::request_render,
             "Request render on next tick.")

        .def("consume_render_request", &SceneManager::consume_render_request,
             "Consume and return render request flag.")
        ;
}

} // namespace termin
