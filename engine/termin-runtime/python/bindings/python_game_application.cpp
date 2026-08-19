#include "python_game_application.hpp"

#include <Python.h>

#include <exception>
#include <string>
#include <utility>

#include <nanobind/stl/string.h>

#include <inspect/tc_runtime_type_registry.h>
#include <tcbase/tc_log.hpp>
#include <termin/runtime/game_application.hpp>

namespace termin::runtime::python {

    namespace nb = nanobind;

    namespace {

        constexpr const char* kPythonClassProjectionBinding = "termin.python.game_application_class_projection";

        struct PythonGameApplicationFactoryContext {
            nb::object cls;
            std::string type_name;
        };

        struct PythonGameApplicationObject {
            nb::object value;
            std::string type_name;
        };

        void set_error(tc_game_application_error_v1* error, const std::string& message) {
            tc_game_application_set_error(error, message.c_str());
        }

        void report_python_error(const nb::python_error& exception,
                                 const std::string& type_name,
                                 const char* operation,
                                 tc_game_application_error_v1* error) {
            const std::string message =
                "Python GameApplication '" + type_name + "' " + operation + " failed: " + exception.what();
            set_error(error, message);
            tc::Log::error(exception, "[PythonGameApplication] type='%s' operation='%s'", type_name.c_str(), operation);
            PyErr_Clear();
        }

        void report_native_error(const std::exception& exception,
                                 const std::string& type_name,
                                 const char* operation,
                                 tc_game_application_error_v1* error) {
            const std::string message =
                "Python GameApplication '" + type_name + "' " + operation + " failed: " + exception.what();
            set_error(error, message);
            tc::Log::error(exception, "[PythonGameApplication] type='%s' operation='%s'", type_name.c_str(), operation);
        }

        void destroy_python_factory_context(void* context) {
            if (!context) {
                return;
            }
            nb::gil_scoped_acquire gil;
            delete static_cast<PythonGameApplicationFactoryContext*>(context);
        }

        void destroy_python_application(void* object) {
            if (!object) {
                return;
            }
            nb::gil_scoped_acquire gil;
            delete static_cast<PythonGameApplicationObject*>(object);
        }

        bool invoke_lifecycle(void* object, tc_game_application_error_v1* error, const char* operation) {
            auto* application = static_cast<PythonGameApplicationObject*>(object);
            if (!application) {
                set_error(error, "Python GameApplication lifecycle received a null object");
                tc::Log::error("[PythonGameApplication] operation='%s' received a null object", operation);
                return false;
            }

            nb::gil_scoped_acquire gil;
            try {
                nb::object result = application->value.attr(operation)();
                if (!result.is_none()) {
                    const std::string message =
                        "Python GameApplication '" + application->type_name + "' " + operation + " must return None";
                    set_error(error, message);
                    tc::Log::error("[PythonGameApplication] %s", message.c_str());
                    return false;
                }
                return true;
            } catch (const nb::python_error& exception) {
                report_python_error(exception, application->type_name, operation, error);
            } catch (const std::exception& exception) {
                report_native_error(exception, application->type_name, operation, error);
            } catch (...) {
                const std::string message = "Python GameApplication '" + application->type_name + "' " + operation +
                                            " failed with an unknown native exception";
                set_error(error, message);
                tc::Log::error("[PythonGameApplication] %s", message.c_str());
            }
            return false;
        }

        bool start_python_application(void* object, tc_game_application_error_v1* error) {
            return invoke_lifecycle(object, error, "start");
        }

        bool stop_python_application(void* object, tc_game_application_error_v1* error) {
            return invoke_lifecycle(object, error, "stop");
        }

        const tc_game_application_ops_v1 kPythonGameApplicationOps = {
            sizeof(tc_game_application_ops_v1),
            TC_GAME_APPLICATION_OPS_ABI_VERSION,
            &start_python_application,
            &stop_python_application,
        };

