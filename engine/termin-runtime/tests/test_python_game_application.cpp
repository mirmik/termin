#include "guard_main.h"

GUARD_TEST_MAIN();

#include <Python.h>

#include <string>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <inspect/tc_runtime_type_registry.h>
#include <termin/runtime/game_application.h>

namespace {

    namespace nb = nanobind;

    struct ErrorBuffer {
        char text[1024] = {};
        tc_game_application_error_v1 value{sizeof(tc_game_application_error_v1), text, sizeof(text)};
    };

    bool register_class(
        nb::module_& bindings, nb::module_& main, const char* type_name, const char* class_name, const char* owner) {
        return nb::cast<bool>(
            bindings.attr("_register_game_application")(type_name, main.attr(class_name), owner, nb::none()));
    }

    std::string event_at(nb::module_& main, size_t index) {
        nb::list events = nb::cast<nb::list>(main.attr("events"));
        return nb::cast<std::string>(events[index]);
    }

} // namespace

TEST_CASE("Python GameApplication factory owns objects and contains lifecycle exceptions") {
    tc_runtime_type_registry_clear();
    REQUIRE_FALSE(Py_IsInitialized());
    Py_Initialize();

    {
        nb::module_ main = nb::module_::import_("__main__");
        nb::module_ sys = nb::module_::import_("sys");
        sys.attr("path").attr("insert")(0, TERMIN_RUNTIME_PYTHON_MODULE_DIR);
        nb::module_ bindings = nb::module_::import_("_runtime_native");

        const char* script = R"PY(
events = []

class LifecycleApplication:
    version = 1

    def __init__(self):
        events.append("construct:1")

    def start(self):
        events.append("start:1")

    def stop(self):
        events.append("stop:1")

    def __del__(self):
        events.append("destroy:1")

class ReplacementApplication:
    version = 2

    def start(self):
        pass

    def stop(self):
        pass

class ConstructorFailureApplication:
    def __init__(self):
        raise RuntimeError("injected Python constructor failure")

    def start(self):
        pass

    def stop(self):
        pass

class StartFailureApplication:
    def __init__(self):
        events.append("construct:failure")

    def start(self):
        events.append("start:failure")
        raise RuntimeError("injected Python start failure")

    def stop(self):
        events.append("stop:failure")

    def __del__(self):
        events.append("destroy:failure")
)PY";
        REQUIRE_EQ(PyRun_SimpleString(script), 0);

        constexpr const char* owner = "termin-runtime-python-test";
        constexpr const char* lifecycle_type = "PythonLifecycleApplication";
        REQUIRE(register_class(bindings, main, lifecycle_type, "LifecycleApplication", owner));

        ErrorBuffer error;
        tc_game_application_instance* instance = nullptr;

        PyThreadState* thread_state = PyEval_SaveThread();
        instance = tc_game_application_instance_create(lifecycle_type, &error.value);
        const bool started = tc_game_application_instance_start(instance, &error.value);
        const bool unload_while_live = tc_runtime_type_registry_prepare_owner_unload(owner, nullptr);
        PyEval_RestoreThread(thread_state);

        REQUIRE(instance != nullptr);
        CHECK(started);
        CHECK_FALSE(unload_while_live);
        CHECK_EQ(tc_runtime_type_registry_instance_count(lifecycle_type), 1u);
        CHECK_FALSE(register_class(bindings, main, lifecycle_type, "ReplacementApplication", owner));

        thread_state = PyEval_SaveThread();
        const bool stopped = tc_game_application_instance_stop(instance, &error.value);
        const bool destroyed = tc_game_application_instance_destroy(&instance, &error.value);
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

        CHECK(register_class(bindings, main, lifecycle_type, "ReplacementApplication", owner));
        nb::dict replacement_info = nb::cast<nb::dict>(bindings.attr("_game_application_type_info")(lifecycle_type));
        CHECK(nb::cast<int>(replacement_info["python_class"].attr("version")) == 2);

        constexpr const char* constructor_failure_type = "PythonConstructorFailureApplication";
        REQUIRE(register_class(bindings, main, constructor_failure_type, "ConstructorFailureApplication", owner));
        error.text[0] = '\0';
        thread_state = PyEval_SaveThread();
        tc_game_application_instance* failed_construction =
            tc_game_application_instance_create(constructor_failure_type, &error.value);
        PyEval_RestoreThread(thread_state);
        CHECK(failed_construction == nullptr);
        CHECK(std::string(error.text).find("injected Python constructor failure") != std::string::npos);
        CHECK_EQ(tc_runtime_type_registry_instance_count(constructor_failure_type), 0u);

        constexpr const char* start_failure_type = "PythonStartFailureApplication";
        REQUIRE(register_class(bindings, main, start_failure_type, "StartFailureApplication", owner));
        error.text[0] = '\0';
        thread_state = PyEval_SaveThread();
        tc_game_application_instance* failed_start =
            tc_game_application_instance_create(start_failure_type, &error.value);
        const bool start_result = tc_game_application_instance_start(failed_start, &error.value);
        PyEval_RestoreThread(thread_state);
        REQUIRE(failed_start != nullptr);
        CHECK_FALSE(start_result);
        CHECK(std::string(error.text).find("injected Python start failure") != std::string::npos);

        thread_state = PyEval_SaveThread();
        const bool failure_destroyed = tc_game_application_instance_destroy(&failed_start, &error.value);
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
