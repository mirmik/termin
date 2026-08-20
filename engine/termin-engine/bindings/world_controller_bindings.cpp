#include "world_controller_bindings.hpp"

#include <Python.h>

#include <exception>
#include <string>
#include <utility>

#include <nanobind/stl/string.h>

#include <inspect/tc_runtime_type_registry.h>
#include <tcbase/tc_log.hpp>
#include <termin/engine/world_controller.hpp>
#include <termin/tc_scene.hpp>

namespace termin::python {

    namespace nb = nanobind;

    namespace {

        constexpr const char* kPythonClassProjectionBinding = "termin.python.world_controller_class_projection";

        struct PythonWorldControllerFactoryContext {
            nb::object cls;
            std::string type_name;
        };

        struct PythonWorldControllerObject {
            nb::object value;
            std::string type_name;
            nb::object context_value;
            tc_world_context* context = nullptr;
        };

        void set_error(tc_world_controller_error_v1* error, const std::string& message) {
            tc_world_controller_set_error(error, message.c_str());
        }

        void report_python_error(const nb::python_error& exception,
                                 const std::string& type_name,
                                 const char* operation,
                                 tc_world_controller_error_v1* error) {
            const std::string message =
                "Python WorldController '" + type_name + "' " + operation + " failed: " + exception.what();
            set_error(error, message);
            tc::Log::error(exception, "[PythonWorldController] type='%s' operation='%s'", type_name.c_str(), operation);
            PyErr_Clear();
        }

        void report_native_error(const std::exception& exception,
                                 const std::string& type_name,
                                 const char* operation,
                                 tc_world_controller_error_v1* error) {
            const std::string message =
                "Python WorldController '" + type_name + "' " + operation + " failed: " + exception.what();
            set_error(error, message);
            tc::Log::error(exception, "[PythonWorldController] type='%s' operation='%s'", type_name.c_str(), operation);
        }

        void destroy_python_factory_context(void* context) {
            if (!context) {
                return;
            }
            nb::gil_scoped_acquire gil;
            delete static_cast<PythonWorldControllerFactoryContext*>(context);
        }

        void destroy_python_controller(void* object) {
            if (!object) {
                return;
            }
            nb::gil_scoped_acquire gil;
            delete static_cast<PythonWorldControllerObject*>(object);
        }

        bool invoke_lifecycle(PythonWorldControllerObject* controller,
                              nb::handle context,
                              tc_world_controller_error_v1* error,
                              const char* operation) {
            try {
                nb::object result = controller->value.attr(operation)(context);
                if (!result.is_none()) {
                    const std::string message =
                        "Python WorldController '" + controller->type_name + "' " + operation + " must return None";
                    set_error(error, message);
                    tc::Log::error("[PythonWorldController] %s", message.c_str());
                    return false;
                }
                return true;
            } catch (const nb::python_error& exception) {
                report_python_error(exception, controller->type_name, operation, error);
            } catch (const std::exception& exception) {
                report_native_error(exception, controller->type_name, operation, error);
            } catch (...) {
                const std::string message = "Python WorldController '" + controller->type_name + "' " + operation +
                                            " failed with an unknown native exception";
                set_error(error, message);
                tc::Log::error("[PythonWorldController] %s", message.c_str());
            }
            return false;
        }

        bool start_python_controller(void* object,
                                     tc_world_context* context,
                                     tc_world_controller_error_v1* error) {
            auto* controller = static_cast<PythonWorldControllerObject*>(object);
            if (!controller || !context || controller->context) {
                set_error(error, "Python WorldController start received invalid lifecycle arguments");
                tc::Log::error("[PythonWorldController] start received invalid lifecycle arguments");
                return false;
            }

            nb::gil_scoped_acquire gil;
            try {
                controller->context_value = nb::cast(WorldContext(context));
                controller->context = context;
                return invoke_lifecycle(controller, controller->context_value, error, "start");
            } catch (const nb::python_error& exception) {
                report_python_error(exception, controller->type_name, "WorldContext construction", error);
            } catch (const std::exception& exception) {
                report_native_error(exception, controller->type_name, "WorldContext construction", error);
            } catch (...) {
                const std::string message = "Python WorldController '" + controller->type_name +
                                            "' WorldContext construction failed with an unknown native exception";
                set_error(error, message);
                tc::Log::error("[PythonWorldController] %s", message.c_str());
            }
            return false;
        }

        bool stop_python_controller(void* object,
                                    tc_world_context* context,
                                    tc_world_controller_error_v1* error) {
            auto* controller = static_cast<PythonWorldControllerObject*>(object);
            if (!controller || !context || controller->context != context) {
                set_error(error, "Python WorldController stop received a mismatched WorldContext");
                tc::Log::error("[PythonWorldController] stop received a mismatched WorldContext");
                return false;
            }

            nb::gil_scoped_acquire gil;
            if (!controller->context_value.is_valid()) {
                set_error(error, "Python WorldController stop received no published WorldContext");
                tc::Log::error("[PythonWorldController] stop received no published WorldContext");
                return false;
            }
            return invoke_lifecycle(controller, controller->context_value, error, "stop");
        }

