// Termin Editor - Minimal C++ entry point
//
// This version doesn't require Qt C++ SDK - it just initializes Python
// and lets PyQt6 handle everything including QApplication creation.

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <iostream>
#include <filesystem>

#ifdef _WIN32
#include <windows.h>
#endif

namespace fs = std::filesystem;

// Get executable directory
static fs::path get_executable_dir() {
#ifdef _WIN32
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    return fs::path(path).parent_path();
#else
    return fs::current_path();
#endif
}

int main(int argc, char* argv[]) {
    // Find project root
    fs::path exe_dir = get_executable_dir();
    fs::path project_root = exe_dir;

    while (!project_root.empty()) {
        if (fs::exists(project_root / "termin" / "__init__.py")) {
            break;
        }
        auto parent = project_root.parent_path();
        if (parent == project_root) {
            project_root = exe_dir;
            break;
        }
        project_root = parent;
    }

    std::cout << "Project root: " << project_root << std::endl;

    // Initialize Python
    Py_Initialize();
    if (!Py_IsInitialized()) {
        std::cerr << "Failed to initialize Python" << std::endl;
        return 1;
    }

    // Set Python path
    std::string init_code =
        "import sys\n"
        "sys.path.insert(0, r'" + project_root.string() + "')\n";

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
