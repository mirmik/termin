#include "termin_modules/module_python_backend.hpp"

#include <Python.h>

#include <sstream>

namespace termin_modules {
namespace {

bool append_sys_path(const std::filesystem::path& path, std::string& error) {
    PyObject* sys_path = PySys_GetObject("path");
    if (sys_path == nullptr) {
        error = "sys.path is unavailable";
        return false;
    }

    PyObject* py_path = PyUnicode_FromString(path.string().c_str());
    if (py_path == nullptr) {
        error = "Failed to convert path to Python string";
        return false;
    }

    const int result = PyList_Insert(sys_path, 0, py_path);
    Py_DECREF(py_path);
    if (result != 0) {
        error = "Failed to add path to sys.path";
        return false;
    }

    return true;
}

void remove_sys_path(const std::filesystem::path& path) {
    PyObject* sys_path = PySys_GetObject("path");
    if (sys_path == nullptr) {
        return;
    }

    const Py_ssize_t size = PyList_Size(sys_path);
    for (Py_ssize_t i = size - 1; i >= 0; --i) {
        PyObject* item = PyList_GetItem(sys_path, i);
        if (item == nullptr || !PyUnicode_Check(item)) {
            continue;
        }

        const char* raw = PyUnicode_AsUTF8(item);
        if (raw != nullptr && path == std::filesystem::path(raw)) {
            PySequence_DelItem(sys_path, i);
        }
    }
}

} // namespace

bool PythonModuleBackend::load(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    (void)environment;

    const auto config = std::dynamic_pointer_cast<PythonModuleConfig>(record.spec.config);
    if (!config) {
        record.error_message = "Invalid Python module config";
        return false;
    }

    std::string error;
    if (!ensure_interpreter(error)) {
        record.error_message = error;
        return false;
    }

    record.error_message.clear();
    record.diagnostics.clear();

    PyGILState_STATE gil = PyGILState_Ensure();

    auto handle = std::make_shared<PythonModuleHandle>();

    if (!append_sys_path(config->root, error)) {
        PyGILState_Release(gil);
        record.error_message = error;
        return false;
    }
    handle->added_paths.push_back(config->root);

    for (const std::string& package : config->packages) {
        PyObject* module = PyImport_ImportModule(package.c_str());
        if (module == nullptr) {
            record.error_message = "Failed to import package '" + package + "': " + fetch_python_error();
            PyGILState_Release(gil);
            record.handle = handle;
            unload(record, environment);
            return false;
        }

        Py_DECREF(module);
        handle->imported_modules.push_back(package);
    }

    PyGILState_Release(gil);
    record.handle = handle;
    return true;
}

bool PythonModuleBackend::unload(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    (void)environment;

    auto handle = std::dynamic_pointer_cast<PythonModuleHandle>(record.handle);
    if (!handle) {
        return true;
    }

    std::string error;
    if (!ensure_interpreter(error)) {
        record.error_message = error;
        return false;
    }

    PyGILState_STATE gil = PyGILState_Ensure();

    PyObject* sys_modules = PyImport_GetModuleDict();
    for (const std::string& name : handle->imported_modules) {
        PyDict_DelItemString(sys_modules, name.c_str());
    }
    for (const auto& path : handle->added_paths) {
        remove_sys_path(path);
    }

    PyGILState_Release(gil);
    return true;
}

bool PythonModuleBackend::ensure_interpreter(std::string& error) const {
    error.clear();

    if (!Py_IsInitialized()) {
        Py_Initialize();
        if (!Py_IsInitialized()) {
            error = "Failed to initialize Python interpreter";
            return false;
        }
    }

    return true;
}

std::string PythonModuleBackend::fetch_python_error() const {
    PyObject* type = nullptr;
    PyObject* value = nullptr;
    PyObject* traceback = nullptr;
    PyErr_Fetch(&type, &value, &traceback);
    PyErr_NormalizeException(&type, &value, &traceback);

    std::string result = "unknown python error";
    if (value != nullptr) {
        PyObject* str_obj = PyObject_Str(value);
        if (str_obj != nullptr) {
            const char* text = PyUnicode_AsUTF8(str_obj);
            if (text != nullptr) {
                result = text;
            }
            Py_DECREF(str_obj);
        }
    }

    Py_XDECREF(type);
    Py_XDECREF(value);
    Py_XDECREF(traceback);
    return result;
}

} // namespace termin_modules
