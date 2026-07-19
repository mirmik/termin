// Termin Editor - C++ entry point with EngineCore
//
// Creates EngineCore in C++, initializes Python/tcgui/SDL via Python,
// runs main loop in C++ (EngineCore.run()).

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "termin/bootstrap/bootstrap.hpp"
#include "termin/engine/engine_core.hpp"

#include <iostream>
#include <cstring>
#include <filesystem>
#include <cstdlib>
#include <string>

#ifdef _WIN32
#include <windows.h>
#endif

#ifdef __linux__
#include <unistd.h>
#include <linux/limits.h>
#endif

namespace fs = std::filesystem;

namespace {

class RuntimeBootstrapGuard {
public:
    RuntimeBootstrapGuard() {
        termin::bootstrap::bootstrap_runtime();
    }

    ~RuntimeBootstrapGuard() {
        termin::bootstrap::shutdown_runtime();
    }

    RuntimeBootstrapGuard(const RuntimeBootstrapGuard&) = delete;
    RuntimeBootstrapGuard& operator=(const RuntimeBootstrapGuard&) = delete;
};

} // namespace

static fs::path get_executable_dir() {
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

static fs::path find_python_stdlib(const fs::path& install_root) {
#ifdef _WIN32
    fs::path lib_dir = install_root / "python" / "Lib";
    if (fs::exists(lib_dir) && fs::exists(lib_dir / "os.py")) {
        return lib_dir;
    }
    return {};
#else
    fs::path lib_dir = install_root / "lib";
    if (!fs::exists(lib_dir)) return {};

    for (const auto& entry : fs::directory_iterator(lib_dir)) {
        if (entry.is_directory()) {
            std::string name = entry.path().filename().string();
            if (name.find("python3.") == 0 && name.find("python3.10") != std::string::npos) {
                return entry.path();
            }
        }
    }

    for (const auto& entry : fs::directory_iterator(lib_dir)) {
        if (entry.is_directory()) {
            std::string name = entry.path().filename().string();
            if (name.find("python3.") == 0) {
                return entry.path();
            }
        }
    }

    return {};
#endif
}

static fs::path find_site_packages_termin(const fs::path& install_root) {
#ifdef _WIN32
    fs::path termin_dir = install_root / "python" / "Lib" / "site-packages" / "termin";
    if (fs::exists(termin_dir)) {
        return termin_dir;
    }
    return {};
#else
    fs::path lib_dir = install_root / "lib";
    if (!fs::exists(lib_dir)) return {};

    for (const auto& entry : fs::directory_iterator(lib_dir)) {
        if (!entry.is_directory()) continue;
        std::string name = entry.path().filename().string();
        if (name.find("python3.") != 0) continue;
        fs::path termin_dir = entry.path() / "site-packages" / "termin";
        if (fs::exists(termin_dir)) {
            return termin_dir;
        }
    }
    return {};
#endif
}

static void set_python_argv(int argc, char* argv[]) {
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

static bool is_python_layout_smoke_request(int argc, char* argv[]) {
    return argc == 2 && std::strcmp(argv[1], "--termin-python-layout-smoke") == 0;
}

static bool initialize_python_editor(termin::EngineCore& engine) {
    PyObject* module = PyImport_ImportModule("termin.editor.run_editor");
    if (module == nullptr) {
        PyErr_Print();
        std::cerr << "Failed to import termin.editor.run_editor" << std::endl;
        return false;
    }

    PyObject* init_editor = PyObject_GetAttrString(module, "init_editor_from_host");
    Py_DECREF(module);
    if (init_editor == nullptr || !PyCallable_Check(init_editor)) {
        Py_XDECREF(init_editor);
        PyErr_Print();
        std::cerr << "Missing callable init_editor_from_host" << std::endl;
        return false;
    }

    PyObject* capsule = PyCapsule_New(
        &engine,
        "termin.EngineCore.borrowed",
        nullptr);
    if (capsule == nullptr) {
        Py_DECREF(init_editor);
        PyErr_Print();
        std::cerr << "Failed to create borrowed EngineCore capsule" << std::endl;
        return false;
    }

    PyObject* result = PyObject_CallFunctionObjArgs(init_editor, capsule, nullptr);
    Py_DECREF(capsule);
    Py_DECREF(init_editor);
    if (result == nullptr) {
        PyErr_Print();
        std::cerr << "Failed to initialize Python editor" << std::endl;
        return false;
    }
    Py_DECREF(result);
    return true;
}

int main(int argc, char* argv[]) {
    fs::path exe_dir = get_executable_dir();
    fs::path install_root = exe_dir.parent_path();
    bool bundled_python = false;

    fs::path python_stdlib = find_python_stdlib(install_root);

    fs::path termin_path;
    bool installed_site_packages = false;
    fs::path installed_termin_path = find_site_packages_termin(install_root);

    if (!python_stdlib.empty()) {
        bundled_python = true;
        termin_path = python_stdlib / "site-packages" / "termin";

        std::cout << "Using bundled Python: " << python_stdlib << std::endl;

        // Anchor the SDK root to this executable's install tree so
        // Python-side `preload_sdk_libs()` (termin_nanobind/runtime.py)
        // loads libs from here instead of falling back to /opt/termin.
        // Respect an explicit TERMIN_SDK if the user already set one.
        if (std::getenv("TERMIN_SDK") == nullptr) {
#ifdef _WIN32
            _putenv_s("TERMIN_SDK", install_root.string().c_str());
#else
            setenv("TERMIN_SDK", install_root.c_str(), 1);
#endif
        }

        static std::string python_home_str =
#ifdef _WIN32
            python_stdlib.parent_path().string();
#else
            install_root.string();
#endif
        static std::wstring python_home_wstr(python_home_str.begin(), python_home_str.end());
        Py_SetPythonHome(python_home_wstr.c_str());

        Py_NoSiteFlag = 0;
        Py_IgnoreEnvironmentFlag = 1;
    } else if (!installed_termin_path.empty()) {
        installed_site_packages = true;
        termin_path = installed_termin_path;
        std::cout << "Using installed Python modules: " << termin_path << std::endl;

        if (std::getenv("TERMIN_SDK") == nullptr) {
#ifdef _WIN32
            _putenv_s("TERMIN_SDK", install_root.string().c_str());
#else
            setenv("TERMIN_SDK", install_root.c_str(), 1);
#endif
        }
    } else {
        fs::path project_root = exe_dir;
        while (!project_root.empty()) {
            if (fs::exists(project_root / "termin" / "__init__.py")) {
                termin_path = project_root;
                break;
            }
            auto parent = project_root.parent_path();
            if (parent == project_root) {
                termin_path = exe_dir;
                break;
            }
            project_root = parent;
        }
        std::cout << "Development mode, project root: " << termin_path << std::endl;
    }

    // The process runtime owns scene pools, type registries and scene-extension
    // registration.  It must outlive EngineCore and must be initialized before
    // the native host constructs any engine-owned subsystem.
    RuntimeBootstrapGuard runtime_bootstrap;

    // The native host owns the engine. Python receives a borrowed reference
    // explicitly during frontend initialization.
    termin::EngineCore engine;

    // Initialize Python
    Py_Initialize();
    if (!Py_IsInitialized()) {
        std::cerr << "Failed to initialize Python" << std::endl;
        return 1;
    }
    set_python_argv(argc, argv);

    // Set Python path
    std::string path_code;
    if (bundled_python) {
        fs::path site_packages = python_stdlib / "site-packages";
        path_code =
            "import sys\n"
            "sys.path.insert(0, r'" + site_packages.string() + "')\n";
    } else if (installed_site_packages) {
        path_code =
            "import sys\n"
            "host_paths = [p for p in r'" TERMIN_HOST_PYTHON_PATHS "'.split('|') if p]\n"
            "for p in reversed(host_paths):\n"
            "    if p and p not in sys.path:\n"
            "        sys.path.insert(0, p)\n"
            "sys.path.insert(0, r'" + termin_path.parent_path().string() + "')\n";
    } else {
        path_code =
            "import sys\n"
            "sys.path.insert(0, r'" + termin_path.string() + "')\n";
    }

    if (PyRun_SimpleString(path_code.c_str()) != 0) {
        std::cerr << "Failed to set Python path" << std::endl;
        return 1;
    }

    if (is_python_layout_smoke_request(argc, argv)) {
        const char* smoke_code = R"(
import json
import tcbase
import termin.editor
print(json.dumps({"tcbase": tcbase.__file__, "termin_editor": termin.editor.__file__}))
)";
        const int result = PyRun_SimpleString(smoke_code);
        if (result != 0) {
            PyErr_Print();
        }
        Py_Finalize();
        return result == 0 ? 0 : 1;
    }

    // Initialize editor (creates UI/SDL and installs engine callbacks).
    if (!initialize_python_editor(engine)) {
        return 1;
    }

    // Run main loop in C++
    engine.run();

    // Let the OS tear down the embedded interpreter. Some app/UI destructors
    // can still touch Python during shutdown, and Py_Finalize makes that crash.
    return 0;
}
