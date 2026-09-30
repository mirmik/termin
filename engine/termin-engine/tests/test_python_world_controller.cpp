#include "guard_main.h"

GUARD_TEST_MAIN();

#include <Python.h>

#include <string>
#include <utility>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <inspect/tc_runtime_type_registry.h>
#include <tcbase/tc_log.h>
#include <termin/engine/engine_core.hpp>
#include <termin/engine/world_controller.hpp>

namespace {

    namespace nb = nanobind;

    std::string captured_errors;

    void capture_error(tc_log_level level, const char* message) {
        if (level == TC_LOG_ERROR && message) {
            captured_errors += message;
            captured_errors += '\n';
        }
    }

    struct ErrorLogCapture {
        ErrorLogCapture() {
            captured_errors.clear();
            tc_log_set_callback(capture_error);
        }
        ~ErrorLogCapture() {
            tc_log_set_callback(nullptr);
        }
    };

    bool register_class(
        nb::module_& bindings, nb::module_& main, const char* type_name, const char* class_name, const char* owner) {
        return nb::cast<bool>(
            bindings.attr("_register_world_controller")(type_name, main.attr(class_name), owner, nb::none()));
    }

    std::string event_at(nb::module_& main, size_t index) {
        nb::list events = nb::cast<nb::list>(main.attr("events"));
        return nb::cast<std::string>(events[index]);
    }

} // namespace

