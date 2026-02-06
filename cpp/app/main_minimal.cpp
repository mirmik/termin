// Termin Editor - C++ entry point with EngineCore
//
// Creates EngineCore in C++, initializes Python/Qt/SDL via Python,
// runs main loop in C++ (EngineCore.run()).

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "termin/engine/engine_core.hpp"

#include <iostream>
#include <filesystem>
#include <cstdlib>

#ifdef _WIN32
#include <windows.h>
#endif

#ifdef __linux__
#include <unistd.h>
#include <linux/limits.h>
#endif

namespace fs = std::filesystem;

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
    fs::path lib_dir = install_root / "Lib";
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

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    fs::path exe_dir = get_executable_dir();
    fs::path install_root = exe_dir.parent_path();
    bool bundled_python = false;

    fs::path python_stdlib = find_python_stdlib(install_root);
    fs::path termin_path;

    if (!python_stdlib.empty()) {
        bundled_python = true;
        termin_path = install_root / "lib" / "python" / "termin";

        std::cout << "Using bundled Python: " << python_stdlib << std::endl;

        static std::string python_home_str = install_root.string();
        static std::wstring python_home_wstr(python_home_str.begin(), python_home_str.end());
        Py_SetPythonHome(python_home_wstr.c_str());

        Py_NoSiteFlag = 0;
        Py_IgnoreEnvironmentFlag = 1;
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

    // Create EngineCore BEFORE Python init
    // This sets up RenderingManager::instance()
    termin::EngineCore engine;

    // Initialize Python
    Py_Initialize();
    if (!Py_IsInitialized()) {
        std::cerr << "Failed to initialize Python" << std::endl;
        return 1;
    }

    // Set Python path
    std::string path_code;
    if (bundled_python) {
        fs::path site_packages = python_stdlib / "site-packages";
        path_code =
            "import sys\n"
            "sys.path.insert(0, r'" + termin_path.parent_path().string() + "')\n"
            "sys.path.insert(0, r'" + site_packages.string() + "')\n";
    } else {
        path_code =
            "import sys\n"
            "sys.path.insert(0, r'" + termin_path.string() + "')\n";
    }

    if (PyRun_SimpleString(path_code.c_str()) != 0) {
        std::cerr << "Failed to set Python path" << std::endl;
        Py_Finalize();
        return 1;
    }

    // Initialize editor (creates Qt app, SDL, EditorWindow, sets up callbacks)
    const char* init_code = R"(
from termin.editor.run_editor import init_editor
init_editor()
)";

    int result = PyRun_SimpleString(init_code);
    if (result != 0) {
        PyErr_Print();
        Py_Finalize();
        return 1;
    }

    // Run main loop in C++
    engine.run();

    Py_Finalize();
    return 0;
}
