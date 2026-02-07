"""Termin Launcher: project selection and creation UI."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import time

import sdl2
from sdl2 import video

from termin.graphics import OpenGLGraphicsBackend
from termin.visualization.platform.backends import set_default_graphics_backend
from termin.visualization.ui.widgets.ui import UI
from termin.visualization.ui.widgets.basic import Label, Button, TextInput, Separator
from termin.visualization.ui.widgets.containers import HStack, VStack, Panel
from termin.visualization.ui.widgets.units import px, pct
from termin.visualization.platform.backends.base import Key
from termin._native import log
from termin.launcher.recent import RecentProjects, create_project, write_launch_project


# ---------------------------------------------------------------------------
# SDL helpers
# ---------------------------------------------------------------------------

def _create_sdl_window(title: str, width: int, height: int) -> tuple:
    """Create SDL window with OpenGL 3.3 core context."""
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError()}")

    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
    video.SDL_GL_SetAttribute(
        video.SDL_GL_CONTEXT_PROFILE_MASK,
        video.SDL_GL_CONTEXT_PROFILE_CORE,
    )
    video.SDL_GL_SetAttribute(video.SDL_GL_DOUBLEBUFFER, 1)
    video.SDL_GL_SetAttribute(video.SDL_GL_DEPTH_SIZE, 24)

    flags = video.SDL_WINDOW_OPENGL | video.SDL_WINDOW_RESIZABLE | video.SDL_WINDOW_SHOWN
    window = video.SDL_CreateWindow(
        title.encode("utf-8"),
        video.SDL_WINDOWPOS_CENTERED,
        video.SDL_WINDOWPOS_CENTERED,
        width, height, flags,
    )
    if not window:
        raise RuntimeError(f"SDL_CreateWindow failed: {sdl2.SDL_GetError()}")

    gl_context = video.SDL_GL_CreateContext(window)
    if not gl_context:
        video.SDL_DestroyWindow(window)
        raise RuntimeError(f"SDL_GL_CreateContext failed: {sdl2.SDL_GetError()}")

    video.SDL_GL_MakeCurrent(window, gl_context)
    video.SDL_GL_SetSwapInterval(1)
    return window, gl_context


def _get_drawable_size(window) -> tuple[int, int]:
    w = ctypes.c_int()
    h = ctypes.c_int()
    video.SDL_GL_GetDrawableSize(window, ctypes.byref(w), ctypes.byref(h))
    return w.value, h.value


def _translate_sdl_key(scancode: int) -> int:
    _MAP = {
        sdl2.SDL_SCANCODE_BACKSPACE: Key.BACKSPACE,
        sdl2.SDL_SCANCODE_DELETE: Key.DELETE,
        sdl2.SDL_SCANCODE_LEFT: Key.LEFT,
        sdl2.SDL_SCANCODE_RIGHT: Key.RIGHT,
        sdl2.SDL_SCANCODE_HOME: Key.HOME,
        sdl2.SDL_SCANCODE_END: Key.END,
        sdl2.SDL_SCANCODE_RETURN: Key.ENTER,
        sdl2.SDL_SCANCODE_ESCAPE: Key.ESCAPE,
        sdl2.SDL_SCANCODE_TAB: Key.TAB,
        sdl2.SDL_SCANCODE_SPACE: Key.SPACE,
    }
    if scancode in _MAP:
        return _MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


def _translate_sdl_mods(sdl_mods: int) -> int:
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= 0x0001
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= 0x0002
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= 0x0004
    return result


# ---------------------------------------------------------------------------
# Tkinter dialogs
# ---------------------------------------------------------------------------

def _ask_directory() -> str:
    """Open a native directory picker."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askdirectory(title="Select project location")
    root.destroy()
    return path or ""