TEST_CASE("Python WorldController factory owns objects and contains lifecycle exceptions") {
    tc_runtime_type_registry_clear();
    REQUIRE_FALSE(Py_IsInitialized());
    Py_Initialize();

    {
        nb::module_ main = nb::module_::import_("__main__");
        nb::module_ sys = nb::module_::import_("sys");
        sys.attr("path").attr("insert")(0, TERMIN_ENGINE_WORLD_CONTROLLER_TEST_MODULE_DIR);
        nb::module_ bindings = nb::module_::import_("_world_controller_test_native");

        const char* script = R"PY(
events = []
retained_context = None
retained_failure_context = None

class LifecycleController:
    version = 1

    def __init__(self):
        events.append("construct:1")

    def start(self, context):
        global retained_context
        assert context.valid
        self.context = context
        retained_context = context
        events.append("start:1")

    def stop(self, context):
        assert context.valid
        assert context is self.context
        assert context is retained_context
        events.append("stop:1")

    def __del__(self):
        events.append("destroy:1")

class ReplacementController:
    version = 2

    def start(self, context):
        pass

    def stop(self, context):
        pass

class ConstructorFailureController:
    def __init__(self):
        raise RuntimeError("injected Python constructor failure")

    def start(self, context):
        pass

    def stop(self, context):
        pass

class StartFailureController:
    def __init__(self):
        events.append("construct:failure")

    def start(self, context):
        global retained_failure_context
        assert context.valid
        self.context = context
        retained_failure_context = context
        events.append("start:failure")
        raise RuntimeError("injected Python start failure")

    def stop(self, context):
        assert context.valid
        assert context is self.context
        assert context is retained_failure_context
        events.append("stop:failure")

    def __del__(self):
        events.append("destroy:failure")
)PY";
        REQUIRE_EQ(PyRun_SimpleString(script), 0);

        constexpr const char* owner = "termin-engine-python-test";
        constexpr const char* lifecycle_type = "PythonLifecycleController";
        REQUIRE(register_class(bindings, main, lifecycle_type, "LifecycleController", owner));

        termin::EngineCore engine;
        std::string error;
        termin::WorldControllerInstance instance;
        {
            nb::gil_scoped_release release;
            instance = termin::WorldControllerInstance::create(lifecycle_type, error);
        }
        REQUIRE(instance.valid());
        CHECK(error.empty());
        bool started = false;
        bool unload_while_live = true;
        {
            nb::gil_scoped_release release;
            started = engine.begin_session(std::move(instance));
            unload_while_live = tc_runtime_type_registry_prepare_owner_unload(owner, nullptr);
        }

        REQUIRE(started);
        CHECK_FALSE(instance.valid());
        CHECK(engine.has_runtime_session());
        CHECK(nb::cast<bool>(main.attr("retained_context").attr("valid")));
        CHECK_FALSE(unload_while_live);
        CHECK_EQ(tc_runtime_type_registry_instance_count(lifecycle_type), 1u);
        CHECK_FALSE(register_class(bindings, main, lifecycle_type, "ReplacementController", owner));

        bool ended = false;
        {
            nb::gil_scoped_release release;
            ended = engine.end_session();
        }

        CHECK(ended);
        CHECK_FALSE(engine.has_runtime_session());
        CHECK_EQ(tc_runtime_type_registry_instance_count(lifecycle_type), 0u);
        CHECK_FALSE(nb::cast<bool>(main.attr("retained_context").attr("valid")));
        CHECK(PyErr_Occurred() == nullptr);
        nb::list lifecycle_events = nb::cast<nb::list>(main.attr("events"));
        REQUIRE_EQ(nb::len(lifecycle_events), 4u);
        CHECK_EQ(event_at(main, 0), std::string("construct:1"));
        CHECK_EQ(event_at(main, 1), std::string("start:1"));
        CHECK_EQ(event_at(main, 2), std::string("stop:1"));
        CHECK_EQ(event_at(main, 3), std::string("destroy:1"));

        CHECK(register_class(bindings, main, lifecycle_type, "ReplacementController", owner));
        nb::dict replacement_info = nb::cast<nb::dict>(bindings.attr("_world_controller_type_info")(lifecycle_type));
        CHECK(nb::cast<int>(replacement_info["python_class"].attr("version")) == 2);

        constexpr const char* constructor_failure_type = "PythonConstructorFailureController";
        REQUIRE(register_class(bindings, main, constructor_failure_type, "ConstructorFailureController", owner));
        termin::WorldControllerInstance failed_construction;
        {
            nb::gil_scoped_release release;
            failed_construction = termin::WorldControllerInstance::create(constructor_failure_type, error);
        }
        CHECK_FALSE(failed_construction.valid());
        CHECK(error.find("injected Python constructor failure") != std::string::npos);
        CHECK_EQ(tc_runtime_type_registry_instance_count(constructor_failure_type), 0u);
        CHECK(PyErr_Occurred() == nullptr);

        constexpr const char* start_failure_type = "PythonStartFailureController";
        REQUIRE(register_class(bindings, main, start_failure_type, "StartFailureController", owner));
        termin::WorldControllerInstance failed_start;
        {
            nb::gil_scoped_release release;
            failed_start = termin::WorldControllerInstance::create(start_failure_type, error);
        }
        REQUIRE(failed_start.valid());
        CHECK(error.empty());
        CHECK_EQ(tc_runtime_type_registry_instance_count(start_failure_type), 1u);
        bool start_result = true;
        {
            ErrorLogCapture capture;
            nb::gil_scoped_release release;
            start_result = engine.begin_session(std::move(failed_start));
        }
        CHECK_FALSE(start_result);
        CHECK(captured_errors.find("injected Python start failure") != std::string::npos);
        CHECK_FALSE(failed_start.valid());
        CHECK_FALSE(engine.has_runtime_session());
        CHECK_EQ(tc_runtime_type_registry_instance_count(start_failure_type), 0u);
        CHECK_FALSE(nb::cast<bool>(main.attr("retained_failure_context").attr("valid")));
        CHECK(PyErr_Occurred() == nullptr);

        nb::list events = nb::cast<nb::list>(main.attr("events"));
        REQUIRE_EQ(nb::len(events), 8u);
        CHECK_EQ(nb::cast<std::string>(events[4]), std::string("construct:failure"));
        CHECK_EQ(nb::cast<std::string>(events[5]), std::string("start:failure"));
        CHECK_EQ(nb::cast<std::string>(events[6]), std::string("stop:failure"));
        CHECK_EQ(nb::cast<std::string>(events[7]), std::string("destroy:failure"));

        main.attr("retained_context") = nb::none();
        main.attr("retained_failure_context") = nb::none();
        CHECK(engine.shutdown());
        CHECK_EQ(tc_runtime_type_registry_unregister_owner(owner), 3u);
        tc_runtime_type_registry_clear();
    }

    Py_Finalize();
}
