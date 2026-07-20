// engine_core_bindings.cpp - Python bindings for EngineCore
#include <nanobind/nanobind.h>
#include <nanobind/stl/function.h>

#include <utility>

#include "termin/engine/engine_core.hpp"

namespace nb = nanobind;

namespace termin {

void bind_engine_core(nb::module_& m) {
    m.def("_borrow_engine_core", [](nb::handle capsule) -> EngineCore* {
        constexpr const char* capsule_name = "termin.EngineCore.borrowed";
        if (!PyCapsule_IsValid(capsule.ptr(), capsule_name)) {
            throw nb::type_error("expected a borrowed EngineCore host capsule");
        }
        return static_cast<EngineCore*>(
            PyCapsule_GetPointer(capsule.ptr(), capsule_name));
    }, nb::arg("capsule"), nb::rv_policy::reference,
       "Convert an explicit C++ host capsule into a borrowed EngineCore reference.");

    nb::class_<EngineLoopClient>(m, "EngineLoopClient")
        .def(nb::init<>(),
             "Create an incomplete loop client for explicit population.")
        .def(nb::init<
                 std::function<void()>,
                 std::function<bool()>,
                 std::function<void()>>(),
             nb::arg("poll_events"),
             nb::arg("should_continue"),
             nb::arg("on_shutdown"),
             "Create one complete external main-loop integration.")
        .def_rw("poll_events", &EngineLoopClient::poll_events)
        .def_rw("should_continue", &EngineLoopClient::should_continue)
        .def_rw("on_shutdown", &EngineLoopClient::on_shutdown)
        ;

    nb::class_<EngineLoopClientConnection>(m, "EngineLoopClientConnection")
        .def("detach", &EngineLoopClientConnection::detach,
             "Detach the complete loop client. Repeated calls are harmless.")
        .def("connected", &EngineLoopClientConnection::connected,
             "Return whether this handle still owns the engine connection.")
        .def("__bool__", &EngineLoopClientConnection::connected)
        ;

    nb::class_<EngineCore>(m, "EngineCore")
        .def(nb::init<>(),
             "Create EngineCore. Python player uses this when it is not "
             "started through a C++ entry point.")

        // Access to managers
        .def_prop_ro("scene_manager", [](EngineCore& self) -> SceneManager& {
            return self.scene_manager;
        }, nb::rv_policy::reference_internal,
           "Access to SceneManager owned by this EngineCore")

        .def_prop_ro("rendering_manager", [](EngineCore& self) -> RenderingManager& {
            return self.rendering_manager;
        }, nb::rv_policy::reference_internal,
           "Access to RenderingManager owned by this EngineCore")

        .def_prop_ro("render_topology", [](EngineCore& self) -> RenderTopology& {
            return self.render_topology;
        }, nb::rv_policy::reference_internal,
           "Access to live render topology owned by this EngineCore")

        // Configuration
        .def_prop_rw("target_fps",
            &EngineCore::target_fps,
            &EngineCore::set_target_fps,
            "Software frame-rate limit for the main loop; zero means unlimited")

        .def_prop_rw("profile_ui",
            &EngineCore::profile_ui,
            &EngineCore::set_profile_ui,
            "When true, run() wraps poll_events in a 'UI' profiler section "
            "and the frame scope covers both UI and tick_and_render.")

        .def("attach_loop_client", [](EngineCore& self, EngineLoopClient& client) {
            return self.attach_loop_client(std::move(client));
        }, nb::arg("client"),
           "Atomically attach and consume one complete loop client. "
           "The returned connection controls its lifetime.")

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

        .def("set_on_shutdown_callback", [](EngineCore& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_on_shutdown_callback(nullptr);
            } else {
                auto cb = std::make_shared<nb::object>(callback);
                self.set_on_shutdown_callback([cb]() {
                    nb::gil_scoped_acquire guard;
                    (*cb)();
                });
            }
        }, nb::arg("callback"),
           "Set callback for cleanup after main loop ends.")

        // Main loop
        .def("tick_and_render", &EngineCore::tick_and_render, nb::arg("dt"),
             "Run one frame: tick scenes, prepare render, render, invoke after-render callback.")

        .def("run", &EngineCore::run,
             "Run blocking main loop. Returns when should_continue returns False or stop() called.")

        .def("stop", &EngineCore::stop,
             "Stop the run() loop")

        .def("is_running", &EngineCore::is_running,
             "Check if main loop is running")

        .def("shutdown", &EngineCore::shutdown,
             "Finalize engine-owned scenes and rendering resources. Repeated calls are harmless.")
        ;
}

} // namespace termin