def _ask_open_project() -> str:
    """Open a native file picker for .terminproj files."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Open Termin Project",
        filetypes=[("Termin Project", "*.terminproj"), ("All files", "*.*")],
    )
    root.destroy()
    return path or ""


# ---------------------------------------------------------------------------
# Editor launch
# ---------------------------------------------------------------------------

def _find_editor_executable() -> str | None:
    """Find the termin_editor executable next to this launcher."""
    try:
        exe_dir = os.path.dirname(os.readlink("/proc/self/exe"))
    except (OSError, AttributeError):
        exe_dir = None

    if exe_dir:
        editor = os.path.join(exe_dir, "termin_editor")
        if os.path.isfile(editor):
            return editor

    import shutil
    return shutil.which("termin_editor")


# ---------------------------------------------------------------------------
# Launcher app
# ---------------------------------------------------------------------------

class LauncherApp:
    """Manages launcher state and screen switching."""

    def __init__(self, graphics: OpenGLGraphicsBackend):
        self.graphics = graphics
        self.ui = UI(graphics)
        self.recent = RecentProjects()
        self._bg_image_path = os.path.join(os.path.dirname(__file__), "back.png")
        self.should_quit: bool = False

        self.show_main_screen()

    # --- Screen builders ---

    def show_main_screen(self):
        """Build and show the main launcher screen."""
        bg = self._make_background()

        panel = Panel()
        panel.background_color = (0.12, 0.12, 0.16, 0.90)
        panel.padding = 36
        panel.anchor = "center"
        panel.border_radius = 12

        stack = VStack()
        stack.spacing = 16
        stack.alignment = "left"

        # Title
        title = Label()
        title.text = "Termin Engine"
        title.font_size = 32
        title.color = (1.0, 1.0, 1.0, 1.0)

        subtitle = Label()
        subtitle.text = "Project Launcher"
        subtitle.font_size = 16
        subtitle.color = (0.55, 0.6, 0.7, 1.0)

        stack.add_child(title)
        stack.add_child(subtitle)

        # Separator
        sep1 = Separator()
        sep1.orientation = "horizontal"
        sep1.color = (0.3, 0.3, 0.35, 1.0)
        stack.add_child(sep1)

        # Recent projects header
        recent_header = Label()
        recent_header.text = "Recent Projects"
        recent_header.font_size = 14
        recent_header.color = (0.6, 0.6, 0.65, 1.0)
        stack.add_child(recent_header)

        # Recent projects list
        projects = self.recent.list()
        if projects:
            for entry in projects[:8]:
                row = self._make_project_row(entry)
                stack.add_child(row)
        else:
            empty_label = Label()
            empty_label.text = "No recent projects"
            empty_label.font_size = 14
            empty_label.color = (0.4, 0.4, 0.45, 1.0)
            stack.add_child(empty_label)

        # Separator
        sep2 = Separator()
        sep2.orientation = "horizontal"
        sep2.color = (0.3, 0.3, 0.35, 1.0)
        stack.add_child(sep2)

        # Action buttons
        btn_row = HStack()
        btn_row.spacing = 12
        btn_row.alignment = "center"

        new_btn = Button()
        new_btn.text = "New Project"
        new_btn.font_size = 15
        new_btn.padding = 12
        new_btn.background_color = (0.2, 0.45, 0.8, 1.0)
        new_btn.hover_color = (0.25, 0.55, 0.9, 1.0)
        new_btn.pressed_color = (0.15, 0.35, 0.7, 1.0)
        new_btn.border_radius = 6
        new_btn.on_click = self.show_new_project_screen

        open_btn = Button()
        open_btn.text = "Open Project"
        open_btn.font_size = 15
        open_btn.padding = 12
        open_btn.background_color = (0.25, 0.25, 0.3, 1.0)
        open_btn.hover_color = (0.35, 0.35, 0.4, 1.0)
        open_btn.pressed_color = (0.18, 0.18, 0.22, 1.0)
        open_btn.border_radius = 6
        open_btn.on_click = self._on_open_project

        btn_row.add_child(new_btn)
        btn_row.add_child(open_btn)
        stack.add_child(btn_row)

        panel.add_child(stack)
        bg.add_child(panel)
        self.ui.root = bg

    def show_new_project_screen(self):
        """Build and show the new-project form screen."""
        bg = self._make_background()

        panel = Panel()
        panel.background_color = (0.12, 0.12, 0.16, 0.90)
        panel.padding = 36
        panel.anchor = "center"
        panel.border_radius = 12

        stack = VStack()
        stack.spacing = 16
        stack.alignment = "left"

        # Title
        title = Label()
        title.text = "New Project"
        title.font_size = 28
        title.color = (1.0, 1.0, 1.0, 1.0)

        sep = Separator()
        sep.orientation = "horizontal"
        sep.color = (0.3, 0.3, 0.35, 1.0)

        # Name
        name_label = Label()
        name_label.text = "Project Name"
        name_label.font_size = 13
        name_label.color = (0.6, 0.6, 0.65, 1.0)

        name_input = TextInput()
        name_input.placeholder = "MyProject"
        name_input.preferred_width = px(400)
        name_input.font_size = 15

        # Path
        path_label = Label()
        path_label.text = "Location"
        path_label.font_size = 13
        path_label.color = (0.6, 0.6, 0.65, 1.0)

        path_input = TextInput()
        path_input.text = os.path.expanduser("~/projects")
        path_input.preferred_width = px(320)
        path_input.font_size = 15

        browse_btn = Button()
        browse_btn.text = "Browse..."
        browse_btn.font_size = 13
        browse_btn.padding = 8
        browse_btn.background_color = (0.25, 0.25, 0.3, 1.0)
        browse_btn.hover_color = (0.35, 0.35, 0.4, 1.0)

        def on_browse():
            chosen = _ask_directory()
            if chosen:
                path_input.text = chosen
                path_input.cursor_pos = len(chosen)

        browse_btn.on_click = on_browse

        path_row = HStack()
        path_row.spacing = 8
        path_row.alignment = "center"
        path_row.add_child(path_input)
        path_row.add_child(browse_btn)

        # Buttons row
        btn_row = HStack()
        btn_row.spacing = 12
        btn_row.alignment = "center"

        create_btn = Button()
        create_btn.text = "Create"
        create_btn.font_size = 15
        create_btn.padding = 12
        create_btn.background_color = (0.2, 0.45, 0.8, 1.0)
        create_btn.hover_color = (0.25, 0.55, 0.9, 1.0)
        create_btn.pressed_color = (0.15, 0.35, 0.7, 1.0)
        create_btn.border_radius = 6

        back_btn = Button()
        back_btn.text = "Back"
        back_btn.font_size = 15
        back_btn.padding = 12
        back_btn.background_color = (0.25, 0.25, 0.3, 1.0)
        back_btn.hover_color = (0.35, 0.35, 0.4, 1.0)
        back_btn.pressed_color = (0.18, 0.18, 0.22, 1.0)
        back_btn.border_radius = 6
        back_btn.on_click = self.show_main_screen

        def on_create():
            name = name_input.text.strip()
            location = path_input.text.strip()
            if not name or not location:
                log.error("Name and location are required")
                return
            try:
                proj_file = create_project(name, location)
                self._launch_editor(proj_file)
            except Exception as e:
                log.error(f"Failed to create project: {e}")

        create_btn.on_click = on_create

        btn_row.add_child(create_btn)
        btn_row.add_child(back_btn)

        # Assemble
        stack.add_child(title)
        stack.add_child(sep)
        stack.add_child(name_label)
        stack.add_child(name_input)
        stack.add_child(path_label)
        stack.add_child(path_row)
        stack.add_child(btn_row)

        panel.add_child(stack)
        bg.add_child(panel)
        self.ui.root = bg

    # --- Helpers ---

    def _make_background(self) -> Panel:
        """Create full-screen background panel with wallpaper."""
        bg = Panel()
        bg.preferred_width = pct(100)
        bg.preferred_height = pct(100)
        bg.background_color = (0.05, 0.05, 0.08, 1)
        if os.path.exists(self._bg_image_path):
            bg.background_image = self._bg_image_path
        return bg

    def _make_project_row(self, entry: dict) -> Panel:
        """Create a clickable row for a recent project entry."""
        project_path = entry["path"]
        project_name = entry.get("name", "???")
        project_dir = os.path.dirname(project_path)

        row = Panel()
        row.background_color = (0.18, 0.18, 0.22, 0.8)
        row.border_radius = 6
        row.padding = 10

        content = HStack()
        content.spacing = 16
        content.alignment = "center"

        name_lbl = Label()
        name_lbl.text = project_name
        name_lbl.font_size = 15
        name_lbl.color = (0.95, 0.95, 1.0, 1.0)

        path_lbl = Label()
        path_lbl.text = project_dir
        path_lbl.font_size = 12
        path_lbl.color = (0.45, 0.45, 0.5, 1.0)

        content.add_child(name_lbl)
        content.add_child(path_lbl)
        row.add_child(content)

        # Make the whole row clickable via a transparent button overlay
        btn = Button()
        btn.text = ""
        btn.preferred_width = pct(100)
        btn.preferred_height = pct(100)
        btn.background_color = (0, 0, 0, 0)
        btn.hover_color = (0.3, 0.5, 0.8, 0.15)
        btn.pressed_color = (0.2, 0.4, 0.7, 0.25)
        btn.border_radius = 6
        btn.anchor = "top-left"

        def on_click(p=project_path):
            self._launch_editor(p)

        btn.on_click = on_click
        row.add_child(btn)

        return row

    def _launch_editor(self, project_path: str):
        """Launch termin_editor with the given project and quit the launcher."""
        editor_exe = _find_editor_executable()
        if editor_exe is None:
            log.error("Cannot find termin_editor executable")
            return

        write_launch_project(project_path)
        self.recent.add(project_path)

        log.info(f"Launching editor: {editor_exe} for project {project_path}")
        subprocess.Popen([editor_exe])
        self.should_quit = True

    def _on_open_project(self):
        """Handle 'Open Project' button."""
        path = _ask_open_project()
        if path:
            self._launch_editor(path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    """Entry point: create window, build UI, run event loop."""
    window, gl_context = _create_sdl_window("Termin Launcher", 1024, 640)

    graphics = OpenGLGraphicsBackend.get_instance()
    graphics.ensure_ready()
    set_default_graphics_backend(graphics)

    app = LauncherApp(graphics)

    sdl2.SDL_StartTextInput()

    event = sdl2.SDL_Event()
    running = True

    while running:
        if app.should_quit:
            running = False
            break

        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            etype = event.type

            if etype == sdl2.SDL_QUIT:
                running = False
            elif etype == sdl2.SDL_WINDOWEVENT:
                if event.window.event == video.SDL_WINDOWEVENT_CLOSE:
                    running = False
            elif etype == sdl2.SDL_MOUSEMOTION:
                app.ui.mouse_move(float(event.motion.x), float(event.motion.y))
            elif etype == sdl2.SDL_MOUSEBUTTONDOWN:
                app.ui.mouse_down(float(event.button.x), float(event.button.y))
            elif etype == sdl2.SDL_MOUSEBUTTONUP:
                app.ui.mouse_up(float(event.button.x), float(event.button.y))
            elif etype == sdl2.SDL_KEYDOWN:
                scancode = event.key.keysym.scancode
                key = _translate_sdl_key(scancode)
                mods = _translate_sdl_mods(sdl2.SDL_GetModState())
                app.ui.key_down(key, mods)
            elif etype == sdl2.SDL_TEXTINPUT:
                text = event.text.text.decode('utf-8')
                app.ui.text_input(text)

        vw, vh = _get_drawable_size(window)
        graphics.bind_framebuffer(None)
        graphics.set_viewport(0, 0, vw, vh)
        graphics.clear_color_depth(0.08, 0.08, 0.10, 1.0)

        app.ui.render(vw, vh)

        video.SDL_GL_SwapWindow(window)

    video.SDL_GL_DeleteContext(gl_context)
    video.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()


if __name__ == "__main__":
    run()
