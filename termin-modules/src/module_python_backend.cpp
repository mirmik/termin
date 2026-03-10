#include "termin_modules/module_python_backend.hpp"

#include <Python.h>

#include <cstdio>
#include <filesystem>
#include <sstream>
#include <string>
#include <vector>

namespace termin_modules {
namespace {

std::filesystem::path venv_python_path(const ModuleEnvironment& environment) {
#ifdef _WIN32
    return environment.project_venv_path / "Scripts" / "python.exe";
#else
    return environment.project_venv_path / "bin" / "python";
#endif
}

bool has_added_path(
    const std::vector<std::filesystem::path>& added_paths,
    const std::filesystem::path& path
) {
    for (const std::filesystem::path& added_path : added_paths) {
        if (added_path == path) {
            return true;
        }
    }

    return false;
}

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

bool append_sys_path_once(
    const std::filesystem::path& path,
    std::vector<std::filesystem::path>& added_paths,
    std::string& error
) {
    if (has_added_path(added_paths, path)) {
        return true;
    }

    if (!append_sys_path(path, error)) {
        return false;
    }

    added_paths.push_back(path);
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

std::string fetch_python_error_string() {
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

std::string shell_quote(const std::string& value) {
    std::string result = "\"";
    for (char ch : value) {
        if (ch == '\\' || ch == '"') {
            result.push_back('\\');
        }
        result.push_back(ch);
    }
    result.push_back('"');
    return result;
}

bool run_command_capture(
    const std::string& command,
    std::string& output,
    std::string& error
) {
    output.clear();
    error.clear();

    FILE* pipe = popen(command.c_str(), "r");
    if (pipe == nullptr) {
        error = "Failed to start process";
        return false;
    }

    char buffer[512];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += buffer;
    }

    const int result = pclose(pipe);
    if (result != 0) {
        std::ostringstream ss;
        ss << "Process exited with code " << result;
        error = ss.str();
        return false;
    }

    return true;
}

std::string summarize_command_output(
    const std::string& output,
    const std::string& fallback
) {
    std::istringstream stream(output);
    std::string line;
    std::string last_non_empty_line;

    while (std::getline(stream, line)) {
        if (!line.empty()) {
            last_non_empty_line = line;
        }
    }

    if (!last_non_empty_line.empty()) {
        return last_non_empty_line;
    }

    return fallback;
}

std::string requirement_name(const std::string& requirement) {
    const std::string separators = "<>=!~";
    const size_t pos = requirement.find_first_of(separators);
    if (pos == std::string::npos) {
        return requirement;
    }
    return requirement.substr(0, pos);
}

bool has_distribution(const std::string& requirement, bool& installed, std::string& error) {
    installed = false;
    error.clear();

    PyObject* metadata_module = PyImport_ImportModule("importlib.metadata");
    if (metadata_module == nullptr) {
        error = fetch_python_error_string();
        return false;
    }

    PyObject* distribution_fn = PyObject_GetAttrString(metadata_module, "distribution");
    PyObject* package_not_found = PyObject_GetAttrString(metadata_module, "PackageNotFoundError");
    if (distribution_fn == nullptr || package_not_found == nullptr) {
        error = fetch_python_error_string();
        Py_XDECREF(distribution_fn);
        Py_XDECREF(package_not_found);
        Py_DECREF(metadata_module);
        return false;
    }

    const std::string dist_name = requirement_name(requirement);
    PyObject* result = PyObject_CallFunction(distribution_fn, "s", dist_name.c_str());
    if (result != nullptr) {
        installed = true;
        Py_DECREF(result);
        Py_DECREF(distribution_fn);
        Py_DECREF(package_not_found);
        Py_DECREF(metadata_module);
        return true;
    }

    if (PyErr_ExceptionMatches(package_not_found)) {
        PyErr_Clear();
        Py_DECREF(distribution_fn);
        Py_DECREF(package_not_found);
        Py_DECREF(metadata_module);
        return true;
    }

    error = fetch_python_error_string();
    Py_DECREF(distribution_fn);
    Py_DECREF(package_not_found);
    Py_DECREF(metadata_module);
    return false;
}

bool ensure_project_venv(
    const ModuleEnvironment& environment,
    std::string& diagnostics,
    std::string& error
) {
    diagnostics.clear();
    error.clear();

    if (!environment.use_project_venv) {
        return true;
    }

    if (environment.project_venv_path.empty()) {
        error = "project_venv_path is not configured";
        return false;
    }

    if (environment.python_executable.empty()) {
        error = "python_executable is not configured";
        return false;
    }

    const std::filesystem::path python = venv_python_path(environment);
    if (std::filesystem::exists(python)) {
        return true;
    }

    if (std::filesystem::exists(environment.project_venv_path)) {
        error = "Project venv is incomplete: " + environment.project_venv_path.string();
        return false;
    }

    std::error_code mkdir_error;
    std::filesystem::create_directories(environment.project_venv_path.parent_path(), mkdir_error);
    if (mkdir_error) {
        error = "Failed to create parent directory for project venv: " + mkdir_error.message();
        return false;
    }

    const std::string command =
        shell_quote(environment.python_executable) +
        " -m venv " +
        shell_quote(environment.project_venv_path.string()) +
        " 2>&1";

    if (!run_command_capture(command, diagnostics, error)) {
        error = "Failed to create project venv: " + summarize_command_output(diagnostics, error);
        return false;
    }

    if (!std::filesystem::exists(python)) {
        error = "Project venv was created, but python executable is missing: " + python.string();
        return false;
    }

    return true;
}

bool append_python_site_paths(
    const ModuleEnvironment& environment,
    std::vector<std::filesystem::path>& added_paths,
    std::string& error
) {
    error.clear();

    if (environment.use_project_venv) {
        const std::filesystem::path python = venv_python_path(environment);
        if (!std::filesystem::exists(python)) {
            error = "Project venv python is missing: " + python.string();
            return false;
        }

        std::string output;
        const std::string command =
            shell_quote(python.string()) +
            " -c " +
            shell_quote(
                "import sysconfig; "
                "print(sysconfig.get_path('purelib')); "
                "print(sysconfig.get_path('platlib'))"
            ) +
            " 2>&1";

        std::string command_error;
        if (!run_command_capture(command, output, command_error)) {
            error = "Failed to query project venv site-packages: " + command_error;
            return false;
        }

        std::istringstream stream(output);
        std::string line;
        while (std::getline(stream, line)) {
            if (line.empty()) {
                continue;
            }

            std::string append_error;
            if (!append_sys_path_once(line, added_paths, append_error)) {
                error = append_error;
                return false;
            }
        }

        return true;
    }

    PyObject* sysconfig_module = PyImport_ImportModule("sysconfig");
    if (sysconfig_module == nullptr) {
        error = fetch_python_error_string();
        return false;
    }

    PyObject* get_path_fn = PyObject_GetAttrString(sysconfig_module, "get_path");
    if (get_path_fn == nullptr) {
        error = fetch_python_error_string();
        Py_DECREF(sysconfig_module);
        return false;
    }

    for (const char* key : {"purelib", "platlib"}) {
        PyObject* result = PyObject_CallFunction(get_path_fn, "s", key);
        if (result == nullptr) {
            error = fetch_python_error_string();
            Py_DECREF(get_path_fn);
            Py_DECREF(sysconfig_module);
            return false;
        }

        const char* raw = PyUnicode_AsUTF8(result);
        if (raw != nullptr && raw[0] != '\0') {
            std::string append_error;
            if (!append_sys_path_once(raw, added_paths, append_error)) {
                error = append_error;
                Py_DECREF(result);
                Py_DECREF(get_path_fn);
                Py_DECREF(sysconfig_module);
                return false;
            }
        }

        Py_DECREF(result);
    }

    Py_DECREF(get_path_fn);
    Py_DECREF(sysconfig_module);
    return true;
}

bool install_requirements(
    const ModuleEnvironment& environment,
    const std::vector<std::string>& requirements,
    std::string& diagnostics,
    std::string& error
) {
    diagnostics.clear();
    error.clear();

    if (requirements.empty()) {
        return true;
    }

    std::string python_executable = environment.python_executable;
    if (environment.use_project_venv) {
        const std::filesystem::path python = venv_python_path(environment);
        if (!std::filesystem::exists(python)) {
            error = "Project venv python is missing: " + python.string();
            return false;
        }
        python_executable = python.string();
    }

    if (python_executable.empty()) {
        error = "Python requirements are missing, but python_executable is not configured";
        return false;
    }

    std::string command = shell_quote(python_executable) + " -m pip install";
    for (const std::string& requirement : requirements) {
        command += " " + shell_quote(requirement);
    }
    command += " 2>&1";

    if (!run_command_capture(command, diagnostics, error)) {
        error = "pip install failed: " + summarize_command_output(diagnostics, error);
        return false;
    }

    return true;
}

bool ensure_requirements(
    const PythonModuleConfig& config,
    const ModuleEnvironment& environment,
    std::string& diagnostics,
    std::string& error
) {
    diagnostics.clear();
    error.clear();

    std::vector<std::string> missing;

    for (const std::string& requirement : config.requirements) {
        bool installed = false;
        std::string requirement_error;
        if (!has_distribution(requirement, installed, requirement_error)) {
            error = "Failed to inspect requirement '" + requirement + "': " + requirement_error;
            return false;
        }
        if (!installed) {
            missing.push_back(requirement);
        }
    }

    if (missing.empty()) {
        return true;
    }

    if (!environment.allow_python_package_install) {
        error = "Missing Python requirements: ";
        for (size_t i = 0; i < missing.size(); ++i) {
            if (i > 0) {
                error += ", ";
            }
            error += missing[i];
        }
        return false;
    }

    if (!install_requirements(environment, missing, diagnostics, error)) {
        return false;
    }

    for (const std::string& requirement : missing) {
        bool installed = false;
        std::string requirement_error;
        if (!has_distribution(requirement, installed, requirement_error)) {
            error = "Failed to re-check requirement '" + requirement + "': " + requirement_error;
            return false;
        }
        if (!installed) {
            error = "Requirement is still unavailable after install: " + requirement;
            return false;
        }
    }

    return true;
}

} // namespace

bool PythonModuleBackend::load(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
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

    if (!ensure_project_venv(environment, record.diagnostics, error)) {
        PyGILState_Release(gil);
        record.error_message = error;
        return false;
    }

    if (!append_python_site_paths(environment, handle->added_paths, error)) {
        PyGILState_Release(gil);
        record.error_message = error;
        return false;
    }

    if (!ensure_requirements(*config, environment, record.diagnostics, error)) {
        PyGILState_Release(gil);
        record.error_message = error;
        return false;
    }

    if (!append_sys_path_once(config->root, handle->added_paths, error)) {
        PyGILState_Release(gil);
        record.error_message = error;
        return false;
    }

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
    return fetch_python_error_string();
}

} // namespace termin_modules
