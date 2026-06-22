// Termin Player - C++ entry point for packaged desktop bundles.

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "termin/engine/engine_core.hpp"
#include "termin/scene/tc_scene_render_ext.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#endif

#ifdef __linux__
#include <linux/limits.h>
#include <unistd.h>
#endif

namespace fs = std::filesystem;

namespace {

fs::path get_executable_dir() {
#ifdef _WIN32
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    return fs::path(path).parent_path();
#elif defined(__linux__)
    char path[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if (len != -1) {
        path[len] = '\0';
        return fs::path(path).parent_path();
    }
    return fs::current_path();
#else
    return fs::current_path();
#endif
}

fs::path resolve_bundle_root(const fs::path& exe_dir) {
    std::error_code ec;
    if (fs::exists(exe_dir / "app.json", ec)) {
        return exe_dir;
    }

    fs::path parent = exe_dir.parent_path();
    if (!parent.empty() && fs::exists(parent / "app.json", ec)) {
        return parent;
    }

    return parent.empty() ? exe_dir : parent;
}

fs::path find_python_stdlib(const fs::path& install_root) {
#ifdef _WIN32
    fs::path lib_dir = install_root / "python" / "Lib";
    if (fs::exists(lib_dir / "os.py")) {
        return lib_dir;
    }
    return {};
#else
    fs::path lib_dir = install_root / "lib";
    if (!fs::exists(lib_dir)) {
        return {};
    }
    for (const auto& entry : fs::directory_iterator(lib_dir)) {
        if (!entry.is_directory()) {
            continue;
        }
        const std::string name = entry.path().filename().string();
        if (name.rfind("python3.", 0) == 0 && fs::exists(entry.path() / "os.py")) {
            return entry.path();
        }
    }
    return {};
#endif
}

void set_env_if_missing(const char* name, const fs::path& value) {
    if (std::getenv(name) != nullptr) {
        return;
    }
#ifdef _WIN32
    _putenv_s(name, value.string().c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

void set_env_value(const char* name, const std::string& value) {
#ifdef _WIN32
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

std::string env_path_separator() {
#ifdef _WIN32
    return ";";
#else
    return ":";
#endif
}

void prepend_env_path(const char* name, const fs::path& value) {
    if (value.empty()) {
        return;
    }
    std::string next = value.string();
    const char* current = std::getenv(name);
    if (current != nullptr && current[0] != '\0') {
        next += env_path_separator();
        next += current;
    }
    set_env_value(name, next);
}

void configure_bundle_runtime_paths(const fs::path& bundle_root, const fs::path& exe_dir) {
    prepend_env_path("PATH", exe_dir);
    prepend_env_path("PATH", bundle_root);
    prepend_env_path("PATH", bundle_root / "bin");
    prepend_env_path("PATH", bundle_root / "lib");
}

void set_python_argv(int argc, char* argv[]) {
    wchar_t** wargv = new wchar_t*[argc];
    for (int i = 0; i < argc; i++) {
        wargv[i] = Py_DecodeLocale(argv[i], nullptr);
    }
    PySys_SetArgvEx(argc, wargv, 0);
    for (int i = 0; i < argc; i++) {
        PyMem_RawFree(wargv[i]);
    }
    delete[] wargv;
}

std::string py_string_literal(const fs::path& path) {
    std::string s = path.string();
    std::string out = "r'";
    for (char ch : s) {
        if (ch == '\'') {
            out += "'\"'\"'";
        } else {
            out += ch;
        }
    }
    out += "'";
    return out;
}

std::vector<std::string> player_args(int argc, char* argv[], const fs::path& bundle_root) {
    std::vector<std::string> result;
    result.emplace_back("termin.player");

    bool has_bundle_arg = false;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--backend") {
            if (i + 1 >= argc) {
                std::cerr << "termin_player: --backend requires a value\n";
                continue;
            }
            set_env_value("TERMIN_BACKEND", argv[++i]);
            continue;
        }
        const std::string backend_prefix = "--backend=";
        if (arg.rfind(backend_prefix, 0) == 0) {
            set_env_value("TERMIN_BACKEND", arg.substr(backend_prefix.size()));
            continue;
        }
        if (arg == "--bundle" || arg == "--app") {
            has_bundle_arg = true;
        }
        result.emplace_back(std::move(arg));
    }

    if (!has_bundle_arg) {
        result.emplace_back("--bundle");
        result.emplace_back((bundle_root / "app.json").string());
    }
    return result;
}

std::string build_bootstrap_code(
    const fs::path& site_packages,
    const fs::path& project_python,
    const std::vector<std::string>& args
) {
    std::string args_literal = "[";
    for (std::size_t i = 0; i < args.size(); ++i) {
        if (i != 0) {
            args_literal += ", ";
        }
        args_literal += "'";
        for (char ch : args[i]) {
            if (ch == '\\' || ch == '\'') {
                args_literal += '\\';
            }
            args_literal += ch;
        }
        args_literal += "'";
    }
    args_literal += "]";

    std::string code =
        "import sys\n"
        "site_packages = " + py_string_literal(site_packages) + "\n"
        "project_python = " + py_string_literal(project_python) + "\n"
        "for p in (site_packages, project_python):\n"
        "    if p and p not in sys.path:\n"
        "        sys.path.insert(0, p)\n"
        "sys.argv = " + args_literal + "\n"
        "from termin.player.__main__ import main\n"
        "main()\n";
    return code;
}

} // namespace

int main(int argc, char* argv[]) {
    fs::path exe_dir = get_executable_dir();
    fs::path bundle_root = resolve_bundle_root(exe_dir);
    fs::path python_stdlib = find_python_stdlib(bundle_root);
    if (python_stdlib.empty()) {
        std::cerr << "termin_player: bundled Python stdlib was not found under "
                  << bundle_root << "\n";
        return 1;
    }

    set_env_if_missing("TERMIN_SDK", bundle_root);
    configure_bundle_runtime_paths(bundle_root, exe_dir);
    std::vector<std::string> args = player_args(argc, argv, bundle_root);

    static std::string python_home_str =
#ifdef _WIN32
        python_stdlib.parent_path().string();
#else
        bundle_root.string();
#endif
    static std::wstring python_home_wstr(python_home_str.begin(), python_home_str.end());
    Py_SetPythonHome(python_home_wstr.c_str());
    Py_NoSiteFlag = 0;
    Py_IgnoreEnvironmentFlag = 1;

    termin::register_default_scene_extensions();
    termin::EngineCore engine;

    Py_Initialize();
    if (!Py_IsInitialized()) {
        std::cerr << "termin_player: failed to initialize Python\n";
        return 1;
    }
    set_python_argv(argc, argv);

    fs::path site_packages = python_stdlib / "site-packages";
    fs::path project_python = bundle_root / "package" / "python";
    std::string bootstrap_code = build_bootstrap_code(site_packages, project_python, args);

    int result = PyRun_SimpleString(bootstrap_code.c_str());
    if (result != 0) {
        PyErr_Print();
        Py_FinalizeEx();
        return 1;
    }

    if (Py_FinalizeEx() < 0) {
        std::cerr << "termin_player: Python finalization failed\n";
        return 1;
    }

    return 0;
}
