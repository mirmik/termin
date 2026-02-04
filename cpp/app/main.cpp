// Termin Editor - C++ entry point with embedded Python
//
// This creates QApplication in C++ and runs the Python editor code.
// Python widgets (PyQt6) can be parented to C++ Qt widgets.

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <QApplication>
#include <QMessageBox>
#include <iostream>
#include <filesystem>

namespace fs = std::filesystem;

// Get the directory containing the executable
static fs::path get_executable_dir() {
    // On Windows, we can use GetModuleFileName, but for simplicity
    // we'll use the current working directory approach first
    return fs::current_path();
}

// Initialize Python paths for termin modules
static bool init_python_paths(const fs::path& project_root) {
    // Add project root to sys.path so "import termin" works
    std::string path_code =
        "import sys\n"
        "sys.path.insert(0, r'" + project_root.string() + "')\n";

    if (PyRun_SimpleString(path_code.c_str()) != 0) {
        std::cerr << "Failed to set Python path" << std::endl;
        return false;
    }
    return true;
}

// Run the editor
static int run_editor() {
    const char* editor_code = R"(
import sys
import time
import warnings

# Suppress SDL2 informational warning
warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor

# Get the existing QApplication instance (created in C++)
app = QApplication.instance()
if app is None:
    raise RuntimeError("QApplication must be created in C++ before running editor")

# Apply dark palette
def apply_dark_palette(app):
    app.setStyle("Fusion")
    palette = QPalette()
    bg = QColor(30, 30, 30)
    window = QColor(37, 37, 38)
    base = QColor(45, 45, 48)
    text = QColor(220, 220, 220)
    disabled_text = QColor(128, 128, 128)
    highlight = QColor(0, 120, 215)
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, bg)
    palette.setColor(QPalette.ColorRole.ToolTipBase, base)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, window)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    app.setPalette(palette)

apply_dark_palette(app)

# Initialize SDL
import sdl2
if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
    raise RuntimeError(f"Failed to initialize SDL: {sdl2.SDL_GetError()}")

# Setup graphics backend
from termin.visualization.platform.backends import (
    OpenGLGraphicsBackend,
    set_default_graphics_backend,
)
from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend

graphics = OpenGLGraphicsBackend.get_instance()
set_default_graphics_backend(graphics)
sdl_backend = SDLEmbeddedWindowBackend(graphics=graphics)

# Create world and scene
from termin.visualization.core.world import VisualizationWorld
from termin.visualization.core.scene import Scene

world = VisualizationWorld()
scene = Scene.create(name="default")
world.add_scene(scene)

# Create editor window
from termin.editor.editor_window import EditorWindow

win = EditorWindow(world, scene, sdl_backend)
win.showMaximized()

# Process events to ensure window is visible
app.processEvents()

# Render first frame
sdl_backend.poll_events()
win.scene_manager.request_render()
win.scene_manager.tick_and_render(0.016)

# Main loop
target_fps = 60
target_frame_time = 1.0 / target_fps
last_time = time.perf_counter()

while not win.should_close():
    current_time = time.perf_counter()
    dt = current_time - last_time
    last_time = current_time

    app.processEvents()
    sdl_backend.poll_events()
    win.scene_manager.tick_and_render(dt)

    elapsed = time.perf_counter() - current_time
    if elapsed < target_frame_time:
        time.sleep(target_frame_time - elapsed)

# Cleanup
sdl_backend.terminate()
sdl2.SDL_Quit()
)";

    if (PyRun_SimpleString(editor_code) != 0) {
        PyErr_Print();
        return 1;
    }
    return 0;
}

int main(int argc, char* argv[]) {
    // Create Qt application FIRST (before Python)
    // This is important: Qt must own the event loop
    QApplication app(argc, argv);

    // Initialize Python interpreter
    Py_Initialize();

    if (!Py_IsInitialized()) {
        QMessageBox::critical(nullptr, "Error", "Failed to initialize Python");
        return 1;
    }

    // Find project root (go up from executable location)
    fs::path exe_dir = get_executable_dir();
    fs::path project_root = exe_dir;

    // Try to find termin package
    while (!project_root.empty()) {
        if (fs::exists(project_root / "termin" / "__init__.py")) {
            break;
        }
        auto parent = project_root.parent_path();
        if (parent == project_root) {
            // Reached filesystem root
            project_root = exe_dir;
            break;
        }
        project_root = parent;
    }

    std::cout << "Project root: " << project_root << std::endl;

    // Setup Python paths
    if (!init_python_paths(project_root)) {
        QMessageBox::critical(nullptr, "Error", "Failed to initialize Python paths");
        Py_Finalize();
        return 1;
    }

    // Run the editor
    int result = run_editor();

    // Cleanup Python
    Py_Finalize();

    return result;
}