        bool create_python_application(void* context, const void* request_raw, void* result_raw) {
            auto* factory = static_cast<PythonGameApplicationFactoryContext*>(context);
            const auto* request = static_cast<const tc_game_application_factory_request_v1*>(request_raw);
            auto* result = static_cast<tc_game_application_factory_result_v1*>(result_raw);
            if (!factory || !request || request->struct_size < sizeof(tc_game_application_factory_request_v1) ||
                !result || result->struct_size < sizeof(tc_game_application_factory_result_v1)) {
                tc_game_application_set_error(request ? request->error : nullptr,
                                              "Python GameApplication factory received an incompatible request");
                tc::Log::error("[PythonGameApplication] factory received an incompatible request or result");
                return false;
            }

            nb::gil_scoped_acquire gil;
            try {
                nb::object value = factory->cls();
                auto* object = new PythonGameApplicationObject{std::move(value), factory->type_name};
                result->struct_size = sizeof(tc_game_application_factory_result_v1);
                result->object = object;
                result->destroy = &destroy_python_application;
                result->ops = &kPythonGameApplicationOps;
                return true;
            } catch (const nb::python_error& exception) {
                report_python_error(exception, factory->type_name, "construction", request->error);
            } catch (const std::exception& exception) {
                report_native_error(exception, factory->type_name, "construction", request->error);
            } catch (...) {
                const std::string message = "Python GameApplication '" + factory->type_name +
                                            "' construction failed with an unknown native exception";
                set_error(request->error, message);
                tc::Log::error("[PythonGameApplication] %s", message.c_str());
            }
            return false;
        }

        PythonGameApplicationFactoryContext* python_factory_context(const char* type_name) {
            if (!type_name) {
                return nullptr;
            }
            return static_cast<PythonGameApplicationFactoryContext*>(
                tc_runtime_type_registry_get_binding(type_name, kPythonClassProjectionBinding));
        }

        bool class_has_callable(nb::handle cls, const char* method_name, const std::string& type_name) {
            PyObject* method = PyObject_GetAttrString(cls.ptr(), method_name);
            if (!method) {
                PyErr_Clear();
                tc::Log::error(
                    "[PythonGameApplication] type='%s' has no required '%s' method", type_name.c_str(), method_name);
                return false;
            }
            const bool callable = PyCallable_Check(method) != 0;
            Py_DECREF(method);
            if (!callable) {
                tc::Log::error(
                    "[PythonGameApplication] type='%s' attribute '%s' is not callable", type_name.c_str(), method_name);
            }
            return callable;
        }

        bool register_python_application(const std::string& type_name,
                                         nb::object cls,
                                         const std::string& owner,
                                         nb::object parent) {
            if (type_name.empty() || owner.empty()) {
                tc::Log::error("[PythonGameApplication] type and owner must be non-empty");
                return false;
            }
            if (!PyType_Check(cls.ptr())) {
                tc::Log::error("[PythonGameApplication] '%s' registration value is not a class", type_name.c_str());
                return false;
            }
            if (!class_has_callable(cls, "start", type_name) || !class_has_callable(cls, "stop", type_name)) {
                return false;
            }
            if (!tc_game_application_registry_init()) {
                tc::Log::error("[PythonGameApplication] failed to initialize the native application registry");
                return false;
            }

            const char* existing_owner = tc_runtime_type_registry_get_owner(type_name.c_str());
            const bool existing_application = tc_game_application_type_is_registered(type_name.c_str());
            auto* existing_python_context = python_factory_context(type_name.c_str());
            if (tc_runtime_type_registry_has_type(type_name.c_str()) &&
                (!existing_application || !existing_python_context)) {
                tc::Log::error("[PythonGameApplication] refusing to replace non-Python type '%s'", type_name.c_str());
                return false;
            }
            if (existing_application && (!existing_owner || owner != existing_owner)) {
                tc::Log::error("[PythonGameApplication] refusing replacement of type '%s' owned by '%s'",
                               type_name.c_str(),
                               existing_owner ? existing_owner : "<none>");
                return false;
            }

            std::string parent_storage = TC_GAME_APPLICATION_ROOT_TYPE;
            if (!parent.is_none()) {
                parent_storage = nb::cast<std::string>(parent);
                if (parent_storage.empty()) {
                    tc::Log::error("[PythonGameApplication] parent for '%s' must be non-empty", type_name.c_str());
                    return false;
                }
            }

            auto* factory_context = new PythonGameApplicationFactoryContext{std::move(cls), type_name};
            tc_runtime_owned_factory factory = tc_runtime_owned_factory_make(
                &create_python_application, factory_context, &destroy_python_factory_context);
            GameApplicationTypeDescriptorBuilder descriptor(
                type_name.c_str(), owner.c_str(), parent_storage.c_str(), factory, false, existing_application);
            descriptor.runtime_binding(kPythonClassProjectionBinding, factory_context, nullptr);
            return descriptor.commit();
        }

