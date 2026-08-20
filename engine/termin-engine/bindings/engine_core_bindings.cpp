// engine_core_bindings.cpp - Python bindings for EngineCore
#include <nanobind/nanobind.h>
#include <nanobind/stl/function.h>

#include <utility>

#include "termin/engine/engine_core.hpp"
#include <termin/tc_scene.hpp>

namespace nb = nanobind;

namespace termin {

    void bind_engine_core(nb::module_& m) {
        m.def(
            "_borrow_engine_core",
            [](nb::handle capsule) -> EngineCore* {
                constexpr const char* capsule_name = "termin.EngineCore.borrowed";
                if (!PyCapsule_IsValid(capsule.ptr(), capsule_name)) {
                    throw nb::type_error("expected a borrowed EngineCore host capsule");
                }
                return static_cast<EngineCore*>(PyCapsule_GetPointer(capsule.ptr(), capsule_name));
            },
            nb::arg("capsule"),
            nb::rv_policy::reference,
            "Convert an explicit C++ host capsule into a borrowed EngineCore reference.");

        nb::class_<EngineLoopClient>(m, "EngineLoopClient")
            .def(nb::init<>(), "Create an incomplete loop client for explicit population.")
            .def(nb::init<std::function<void()>, std::function<bool()>, std::function<void()>>(),
                 nb::arg("poll_events"),
                 nb::arg("should_continue"),
                 nb::arg("on_shutdown"),
                 "Create one complete external main-loop integration.")
            .def_rw("poll_events", &EngineLoopClient::poll_events)
            .def_rw("should_continue", &EngineLoopClient::should_continue)
            .def_rw("on_shutdown", &EngineLoopClient::on_shutdown);

        nb::class_<EngineLoopClientConnection>(m, "EngineLoopClientConnection")
            .def("detach",
                 &EngineLoopClientConnection::detach,
                 "Detach the complete loop client. Repeated calls are harmless.")
            .def("connected",
                 &EngineLoopClientConnection::connected,
                 "Return whether this handle still owns the engine connection.")
            .def("__bool__", &EngineLoopClientConnection::connected);

        nb::class_<EngineCore>(m, "EngineCore")
            .def(nb::init<>(),
                 "Create EngineCore. Python player uses this when it is not "
                 "started through a C++ entry point.")

            // Access to managers
            .def_prop_ro(
                "scene_manager",
                [](EngineCore& self) -> SceneManager& { return self.scene_manager; },
                nb::rv_policy::reference_internal,
                "Access to SceneManager owned by this EngineCore")

            .def_prop_ro(
                "rendering_manager",
                [](EngineCore& self) -> RenderingManager& { return self.rendering_manager; },
                nb::rv_policy::reference_internal,
                "Access to RenderingManager owned by this EngineCore")

            .def_prop_ro(
                "render_topology",
                [](EngineCore& self) -> RenderTopology& { return self.render_topology; },
                nb::rv_policy::reference_internal,
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

            .def(
                "attach_loop_client",
                [](EngineCore& self, EngineLoopClient& client) { return self.attach_loop_client(std::move(client)); },
                nb::arg("client"),
                "Atomically attach and consume one complete loop client. "
                "The returned connection controls its lifetime.")

            // Main loop
            .def("tick",
                 &EngineCore::tick,
                 nb::arg("dt"),
                 "Advance RuntimeSession and scene simulation without rendering.")

            .def("tick_and_render",
                 &EngineCore::tick_and_render,
                 nb::arg("dt"),
                 "Run one frame: tick scenes, prepare render, render, invoke after-render callback.")

            .def("run",
                 &EngineCore::run,
                 "Run the attached loop client until should_continue returns False or stop() is called.")

            .def("stop", &EngineCore::stop, "Stop the run() loop")

            .def("is_running", &EngineCore::is_running, "Check if main loop is running")

            .def(
                "begin_session",
                [](EngineCore& self, nb::object controller) {
                    if (controller.is_none()) {
                        return self.begin_session();
                    }
                    if (!nb::isinstance<WorldControllerInstance>(controller)) {
                        throw nb::type_error(
                            "controller must be a WorldControllerInstance or None");
                    }
                    auto& owner = nb::cast<WorldControllerInstance&>(controller);
                    return self.begin_session(std::move(owner));
                },
                nb::arg("controller") = nb::none(),
                "Begin one supervised world run and consume an optional controller owner.")

            .def("end_session", &EngineCore::end_session, "End and release the active world run.")

            .def(
                "bind_runtime_scene",
                [](EngineCore& self, const TcSceneRef& scene) {
                    return self.bind_runtime_scene(scene.handle());
                },
                nb::arg("scene"),
                "Bind an already registered runtime scene to the active WorldContext.")

            .def(
                "unbind_runtime_scene",
                [](EngineCore& self, const TcSceneRef& scene) {
                    return self.unbind_runtime_scene(scene.handle());
                },
                nb::arg("scene"),
                "Remove this session's transient WorldContext association from a scene.")

            .def_prop_ro("has_runtime_session",
                         &EngineCore::has_runtime_session,
                         "Whether this EngineCore owns an active RuntimeSession.")

            .def("shutdown",
                 &EngineCore::shutdown,
                 "Finalize engine-owned scenes and rendering resources. Repeated calls are harmless.");
    }

} // namespace termin
