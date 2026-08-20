#include "guard_main.h"

GUARD_TEST_MAIN();

#include <Python.h>

#include <string>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <inspect/tc_runtime_type_registry.h>
#include <termin/engine/world_controller.h>

namespace {

    namespace nb = nanobind;

    struct ErrorBuffer {
        char text[1024] = {};
        tc_world_controller_error_v1 value{sizeof(tc_world_controller_error_v1), text, sizeof(text)};
    };

    int g_context_token = 0;

    tc_world_context* test_context() {
        return reinterpret_cast<tc_world_context*>(&g_context_token);
    }

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

class LifecycleController:
    version = 1

    def __init__(self):
        events.append("construct:1")

    def start(self, context):
        assert context.valid
        self.context = context
        events.append("start:1")

    def stop(self, context):
        assert context.valid
        assert context is self.context
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
        assert context.valid
        events.append("start:failure")
        raise RuntimeError("injected Python start failure")

    def stop(self, context):
        assert context.valid
        events.append("stop:failure")

    def __del__(self):
        events.append("destroy:failure")
)PY";
        REQUIRE_EQ(PyRun_SimpleString(script), 0);

        constexpr const char* owner = "termin-engine-python-test";
        constexpr const char* lifecycle_type = "PythonLifecycleController";
        REQUIRE(register_class(bindings, main, lifecycle_type, "LifecycleController", owner));

        ErrorBuffer error;
        tc_world_controller_instance* instance = nullptr;

        PyThreadState* thread_state = PyEval_SaveThread();
        instance = tc_world_controller_instance_create(lifecycle_type, &error.value);
        const bool started = tc_world_controller_instance_start(instance, test_context(), &error.value);
        const bool unload_while_live = tc_runtime_type_registry_prepare_owner_unload(owner, nullptr);
        PyEval_RestoreThread(thread_state);

        REQUIRE(instance != nullptr);
        CHECK(started);
        CHECK_FALSE(unload_while_live);
        CHECK_EQ(tc_runtime_type_registry_instance_count(lifecycle_type), 1u);
        CHECK_FALSE(register_class(bindings, main, lifecycle_type, "ReplacementController", owner));

        thread_state = PyEval_SaveThread();
        const bool stopped = tc_world_controller_instance_stop(instance, &error.value);
        const bool destroyed = tc_world_controller_instance_destroy(&instance, &error.value);
        PyEval_RestoreThread(thread_state);

        CHECK(stopped);
        CHECK(destroyed);
        CHECK(instance == nullptr);
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
        error.text[0] = '\0';
        thread_state = PyEval_SaveThread();
        tc_world_controller_instance* failed_construction =
            tc_world_controller_instance_create(constructor_failure_type, &error.value);
        PyEval_RestoreThread(thread_state);
        CHECK(failed_construction == nullptr);
        CHECK(std::string(error.text).find("injected Python constructor failure") != std::string::npos);
        CHECK_EQ(tc_runtime_type_registry_instance_count(constructor_failure_type), 0u);

        constexpr const char* start_failure_type = "PythonStartFailureController";
        REQUIRE(register_class(bindings, main, start_failure_type, "StartFailureController", owner));
        error.text[0] = '\0';
        thread_state = PyEval_SaveThread();
        tc_world_controller_instance* failed_start =
            tc_world_controller_instance_create(start_failure_type, &error.value);
        const bool start_result = tc_world_controller_instance_start(failed_start, test_context(), &error.value);
        PyEval_RestoreThread(thread_state);
        REQUIRE(failed_start != nullptr);
        CHECK_FALSE(start_result);
        CHECK(std::string(error.text).find("injected Python start failure") != std::string::npos);

        thread_state = PyEval_SaveThread();
        const bool failure_destroyed = tc_world_controller_instance_destroy(&failed_start, &error.value);
        PyEval_RestoreThread(thread_state);
        CHECK(failure_destroyed);
        CHECK(failed_start == nullptr);

        nb::list events = nb::cast<nb::list>(main.attr("events"));
        REQUIRE_EQ(nb::len(events), 8u);
        CHECK_EQ(nb::cast<std::string>(events[4]), std::string("construct:failure"));
        CHECK_EQ(nb::cast<std::string>(events[5]), std::string("start:failure"));
        CHECK_EQ(nb::cast<std::string>(events[6]), std::string("stop:failure"));
        CHECK_EQ(nb::cast<std::string>(events[7]), std::string("destroy:failure"));

        CHECK_EQ(tc_runtime_type_registry_unregister_owner(owner), 3u);
        tc_runtime_type_registry_clear();
    }

    Py_Finalize();
}