        bool unregister_python_application(const std::string& type_name) {
            if (!tc_game_application_type_is_registered(type_name.c_str())) {
                return true;
            }
            if (!python_factory_context(type_name.c_str())) {
                tc::Log::error("[PythonGameApplication] refusing Python unregister for native type '%s'",
                               type_name.c_str());
                return false;
            }
            return tc_runtime_type_registry_unregister_type_with_context(type_name.c_str(), nullptr);
        }

        nb::object type_info(const std::string& type_name) {
            if (!tc_game_application_type_is_registered(type_name.c_str())) {
                return nb::none();
            }
            nb::dict result;
            result["name"] = nb::str(type_name.c_str());
            const char* owner = tc_runtime_type_registry_get_owner(type_name.c_str());
            const char* parent = tc_runtime_type_registry_get_parent(type_name.c_str());
            if (owner) {
                result["owner"] = nb::str(owner);
            } else {
                result["owner"] = nb::none();
            }
            if (parent) {
                result["parent"] = nb::str(parent);
            } else {
                result["parent"] = nb::none();
            }
            result["abstract"] = nb::bool_(tc_game_application_type_is_abstract(type_name.c_str()));
            auto* context = python_factory_context(type_name.c_str());
            if (context) {
                result["python_class"] = context->cls;
            } else {
                result["python_class"] = nb::none();
            }
            result["instance_count"] = nb::int_(tc_runtime_type_registry_instance_count(type_name.c_str()));
            return result;
        }

        nb::list python_types_for_owner(nb::object owner) {
            nb::list result;
            std::string owner_name;
            if (!owner.is_none()) {
                owner_name = nb::cast<std::string>(owner);
            }
            const size_t count = tc_game_application_type_count();
            for (size_t index = 0; index < count; ++index) {
                const char* type_name = tc_game_application_type_at(index);
                if (!type_name || !python_factory_context(type_name)) {
                    continue;
                }
                const char* type_owner = tc_runtime_type_registry_get_owner(type_name);
                if (!owner.is_none() && (!type_owner || owner_name != type_owner)) {
                    continue;
                }
                result.append(nb::str(type_name));
            }
            return result;
        }

    } // namespace

    void bind_game_application(nb::module_& module) {
        module.def("_bootstrap_game_application_registry", &tc_game_application_registry_init);
        module.def("_register_game_application",
                   &register_python_application,
                   nb::arg("type_name"),
                   nb::arg("cls"),
                   nb::arg("owner"),
                   nb::arg("parent") = nb::none());
        module.def("_unregister_game_application", &unregister_python_application, nb::arg("type_name"));
        module.def("_game_application_type_info", &type_info, nb::arg("type_name"));
        module.def("_python_game_application_types", &python_types_for_owner, nb::arg("owner") = nb::none());
    }

} // namespace termin::runtime::python
