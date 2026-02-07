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
from termin.visualization.ui.widgets.basic import Label, Button, TextInput, Separator, ListWidget
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

    # Button color presets
    _BTN_PRIMARY = (0.2, 0.45, 0.8, 1.0)
    _BTN_PRIMARY_HOVER = (0.25, 0.55, 0.9, 1.0)
    _BTN_PRIMARY_PRESSED = (0.15, 0.35, 0.7, 1.0)
    _BTN_NORMAL = (0.25, 0.25, 0.3, 1.0)
    _BTN_NORMAL_HOVER = (0.35, 0.35, 0.4, 1.0)
    _BTN_NORMAL_PRESSED = (0.18, 0.18, 0.22, 1.0)
    _BTN_DISABLED = (0.18, 0.18, 0.2, 0.6)

    def __init__(self, graphics: OpenGLGraphicsBackend):
        self.graphics = graphics
        self.ui = UI(graphics)
        self.recent = RecentProjects()
        self._bg_image_path = os.path.join(os.path.dirname(__file__), "back.png")
        self.should_quit: bool = False

        # Selection-dependent buttons (updated when selection changes)
        self._open_btn: Button | None = None
        self._remove_btn: Button | None = None
        self._project_list: ListWidget | None = None

        self.show_main_screen()

    # --- Screen builders ---

    def show_main_screen(self):
        """Build and show the main launcher screen."""
        bg = self._make_background()

        panel = Panel()
        panel.background_color = (0.12, 0.12, 0.16, 0.90)
        panel.padding = 30
        panel.anchor = "center"
        panel.border_radius = 12

        outer = VStack()
        outer.spacing = 16
        outer.alignment = "left"

        # Title
        title = Label()
        title.text = "Termin Engine"
        title.font_size = 28
        title.color = (1.0, 1.0, 1.0, 1.0)

        subtitle = Label()
        subtitle.text = "Project Launcher"
        subtitle.font_size = 14
        subtitle.color = (0.55, 0.6, 0.7, 1.0)

        sep_top = Separator()
        sep_top.orientation = "horizontal"
        sep_top.color = (0.3, 0.3, 0.35, 1.0)

        outer.add_child(title)
        outer.add_child(subtitle)
        outer.add_child(sep_top)

        # --- Two-column layout ---
        columns = HStack()
        columns.spacing = 20
        columns.alignment = "top"

        # Left column: project list
        left_col = VStack()
        left_col.spacing = 8
        left_col.alignment = "left"

        recent_header = Label()
        recent_header.text = "Recent Projects"
        recent_header.font_size = 13
        recent_header.color = (0.6, 0.6, 0.65, 1.0)

        project_list = ListWidget()
        project_list.preferred_width = px(420)
        project_list.empty_text = "No recent projects"
        project_list.on_select = self._on_project_select
        project_list.on_activate = self._on_project_activate
        self._project_list = project_list

        # Populate list
        items = []
        for entry in self.recent.list()[:10]:
            items.append({
                "text": entry.get("name", "???"),
                "subtitle": os.path.dirname(entry["path"]),
                "data": entry["path"],
            })
        project_list.set_items(items)

        left_col.add_child(recent_header)
        left_col.add_child(project_list)

        # Vertical separator
        vsep = Separator()
        vsep.orientation = "vertical"
        vsep.color = (0.3, 0.3, 0.35, 1.0)

        # Right column: action buttons
        right_col = VStack()
        right_col.spacing = 8
        right_col.alignment = "left"

        actions_header = Label()
        actions_header.text = "Actions"
        actions_header.font_size = 13
        actions_header.color = (0.6, 0.6, 0.65, 1.0)

        new_btn = self._make_button("New Project", self._BTN_PRIMARY,
                                     self._BTN_PRIMARY_HOVER, self._BTN_PRIMARY_PRESSED)
        new_btn.on_click = self.show_new_project_screen
        new_btn.preferred_width = px(180)

        open_btn = self._make_button("Open Project", self._BTN_DISABLED,
                                      self._BTN_DISABLED, self._BTN_DISABLED)
        open_btn.text_color = (0.5, 0.5, 0.5, 1.0)
        open_btn.preferred_width = px(180)
        open_btn.on_click = self._on_open_selected
        self._open_btn = open_btn

        sep_btns = Separator()
        sep_btns.orientation = "horizontal"
        sep_btns.color = (0.3, 0.3, 0.35, 1.0)

        browse_btn = self._make_button("Open Existing...", self._BTN_NORMAL,
                                        self._BTN_NORMAL_HOVER, self._BTN_NORMAL_PRESSED)
        browse_btn.on_click = self._on_open_project
        browse_btn.preferred_width = px(180)

        remove_btn = self._make_button("Remove from List", self._BTN_DISABLED,
                                        self._BTN_DISABLED, self._BTN_DISABLED)
        remove_btn.text_color = (0.5, 0.5, 0.5, 1.0)
        remove_btn.preferred_width = px(180)
        remove_btn.on_click = self._on_remove_selected
        self._remove_btn = remove_btn

        right_col.add_child(actions_header)
        right_col.add_child(new_btn)
        right_col.add_child(open_btn)
        right_col.add_child(sep_btns)
        right_col.add_child(browse_btn)
        right_col.add_child(remove_btn)

        columns.add_child(left_col)
        columns.add_child(vsep)
        columns.add_child(right_col)
        outer.add_child(columns)

        panel.add_child(outer)
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

    def _make_button(self, text: str, bg: tuple, hover: tuple, pressed: tuple) -> Button:
        """Create a styled button."""
        btn = Button()
        btn.text = text
        btn.font_size = 14
        btn.padding = 10
        btn.background_color = bg
        btn.hover_color = hover
        btn.pressed_color = pressed
        btn.border_radius = 6
        return btn

    def _set_button_enabled(self, btn: Button, enabled: bool) -> None:
        """Update button appearance based on enabled state."""
        btn.enabled = enabled
        if enabled:
            btn.background_color = self._BTN_NORMAL
            btn.hover_color = self._BTN_NORMAL_HOVER
            btn.pressed_color = self._BTN_NORMAL_PRESSED
            btn.text_color = (1.0, 1.0, 1.0, 1.0)
        else:
            btn.background_color = self._BTN_DISABLED
            btn.hover_color = self._BTN_DISABLED
            btn.pressed_color = self._BTN_DISABLED
            btn.text_color = (0.5, 0.5, 0.5, 1.0)

    # --- Project list callbacks ---

    def _on_project_select(self, index: int, item: dict) -> None:
        """Single click — select project, enable Open/Remove buttons."""
        if self._open_btn is not None:
            self._set_button_enabled(self._open_btn, True)
        if self._remove_btn is not None:
            self._set_button_enabled(self._remove_btn, True)

    def _on_project_activate(self, index: int, item: dict) -> None:
        """Double click — open project."""
        self._launch_editor(item["data"])

    def _on_open_selected(self) -> None:
        """Open the currently selected project."""
        if self._project_list is None:
            return
        item = self._project_list.selected_item
        if item is None:
            return
        self._launch_editor(item["data"])

    def _on_remove_selected(self) -> None:
        """Remove the currently selected project from the recent list."""
        if self._project_list is None:
            return
        item = self._project_list.selected_item
        if item is None:
            return
        self.recent.remove(item["data"])
        # Rebuild screen
        self.show_main_screen()

    def _launch_editor(self, project_path: str) -> None:
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

    def _on_open_project(self) -> None:
        """Handle 'Open Existing...' button — file dialog for .terminproj."""
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
