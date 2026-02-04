// scene_manager_bindings.cpp - Python bindings for SceneManager
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/trampoline.h>
#include <memory>

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

        // --- Scene lifecycle ---

        .def("create_scene", [](SceneManager& self, const std::string& name) {
            tc_scene_handle h = self.create_scene(name);
            // Return handle as tuple for Python to wrap in TcScene
            return std::make_tuple(h.index, h.generation);
        }, nb::arg("name"),
           "Create a new scene and register it. Returns handle tuple (index, generation).")

        .def("close_scene", &SceneManager::close_scene, nb::arg("name"),
             "Close and destroy a scene.")

        .def("close_all_scenes", &SceneManager::close_all_scenes,
             "Close all scenes.")

        // --- Scene registration (for external scenes) ---

        .def("register_scene", [](SceneManager& self, const std::string& name, std::tuple<uint32_t, uint32_t> handle_tuple) {
            tc_scene_handle h;
            h.index = std::get<0>(handle_tuple);
            h.generation = std::get<1>(handle_tuple);
            self.register_scene(name, h);
        }, nb::arg("name"), nb::arg("handle"),
           "Register an external scene by name. handle is (index, generation) tuple.")

        .def("unregister_scene", &SceneManager::unregister_scene, nb::arg("name"),
             "Unregister a scene by name (does not destroy it).")

        // --- Scene access ---

        .def("get_scene_handle", [](const SceneManager& self, const std::string& name) -> nb::object {
            tc_scene_handle h = self.get_scene(name);
            if (!tc_scene_handle_valid(h)) {
                return nb::none();
            }
            return nb::cast(std::make_tuple(h.index, h.generation));
        }, nb::arg("name"),
           "Get scene handle by name. Returns (index, generation) tuple or None.")

        .def("has_scene", &SceneManager::has_scene, nb::arg("name"),
             "Check if scene exists.")

        .def("scene_names", &SceneManager::scene_names,
             "Get list of all scene names.")

        // --- Path management ---

        .def("get_scene_path", &SceneManager::get_scene_path, nb::arg("name"),
             "Get file path for scene (empty if not set).")

        .def("set_scene_path", &SceneManager::set_scene_path,
             nb::arg("name"), nb::arg("path"),
             "Set file path for scene.")

        // --- Mode management ---

        .def("get_mode", [](const SceneManager& self, const std::string& name) {
            return self.get_mode(name);
        }, nb::arg("name"), "Get scene mode.")

        .def("set_mode", [](SceneManager& self, const std::string& name, tc_scene_mode mode) {
            self.set_mode(name, mode);
        }, nb::arg("name"), nb::arg("mode"), "Set scene mode.")

        .def("has_play_scenes", &SceneManager::has_play_scenes,
             "Check if any scene is in PLAY mode.")

        // --- Update cycle ---

        .def("tick", &SceneManager::tick, nb::arg("dt"),
             "Update all scenes based on their mode. Returns true if render needed.")

        .def("before_render", &SceneManager::before_render,
             "Call before_render on all active scenes.")

        // --- Render request ---

        .def("request_render", &SceneManager::request_render,
             "Request render on next tick.")

        .def("consume_render_request", &SceneManager::consume_render_request,
             "Consume and return render request flag.")

        // --- File I/O ---

        .def_static("read_json_file", &SceneManager::read_json_file, nb::arg("path"),
             "Read JSON file and return as string. Returns empty string on error.")

        .def_static("write_json_file", &SceneManager::write_json_file,
             nb::arg("path"), nb::arg("json"),
             "Write JSON string to file (atomic write).")

        // --- Callbacks ---

        .def("set_on_after_render", [](SceneManager& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_on_after_render(nullptr);
            } else {
                // Store callback as shared_ptr to prevent preventing Python shutdown
                auto cb = std::make_shared<nb::object>(callback);
                self.set_on_after_render([cb]() {
                    nb::gil_scoped_acquire guard;
                    (*cb)();
                });
            }
        }, nb::arg("callback"),
             "Set callback to run after render. Pass None to clear.")

        .def("set_on_before_scene_close", [](SceneManager& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_on_before_scene_close(nullptr);
            } else {
                auto cb = std::make_shared<nb::object>(callback);
                self.set_on_before_scene_close([cb](const std::string& name) {
                    nb::gil_scoped_acquire guard;
                    (*cb)(name);
                });
            }
        }, nb::arg("callback"),
             "Set callback to run before scene close. Pass None to clear.")

        .def("invoke_after_render", &SceneManager::invoke_after_render,
             "Invoke after_render callback (if set).")

        .def("invoke_before_scene_close", &SceneManager::invoke_before_scene_close, nb::arg("name"),
             "Invoke before_scene_close callback (if set).")
        ;
}

} // namespace termin