        const tc_world_controller_ops_v1 kPythonWorldControllerOps = {
            sizeof(tc_world_controller_ops_v1),
            TC_WORLD_CONTROLLER_OPS_ABI_VERSION,
            &start_python_controller,
            &stop_python_controller,
        };

        bool create_python_controller(void* context, const void* request_raw, void* result_raw) {
            auto* factory = static_cast<PythonWorldControllerFactoryContext*>(context);
            const auto* request = static_cast<const tc_world_controller_factory_request_v1*>(request_raw);
            auto* result = static_cast<tc_world_controller_factory_result_v1*>(result_raw);
            if (!factory || !request || request->struct_size < sizeof(tc_world_controller_factory_request_v1) ||
                !result || result->struct_size < sizeof(tc_world_controller_factory_result_v1)) {
                tc_world_controller_set_error(request ? request->error : nullptr,
                                              "Python WorldController factory received an incompatible request");
                tc::Log::error("[PythonWorldController] factory received an incompatible request or result");
                return false;
            }

            nb::gil_scoped_acquire gil;
            try {
                nb::object value = factory->cls();
                auto* object = new PythonWorldControllerObject{std::move(value), factory->type_name, nb::object(), nullptr};
                result->struct_size = sizeof(tc_world_controller_factory_result_v1);
                result->object = object;
                result->destroy = &destroy_python_controller;
                result->ops = &kPythonWorldControllerOps;
                return true;
            } catch (const nb::python_error& exception) {
                report_python_error(exception, factory->type_name, "construction", request->error);
            } catch (const std::exception& exception) {
                report_native_error(exception, factory->type_name, "construction", request->error);
            } catch (...) {
                const std::string message = "Python WorldController '" + factory->type_name +
                                            "' construction failed with an unknown native exception";
                set_error(request->error, message);
                tc::Log::error("[PythonWorldController] %s", message.c_str());
            }
            return false;
        }

        PythonWorldControllerFactoryContext* python_factory_context(const char* type_name) {
            if (!type_name) {
                return nullptr;
            }
            return static_cast<PythonWorldControllerFactoryContext*>(
                tc_runtime_type_registry_get_binding(type_name, kPythonClassProjectionBinding));
        }

        nb::object project_controller(const WorldControllerRef& controller) {
            nb::gil_scoped_acquire gil;
            const char* type_name = controller.type_name();
            if (!type_name || !python_factory_context(type_name)) {
                return nb::cast(controller);
            }

            auto* object = static_cast<PythonWorldControllerObject*>(controller.object());
            if (!object || !object->value.is_valid()) {
                throw std::runtime_error("live Python WorldController has no project object");
            }
            PyObject* proxy = PyWeakref_NewProxy(object->value.ptr(), nullptr);
            if (!proxy) {
                throw nb::python_error();
            }
            return nb::steal<nb::object>(proxy);
        }

        bool class_has_callable(nb::handle cls, const char* method_name, const std::string& type_name) {
            PyObject* method = PyObject_GetAttrString(cls.ptr(), method_name);
            if (!method) {
                PyErr_Clear();
                tc::Log::error(
                    "[PythonWorldController] type='%s' has no required '%s' method", type_name.c_str(), method_name);
                return false;
            }
            const bool callable = PyCallable_Check(method) != 0;
            Py_DECREF(method);
            if (!callable) {
                tc::Log::error(
                    "[PythonWorldController] type='%s' attribute '%s' is not callable", type_name.c_str(), method_name);
            }
            return callable;
        }

        bool register_python_controller(const std::string& type_name,
                                        nb::object cls,
                                        const std::string& owner,
                                        nb::object parent) {
            if (type_name.empty() || owner.empty()) {
                tc::Log::error("[PythonWorldController] type and owner must be non-empty");
                return false;
            }
            if (!PyType_Check(cls.ptr())) {
                tc::Log::error("[PythonWorldController] '%s' registration value is not a class", type_name.c_str());
                return false;
            }
            if (!class_has_callable(cls, "start", type_name) || !class_has_callable(cls, "stop", type_name)) {
                return false;
            }
            if (!tc_world_controller_registry_init()) {
                tc::Log::error("[PythonWorldController] failed to initialize the native controller registry");
                return false;
            }

            const char* existing_owner = tc_runtime_type_registry_get_owner(type_name.c_str());
            const bool existing_controller = tc_world_controller_type_is_registered(type_name.c_str());
            auto* existing_python_context = python_factory_context(type_name.c_str());
            if (tc_runtime_type_registry_has_type(type_name.c_str()) &&
                (!existing_controller || !existing_python_context)) {
                tc::Log::error("[PythonWorldController] refusing to replace non-Python type '%s'", type_name.c_str());
                return false;
            }
            if (existing_controller && (!existing_owner || owner != existing_owner)) {
                tc::Log::error("[PythonWorldController] refusing replacement of type '%s' owned by '%s'",
                               type_name.c_str(),
                               existing_owner ? existing_owner : "<none>");
                return false;
            }

            std::string parent_storage = TC_WORLD_CONTROLLER_ROOT_TYPE;
            if (!parent.is_none()) {
                parent_storage = nb::cast<std::string>(parent);
                if (parent_storage.empty()) {
                    tc::Log::error("[PythonWorldController] parent for '%s' must be non-empty", type_name.c_str());
                    return false;
                }
            }

            auto* factory_context = new PythonWorldControllerFactoryContext{std::move(cls), type_name};
            tc_runtime_owned_factory factory = tc_runtime_owned_factory_make(
                &create_python_controller, factory_context, &destroy_python_factory_context);
            WorldControllerTypeDescriptorBuilder descriptor(
                type_name.c_str(), owner.c_str(), parent_storage.c_str(), factory, false, existing_controller);
            descriptor.runtime_binding(kPythonClassProjectionBinding, factory_context, nullptr);
            return descriptor.commit();
        }

