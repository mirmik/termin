#include "termin_modules/module_python_backend.hpp"
#include "termin_modules/text_encoding.hpp"

#include <Python.h>

#include <cstdio>
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <sstream>
#include <string>
#include <vector>

#ifdef _WIN32
#define popen _popen
#define pclose _pclose
#endif

namespace termin_modules {
namespace {

std::string fetch_python_error_string();

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

std::filesystem::path normalize_import_path(const std::filesystem::path& path) {
    std::error_code error;
    std::filesystem::path normalized = std::filesystem::weakly_canonical(path, error);
    if (!error) {
        return normalized;
    }
    normalized = std::filesystem::absolute(path, error);
    if (!error) {
        return normalized.lexically_normal();
    }
    return path.lexically_normal();
}

std::string import_path_key(const std::filesystem::path& path) {
    std::string key = normalize_import_path(path).generic_string();
#ifdef _WIN32
    std::transform(key.begin(), key.end(), key.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
#endif
    return key;
}

bool sys_path_contains(const std::filesystem::path& path) {
    PyObject* sys_path = PySys_GetObject("path");
    if (sys_path == nullptr) {
        return false;
    }

    const std::string key = import_path_key(path);
    const Py_ssize_t size = PyList_Size(sys_path);
    for (Py_ssize_t i = 0; i < size; ++i) {
        PyObject* item = PyList_GetItem(sys_path, i);
        if (item == nullptr || !PyUnicode_Check(item)) {
            continue;
        }
        const char* raw = PyUnicode_AsUTF8(item);
        if (raw != nullptr && import_path_key(raw) == key) {
            return true;
        }
        if (raw == nullptr) {
            PyErr_Clear();
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
    const std::filesystem::path normalized = normalize_import_path(path);
    if (has_added_path(added_paths, normalized) || sys_path_contains(normalized)) {
        return true;
    }

    if (!append_sys_path(normalized, error)) {
        return false;
    }

    added_paths.push_back(normalized);
    return true;
}

void remove_one_sys_path_entry(const std::filesystem::path& path) {
    PyObject* sys_path = PySys_GetObject("path");
    if (sys_path == nullptr) {
        return;
    }

    const std::string key = import_path_key(path);
    const Py_ssize_t size = PyList_Size(sys_path);
    for (Py_ssize_t i = 0; i < size; ++i) {
        PyObject* item = PyList_GetItem(sys_path, i);
        if (item == nullptr || !PyUnicode_Check(item)) {
            continue;
        }

        const char* raw = PyUnicode_AsUTF8(item);
        if (raw != nullptr && import_path_key(raw) == key) {
            PySequence_DelItem(sys_path, i);
            return;
        }
        if (raw == nullptr) {
            PyErr_Clear();
        }
    }
}

void rollback_added_paths(std::vector<std::filesystem::path>& added_paths) {
    for (auto it = added_paths.rbegin(); it != added_paths.rend(); ++it) {
        remove_one_sys_path_entry(*it);
    }
    added_paths.clear();
}

bool call_module_context_function(
    const char* function_name,
    const std::string& module_id,
    std::string& error
) {
    PyObject* context_module = PyImport_ImportModule("termin_modules.module_context");
    if (context_module == nullptr) {
        error = "Failed to import termin_modules.module_context: " + fetch_python_error_string();
        return false;
    }

    PyObject* result = PyObject_CallMethod(context_module, function_name, "s", module_id.c_str());
    Py_DECREF(context_module);
    if (result == nullptr) {
        error = std::string("termin_modules.module_context.") + function_name + " failed: " + fetch_python_error_string();
        return false;
    }

    Py_DECREF(result);
    return true;
}

bool module_name_matches_package(const std::string& module_name, const std::string& package) {
    if (module_name == package) {
        return true;
    }

    if (module_name.size() <= package.size() + 1) {
        return false;
    }

    return module_name.compare(0, package.size(), package) == 0 &&
        module_name[package.size()] == '.';
}

std::vector<std::string> collect_imported_module_subtree(
    const std::vector<std::string>& packages
) {
    std::vector<std::string> result;

    PyObject* sys_modules = PyImport_GetModuleDict();
    if (sys_modules == nullptr) {
        return result;
    }

    PyObject* keys = PyDict_Keys(sys_modules);
    if (keys == nullptr) {
        PyErr_Clear();
        return result;
    }

    const Py_ssize_t size = PyList_Size(keys);
    for (Py_ssize_t i = 0; i < size; ++i) {
        PyObject* key = PyList_GetItem(keys, i);
        if (key == nullptr || !PyUnicode_Check(key)) {
            continue;
        }

        const char* raw_name = PyUnicode_AsUTF8(key);
        if (raw_name == nullptr) {
            PyErr_Clear();
            continue;
        }

        std::string module_name(raw_name);
        for (const std::string& package : packages) {
            if (module_name_matches_package(module_name, package)) {
                result.push_back(std::move(module_name));
                break;
            }
        }
    }

    Py_DECREF(keys);

    std::sort(result.begin(), result.end(), [](const std::string& lhs, const std::string& rhs) {
        if (lhs.size() != rhs.size()) {
            return lhs.size() > rhs.size();
        }
        return lhs > rhs;
    });
    result.erase(std::unique(result.begin(), result.end()), result.end());
    return result;
}

void remove_sys_module(const std::string& name) {
    PyObject* sys_modules = PyImport_GetModuleDict();
    if (sys_modules == nullptr) {
        return;
    }

    if (PyDict_DelItemString(sys_modules, name.c_str()) != 0) {
        PyErr_Clear();
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
#ifdef _WIN32
        if (ch == '"') {
            result.push_back('\\');
        }
#else
        if (ch == '\\' || ch == '"') {
            result.push_back('\\');
        }
#endif
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

    std::string popen_command = command;
#ifdef _WIN32
    // _popen delegates to cmd.exe. A command that starts with a quoted
    // executable and also contains quoted arguments is parsed incorrectly by
    // `cmd /c` unless the whole command is wrapped with cmd's /S quoting rule.
    popen_command = "cmd /S /C \"" + command + "\"";
#endif

    FILE* pipe = popen(popen_command.c_str(), "r");
    if (pipe == nullptr) {
        error = "Failed to start process";
        return false;
    }

    char buffer[512];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += buffer;
    }
    output = sanitize_external_text(output);

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

bool PythonModuleBackend::prepare_environment(
    const std::vector<ModuleRecord>& records,
    const ModuleEnvironment& environment,
    std::string& diagnostics,
    std::string& error
) {
    diagnostics.clear();
    error.clear();
    if (_environment_prepared) {
        return true;
    }

    std::vector<std::filesystem::path> python_roots;
    for (const ModuleRecord& record : records) {
        if (record.spec.kind != ModuleKind::Python) {
            continue;
        }
        const auto config = std::dynamic_pointer_cast<PythonModuleConfig>(record.spec.config);
        if (!config || config->ignored) {
            continue;
        }
        python_roots.push_back(config->root);
    }
    if (python_roots.empty()) {
        _environment_prepared = true;
        return true;
    }

    if (!ensure_interpreter(error)) {
        return false;
    }

    PyGILState_STATE gil = PyGILState_Ensure();
    if (!ensure_project_venv(environment, diagnostics, error)) {
        PyGILState_Release(gil);
        return false;
    }
    if (!append_python_site_paths(environment, _session_added_paths, error)) {
        rollback_added_paths(_session_added_paths);
        PyGILState_Release(gil);
        return false;
    }
    for (const std::filesystem::path& root : python_roots) {
        if (!append_sys_path_once(root, _session_added_paths, error)) {
            rollback_added_paths(_session_added_paths);
            PyGILState_Release(gil);
            return false;
        }
    }

    _environment_prepared = true;
    PyGILState_Release(gil);
    return true;
}

bool PythonModuleBackend::teardown_environment(
    const ModuleEnvironment& environment,
    std::string& error
) {
    (void)environment;
    error.clear();
    if (!_environment_prepared && _session_added_paths.empty()) {
        return true;
    }
    if (!ensure_interpreter(error)) {
        return false;
    }

    PyGILState_STATE gil = PyGILState_Ensure();
    rollback_added_paths(_session_added_paths);
    _environment_prepared = false;
    PyGILState_Release(gil);
    return true;
}

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
    if (!_environment_prepared) {
        record.error_message = "Python session environment is not prepared";
        return false;
    }

    record.error_message.clear();
    record.diagnostics.clear();

    PyGILState_STATE gil = PyGILState_Ensure();

    auto handle = std::make_shared<PythonModuleHandle>();

    if (!ensure_requirements(*config, environment, record.diagnostics, error)) {
        PyGILState_Release(gil);
        record.error_message = error;
        return false;
    }

    if (!call_module_context_function("begin_module_import", record.spec.id, error)) {
        PyGILState_Release(gil);
        record.error_message = error;
        return false;
    }

    bool import_context_active = true;
    for (const std::string& package : config->packages) {
        PyObject* module = PyImport_ImportModule(package.c_str());
        if (module == nullptr) {
            record.error_message = "Failed to import package '" + package + "': " + fetch_python_error();
            std::string context_error;
            if (!call_module_context_function("end_module_import", record.spec.id, context_error)) {
                record.error_message += "; " + context_error;
            }
            import_context_active = false;
            PyGILState_Release(gil);
            record.handle = handle;
            unload(record, environment);
            return false;
        }

        Py_DECREF(module);
        // Keep the handle authoritative after every successful import. A
        // later package may fail, and the error path must still remove the
        // complete subtree imported so far.
        handle->imported_modules = collect_imported_module_subtree(config->packages);
    }

    handle->imported_modules = collect_imported_module_subtree(config->packages);

    if (import_context_active && !call_module_context_function("end_module_import", record.spec.id, error)) {
        PyGILState_Release(gil);
        record.error_message = error;
        record.handle = handle;
        unload(record, environment);
        return false;
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

    std::string cleanup_error;
    if (!call_module_context_function("unregister_module_owner", record.spec.id, cleanup_error)) {
        record.error_message = cleanup_error;
        PyGILState_Release(gil);
        return false;
    }

    for (const std::string& name : handle->imported_modules) {
        remove_sys_module(name);
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
