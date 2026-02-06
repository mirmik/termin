// engine_core_bindings.cpp - Python bindings for EngineCore
#include <nanobind/nanobind.h>
#include <nanobind/stl/function.h>

#include "termin/engine/engine_core.hpp"

namespace nb = nanobind;

namespace termin {

void bind_engine_core(nb::module_& m) {
    nb::class_<EngineCore>(m, "EngineCore")
        // No __init__ - created in C++ only

        // Singleton access
        .def_static("instance", &EngineCore::instance, nb::rv_policy::reference,
           "Get the EngineCore instance (created in C++)")

        // Access to managers
        .def_prop_ro("scene_manager", [](EngineCore& self) -> SceneManager& {
            return self.scene_manager;
        }, nb::rv_policy::reference_internal,
           "Access to SceneManager owned by this EngineCore")

        .def_prop_ro("rendering_manager", [](EngineCore& self) -> RenderingManager& {
            return self.rendering_manager;
        }, nb::rv_policy::reference_internal,
           "Access to RenderingManager owned by this EngineCore")

        // Configuration
        .def_prop_rw("target_fps",
            &EngineCore::target_fps,
            &EngineCore::set_target_fps,
            "Target frames per second for main loop")

        // Callbacks
        .def("set_poll_events_callback", [](EngineCore& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_poll_events_callback(nullptr);
            } else {
                auto cb = std::make_shared<nb::object>(callback);
                self.set_poll_events_callback([cb]() {
                    nb::gil_scoped_acquire guard;
                    (*cb)();
                });
            }
        }, nb::arg("callback"),
           "Set callback for polling events (Qt, SDL). Called each frame.")

        .def("set_should_continue_callback", [](EngineCore& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_should_continue_callback(nullptr);
            } else {
                auto cb = std::make_shared<nb::object>(callback);
                self.set_should_continue_callback([cb]() -> bool {
                    nb::gil_scoped_acquire guard;
                    return nb::cast<bool>((*cb)());
                });
            }
        }, nb::arg("callback"),
           "Set callback to check if loop should continue. Return False to stop.")

        // Main loop
        .def("run", &EngineCore::run,
             "Run blocking main loop. Returns when should_continue returns False or stop() called.")

        .def("stop", &EngineCore::stop,
             "Stop the run() loop")

        .def("is_running", &EngineCore::is_running,
             "Check if main loop is running")
        ;
}

} // namespace termin
