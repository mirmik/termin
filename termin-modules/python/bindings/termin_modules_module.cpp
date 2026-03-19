#include <nanobind/nanobind.h>
#include <nanobind/stl/filesystem.h>
#include <nanobind/stl/function.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "termin_modules/module_cpp_backend.hpp"
#include "termin_modules/module_python_backend.hpp"
#include "termin_modules/module_runtime.hpp"

namespace nb = nanobind;
using namespace termin_modules;

NB_MODULE(_termin_modules_native, m) {
    nb::enum_<ModuleKind>(m, "ModuleKind")
        .value("Cpp", ModuleKind::Cpp)
        .value("Python", ModuleKind::Python);

    nb::enum_<ModuleState>(m, "ModuleState")
        .value("Discovered", ModuleState::Discovered)
        .value("Loaded", ModuleState::Loaded)
        .value("Failed", ModuleState::Failed)
        .value("Unloaded", ModuleState::Unloaded);

    nb::enum_<ModuleEventKind>(m, "ModuleEventKind")
        .value("Discovered", ModuleEventKind::Discovered)
        .value("Loading", ModuleEventKind::Loading)
        .value("Loaded", ModuleEventKind::Loaded)
        .value("Unloading", ModuleEventKind::Unloading)
        .value("Unloaded", ModuleEventKind::Unloaded)
        .value("Reloading", ModuleEventKind::Reloading)
        .value("Failed", ModuleEventKind::Failed);

    nb::class_<ModuleEvent>(m, "ModuleEvent")
        .def_ro("kind", &ModuleEvent::kind)
        .def_ro("module_id", &ModuleEvent::module_id)
        .def_ro("message", &ModuleEvent::message);

    nb::class_<ModuleEnvironment>(m, "ModuleEnvironment")
        .def(nb::init<>())
        .def_prop_rw(
            "sdk_prefix",
            [](const ModuleEnvironment& self) { return self.sdk_prefix.string(); },
            [](ModuleEnvironment& self, const std::string& value) { self.sdk_prefix = value; }
        )
        .def_prop_rw(
            "cmake_prefix_path",
            [](const ModuleEnvironment& self) { return self.cmake_prefix_path.string(); },
            [](ModuleEnvironment& self, const std::string& value) { self.cmake_prefix_path = value; }
        )
        .def_prop_rw(
            "lib_dir",
            [](const ModuleEnvironment& self) { return self.lib_dir.string(); },
            [](ModuleEnvironment& self, const std::string& value) { self.lib_dir = value; }
        )
        .def_prop_rw(
            "project_root",
            [](const ModuleEnvironment& self) { return self.project_root.string(); },
            [](ModuleEnvironment& self, const std::string& value) { self.project_root = value; }
        )
        .def_prop_rw(
            "project_venv_path",
            [](const ModuleEnvironment& self) { return self.project_venv_path.string(); },
            [](ModuleEnvironment& self, const std::string& value) { self.project_venv_path = value; }
        )
        .def_rw("python_executable", &ModuleEnvironment::python_executable)
        .def_rw("use_project_venv", &ModuleEnvironment::use_project_venv)
        .def_rw("allow_python_package_install", &ModuleEnvironment::allow_python_package_install);

    nb::class_<ModuleSpec>(m, "ModuleSpec")
        .def_ro("id", &ModuleSpec::id)
        .def_ro("kind", &ModuleSpec::kind)
        .def_ro("descriptor_path", &ModuleSpec::descriptor_path)
        .def_ro("dependencies", &ModuleSpec::dependencies)
        .def_ro("components", &ModuleSpec::components);

    nb::class_<ModuleRecord>(m, "ModuleRecord")
        .def_prop_ro("id", [](const ModuleRecord& self) { return self.spec.id; })
        .def_prop_ro("kind", [](const ModuleRecord& self) { return self.spec.kind; })
        .def_prop_ro("descriptor_path", [](const ModuleRecord& self) { return self.spec.descriptor_path; })
        .def_prop_ro("dependencies", [](const ModuleRecord& self) { return self.spec.dependencies; })
        .def_prop_ro("components", [](const ModuleRecord& self) { return self.spec.components; })
        .def_ro("state", &ModuleRecord::state)
        .def_ro("error_message", &ModuleRecord::error_message)
        .def_ro("diagnostics", &ModuleRecord::diagnostics)
        .def_prop_ro("clean_command", [](const ModuleRecord& self) -> std::string {
            auto config = std::dynamic_pointer_cast<CppModuleConfig>(self.spec.config);
            return config ? config->clean_command : "";
        });

    nb::class_<CppModuleBackend>(m, "CppModuleBackend")
        .def(nb::init<>());
    nb::class_<PythonModuleBackend>(m, "PythonModuleBackend")
        .def(nb::init<>());

    nb::class_<ModuleRuntime>(m, "ModuleRuntime")
        .def(nb::init<>())
        .def("set_environment", &ModuleRuntime::set_environment, nb::arg("environment"))
        .def("register_cpp_backend", [](ModuleRuntime& self, const CppModuleBackend&) {
            self.register_backend(std::make_shared<CppModuleBackend>());
        })
        .def("register_python_backend", [](ModuleRuntime& self, const PythonModuleBackend&) {
            self.register_backend(std::make_shared<PythonModuleBackend>());
        })
        .def("discover", &ModuleRuntime::discover, nb::arg("project_root"))
        .def("load_all", &ModuleRuntime::load_all)
        .def("load_module", &ModuleRuntime::load_module, nb::arg("module_id"))
        .def("unload_module", &ModuleRuntime::unload_module, nb::arg("module_id"))
        .def("reload_module", &ModuleRuntime::reload_module, nb::arg("module_id"))
        .def("clean_module", &ModuleRuntime::clean_module, nb::arg("module_id"))
        .def("rebuild_module", &ModuleRuntime::rebuild_module, nb::arg("module_id"))
        .def("list", [](const ModuleRuntime& self) {
            nb::list result;
            for (const ModuleRecord* record : self.list()) {
                result.append(nb::cast(record, nb::rv_policy::reference));
            }
            return result;
        })
        .def("find", [](const ModuleRuntime& self, const std::string& module_id) -> const ModuleRecord* {
            return self.find(module_id);
        }, nb::arg("module_id"), nb::rv_policy::reference)
        .def_prop_ro("last_error", &ModuleRuntime::last_error)
        .def("set_event_callback", [](ModuleRuntime& self, nb::callable callback) {
            self.set_event_callback([callback](const ModuleEvent& event) {
                nb::gil_scoped_acquire gil;
                callback(event);
            });
        }, nb::arg("callback"));
}
