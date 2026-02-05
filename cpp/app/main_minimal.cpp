// Termin Editor - Minimal C++ entry point
//
// This version doesn't require Qt C++ SDK - it just initializes Python
// and lets PyQt6 handle everything including QApplication creation.
//
// Directory structure (standalone install):
//   install/
//     bin/termin_editor
//     lib/
//       libpython3.10.so
//       python3.10/          (stdlib + site-packages)
//       python/termin/       (our modules)

#define PY_SSIZE_T_CLEAN
#include <Python.h>

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

// Get executable directory (not cwd)
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

// Find bundled Python stdlib directory
// Linux: {install_root}/lib/python3.x/
// Windows: {install_root}/Lib/
static fs::path find_python_stdlib(const fs::path& install_root) {
#ifdef _WIN32
    // Windows: stdlib is in {prefix}/Lib/
    fs::path lib_dir = install_root / "Lib";
    if (fs::exists(lib_dir) && fs::exists(lib_dir / "os.py")) {
        return lib_dir;
    }
    return {};
#else
    // Linux: stdlib is in {prefix}/lib/python3.x/
    fs::path lib_dir = install_root / "lib";
    if (!fs::exists(lib_dir)) return {};

    // Look for python3.x directory
    for (const auto& entry : fs::directory_iterator(lib_dir)) {
        if (entry.is_directory()) {
            std::string name = entry.path().filename().string();
            if (name.find("python3.") == 0 && name.find("python3.10") != std::string::npos) {
                return entry.path();
            }
        }
    }

    // Fallback: look for any python3.x
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

    // Check for bundled Python (standalone mode)
    fs::path python_stdlib = find_python_stdlib(install_root);
    fs::path termin_path;

    if (!python_stdlib.empty()) {
        // Bundled Python found
        bundled_python = true;
        termin_path = install_root / "lib" / "python" / "termin";

        std::cout << "Using bundled Python: " << python_stdlib << std::endl;

        // Set PYTHONHOME before Py_Initialize
        // PYTHONHOME should point to the prefix (parent of Lib/ on Windows, parent of lib/python3.x/ on Linux)
        static std::string python_home_str = install_root.string();
        static std::wstring python_home_wstr(python_home_str.begin(), python_home_str.end());
        Py_SetPythonHome(python_home_wstr.c_str());

        // Disable site module customizations that might interfere
        Py_NoSiteFlag = 0;
        Py_IgnoreEnvironmentFlag = 1;
    } else {
        // Development mode - search for project root
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

    // Initialize Python
    Py_Initialize();
    if (!Py_IsInitialized()) {
        std::cerr << "Failed to initialize Python" << std::endl;
        return 1;
    }

    // Set Python path
    std::string init_code;
    if (bundled_python) {
        // For bundled: add both termin path and site-packages
        fs::path site_packages = python_stdlib / "site-packages";
        init_code =
            "import sys\n"
            "sys.path.insert(0, r'" + termin_path.parent_path().string() + "')\n"
            "sys.path.insert(0, r'" + site_packages.string() + "')\n";
    } else {
        init_code =
            "import sys\n"
            "sys.path.insert(0, r'" + termin_path.string() + "')\n";
    }

    if (PyRun_SimpleString(init_code.c_str()) != 0) {
        std::cerr << "Failed to set Python path" << std::endl;
        Py_Finalize();
        return 1;
    }

    // Run the editor (PyQt6 creates QApplication)
    const char* run_code = R"(
from termin.editor.run_editor import run_editor
run_editor()
)";

    int result = PyRun_SimpleString(run_code);
    if (result != 0) {
        PyErr_Print();
    }

    Py_Finalize();
    return result;
}