        bool unregister_python_controller(const std::string& type_name) {
            if (!tc_world_controller_type_is_registered(type_name.c_str())) {
                return true;
            }
            if (!python_factory_context(type_name.c_str())) {
                tc::Log::error("[PythonWorldController] refusing Python unregister for native type '%s'",
                               type_name.c_str());
                return false;
            }
            return tc_runtime_type_registry_unregister_type_with_context(type_name.c_str(), nullptr);
        }

        nb::object type_info(const std::string& type_name) {
            if (!tc_world_controller_type_is_registered(type_name.c_str())) {
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
            result["abstract"] = nb::bool_(tc_world_controller_type_is_abstract(type_name.c_str()));
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
            const size_t count = tc_world_controller_type_count();
            for (size_t index = 0; index < count; ++index) {
                const char* type_name = tc_world_controller_type_at(index);
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

    void bind_world_controller(nb::module_& module) {
        nb::class_<WorldContext>(module, "WorldContext")
            .def_prop_ro("valid", &WorldContext::valid)
            .def_prop_ro(
                "controller",
                [](const WorldContext& context) -> nb::object {
                    auto controller = context.controller();
                    return controller ? project_controller(*controller) : nb::none();
                },
                "The optional project controller; Python controllers are exposed as weak proxies.")
            .def("__bool__", &WorldContext::valid)
            .def("__eq__", [](const WorldContext& self, const WorldContext& other) { return self == other; });

        nb::class_<WorldControllerRef>(module, "WorldControllerRef")
            .def_prop_ro("valid", &WorldControllerRef::valid)
            .def_prop_ro(
                "type_name",
                [](const WorldControllerRef& controller) -> nb::object {
                    const char* type_name = controller.type_name();
                    return type_name ? nb::cast(type_name) : nb::none();
                })
            .def("__bool__", &WorldControllerRef::valid);

        nb::class_<WorldControllerInstance>(module, "WorldControllerInstance")
            .def_prop_ro("valid", &WorldControllerInstance::valid)
            .def_prop_ro(
                "type_name",
                [](const WorldControllerInstance& instance) -> nb::object {
                    const char* type_name = instance.type_name();
                    return type_name ? nb::cast(type_name) : nb::none();
                })
            .def("__bool__", &WorldControllerInstance::valid);

        module.def(
            "create_world_controller",
            [](const std::string& type_name) {
                std::string error;
                WorldControllerInstance instance = WorldControllerInstance::create(type_name.c_str(), error);
                if (!instance) {
                    throw std::runtime_error(error);
                }
                return instance;
            },
            nb::arg("type_name"),
            "Create one move-only WorldController owner without starting it.");

        module.def(
            "world_context",
            [](const TcSceneRef& scene) { return WorldContext::from_scene(scene.handle()); },
            nb::arg("scene"),
            "Return the live WorldContext for a bound runtime scene, or an invalid handle.");
        module.def(
            "require_world_context",
            [](const TcSceneRef& scene, const std::string& consumer) {
                return WorldContext::require_from_scene(scene.handle(), consumer.c_str());
            },
            nb::arg("scene"),
            nb::arg("consumer") = "Python runtime component",
            "Return a bound scene's WorldContext or raise with an actionable error.");

        module.def("_bootstrap_world_controller_registry", &tc_world_controller_registry_init);
        module.def("_register_world_controller",
                   &register_python_controller,
                   nb::arg("type_name"),
                   nb::arg("cls"),
                   nb::arg("owner"),
                   nb::arg("parent") = nb::none());
        module.def("_unregister_world_controller", &unregister_python_controller, nb::arg("type_name"));
        module.def("_world_controller_type_info", &type_info, nb::arg("type_name"));
        module.def("_python_world_controller_types", &python_types_for_owner, nb::arg("owner") = nb::none());
    }

} // namespace termin::python
