"""Termin Launcher: project selection and creation UI."""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys

from termin.editor_core.shader_runtime import configure_sdk_shader_runtime
from termin.launcher.controller import (
    LaunchResult,
    LauncherController,
    LauncherServices,
)
from termin.launcher.recent import RecentProjects, write_launch_project
from termin.project import create_project


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Window helpers
# ---------------------------------------------------------------------------

def _get_drawable_size_from_backend(window) -> tuple[int, int]:
    """Drawable size for a BackendWindow (handles HiDPI + post-resize)."""
    return window.framebuffer_size()


def _event_key(value: int):
    from tcbase import Key

    try:
        return Key(int(value))
    except ValueError:
        log.debug(f"Unrecognized native key value {value}")
        return Key.UNKNOWN


def _event_button(value: int):
    from tcbase import MouseButton

    try:
        return MouseButton(int(value))
    except ValueError:
        log.debug(f"Unrecognized native mouse button value {value}")
        return MouseButton.LEFT


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
    candidate_names = ["termin_editor.exe", "termin_editor"] if os.name == "nt" else ["termin_editor"]
    candidate_dirs: list[str] = []

    termin_sdk = os.environ.get("TERMIN_SDK")
    if termin_sdk:
        candidate_dirs.append(os.path.join(termin_sdk, "bin"))

    if os.name == "nt":
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, len(buffer))
            if size:
                candidate_dirs.append(os.path.dirname(buffer.value))
        except Exception:
            log.debug("Cannot resolve executable path via GetModuleFileNameW")
    else:
        try:
            candidate_dirs.append(os.path.dirname(os.readlink("/proc/self/exe")))
        except (OSError, AttributeError):
            log.debug("Cannot resolve /proc/self/exe")

    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and argv0 not in {"-c", ""}:
        candidate_dirs.append(os.path.dirname(os.path.abspath(argv0)))

    seen_dirs = set()
    for candidate_dir in candidate_dirs:
        if not candidate_dir:
            continue
        normalized_dir = os.path.normcase(os.path.abspath(candidate_dir))
        if normalized_dir in seen_dirs:
            continue
        seen_dirs.add(normalized_dir)
        for name in candidate_names:
            editor = os.path.join(candidate_dir, name)
            if os.path.isfile(editor):
                return editor

    import shutil
    for name in candidate_names:
        editor = shutil.which(name)
        if editor:
            return editor
    return None


def _editor_launch_env(editor_exe: str) -> dict[str, str]:
    env = os.environ.copy()
    lib_dir = os.path.normpath(os.path.join(os.path.dirname(editor_exe), "..", "lib"))
    if os.name == "nt":
        prev = env.get("PATH", "")
        env["PATH"] = f"{lib_dir}{os.pathsep}{prev}" if prev else lib_dir
    else:
        prev = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{lib_dir}{os.pathsep}{prev}" if prev else lib_dir
    return env


def _launcher_mode() -> str:
    mode = os.environ.get("TERMIN_LAUNCHER_MODE", "").strip().lower()
    if not mode:
        return "spawn" if os.name == "nt" else "exec"
    if mode not in {"exec", "spawn"}:
        log.warning(f"Unsupported TERMIN_LAUNCHER_MODE={mode!r}, using spawn")
        return "spawn"
    if mode == "exec" and os.name == "nt":
        log.warning("TERMIN_LAUNCHER_MODE=exec is not supported on Windows, using spawn")
        return "spawn"
    return mode


def _launch_editor_process(editor_exe: str, project_path: str) -> bool:
    """Transfer control to termin_editor.

    The default Linux path uses exec so debugger/profiler sessions attached to
    termin_launcher continue with termin_editor under the same process id.
    Set TERMIN_LAUNCHER_MODE=spawn to keep the historical detached launch.
    """
    env = _editor_launch_env(editor_exe)
    args = [editor_exe, project_path]
    mode = _launcher_mode()
    log.info(f"Launching editor: {editor_exe} for project {project_path} mode={mode}")
    if mode == "exec":
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            os.execvpe(editor_exe, args, env)
        except OSError as exc:
            log.error(f"Failed to exec termin_editor: {exc}")
        return False
    subprocess.Popen(args, env=env)
    return True


def _dispatch_editor(project_path: str) -> LaunchResult:
    """Platform adapter used by the toolkit-neutral launcher controller."""
    editor_exe = _find_editor_executable()
    if editor_exe is None:
        return LaunchResult(started=False, error="Cannot find termin_editor executable")
    write_launch_project(project_path)
    started = _launch_editor_process(editor_exe, project_path)
    if not started:
        return LaunchResult(started=False, error="Failed to launch termin_editor")
    return LaunchResult(started=True, should_quit=True)


def _create_launcher_controller() -> LauncherController:
    return LauncherController(
        RecentProjects(),
        LauncherServices(
            choose_directory=_ask_directory,
            choose_project_file=_ask_open_project,
            create_project=create_project,
            launch_editor=_dispatch_editor,
            report_error=log.error,
        ),
    )


# ---------------------------------------------------------------------------
# Launcher app
# ---------------------------------------------------------------------------

def _load_tcgui_symbols() -> None:
    """Load the legacy projection only when explicitly requested."""
    global UI, Label, Button, TextInput, Separator, ListWidget
    global HStack, VStack, Panel, px, pct

    from tcgui.widgets.ui import UI
    from tcgui.widgets.basic import Label, Button, TextInput, Separator, ListWidget
    from tcgui.widgets.containers import HStack, VStack, Panel
    from tcgui.widgets.units import px, pct


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

    def __init__(self, graphics, controller: LauncherController):
        self.ui = UI(graphics=graphics)
        self.controller = controller
        self._bg_image_path = os.path.join(os.path.dirname(__file__), "back.png")

        # Selection-dependent buttons (updated when selection changes)
        self._open_btn: Button | None = None
        self._remove_btn: Button | None = None
        self._project_list: ListWidget | None = None

        self.show_main_screen()

    @property
    def should_quit(self) -> bool:
        return self.controller.state.should_quit

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
        for entry in self.controller.state.recent_projects:
            items.append({
                "text": entry.name,
                "subtitle": os.path.dirname(entry.path),
                "data": entry.path,
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
        new_btn.on_click = self._on_show_new_project
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
        name_input.text = self.controller.state.new_project_name
        name_input.on_changed = self.controller.set_new_project_name

        path_input.text = self.controller.state.new_project_location
        path_input.on_changed = self.controller.set_new_project_location
        path_input.preferred_width = px(320)
        path_input.font_size = 15

        browse_btn = Button()
        browse_btn.text = "Browse..."
        browse_btn.font_size = 13
        browse_btn.padding = 8
        browse_btn.background_color = (0.25, 0.25, 0.3, 1.0)
        browse_btn.hover_color = (0.35, 0.35, 0.4, 1.0)

        def on_browse():
            chosen = self.controller.choose_new_project_location()
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
        back_btn.on_click = self._on_show_main

        def on_create():
            self.controller.set_new_project_name(name_input.text)
            self.controller.set_new_project_location(path_input.text)
            self.controller.create_new_project()

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

    def _on_show_main(self) -> None:
        self.controller.show_main_screen()
        self.show_main_screen()

    def _on_show_new_project(self) -> None:
        self.controller.show_new_project_screen()
        self.show_new_project_screen()

    def _on_project_select(self, index: int, item: dict) -> None:
        """Single click — select project, enable Open/Remove buttons."""
        self.controller.select_project(item["data"])
        enabled = self.controller.state.can_open_selected
        if self._open_btn is not None:
            self._set_button_enabled(self._open_btn, enabled)
        if self._remove_btn is not None:
            self._set_button_enabled(self._remove_btn, enabled)

    def _on_project_activate(self, index: int, item: dict) -> None:
        """Double click — open project."""
        self.controller.open_project(item["data"])

    def _on_open_selected(self) -> None:
        """Open the currently selected project."""
        self.controller.open_selected_project()

    def _on_remove_selected(self) -> None:
        """Remove the currently selected project from the recent list."""
        if self.controller.remove_selected_project():
            self.show_main_screen()

    def _on_open_project(self) -> None:
        """Handle 'Open Existing...' button — file dialog for .terminproj."""
        self.controller.open_existing_project()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_launcher_args() -> tuple[str | None, str | None]:
    """Parse command-line arguments.

    Returns (project_path_or_sentinel, accepted_ui_arg_or_None).
    project is None for UI mode, "__help__"/"__error__" for early exit.
    """
    import sys
    from termin.launcher.recent import resolve_project_path

    args = sys.argv[1:]

    if '-h' in args or '--help' in args:
        print("Usage: termin_launcher [OPTIONS] [PROJECT]")
        print()
        print("Termin project launcher.")
        print()
        print("Arguments:")
        print("  PROJECT         Path to .terminproj file or project directory")
        print()
        print("Without PROJECT, opens the launcher UI.")
        print()
        print("Options:")
        print("  --ui=native     Select the native launcher UI (default)")
        print("  --ui=tcgui      Select the legacy comparison UI")
        print("  -h, --help      Show this help message and exit")
        print()
        print("Environment:")
        print("  TERMIN_LAUNCHER_MODE=exec|spawn")
        print("                  Linux default is exec, keeping debugger/profiler attached")
        print("                  to the same process. Windows default is spawn.")
        sys.stdout.flush()
        return "__help__", None

    ui_backend: str | None = None
    positional = []
    for a in args:
        if a.startswith('--ui='):
            ui_backend = a.split('=', 1)[1]
            if ui_backend not in {"native", "tcgui"}:
                print(
                    f"Error: unsupported launcher UI backend '{ui_backend}'. "
                    "Expected native or tcgui.",
                    flush=True,
                )
                return "__error__", None
        elif not a.startswith('-'):
            positional.append(a)

    project: str | None = None
    if positional:
        resolved = resolve_project_path(positional[0])
        if resolved is None:
            print(f"Error: cannot find .terminproj at '{positional[0]}'", flush=True)
            return "__error__", None
        project = resolved

    return project, ui_backend


def _run_tcgui(controller: LauncherController) -> None:
    """Run the legacy projection without making it part of default startup."""
    _load_tcgui_symbols()
    configure_sdk_shader_runtime("launcher-tcgui")

    from tcbase import Key, MouseButton
    from termin.display import WindowedGraphicsSession, quit_sdl, start_text_input, wait_sdl_events_timeout
    from tgfx import Tgfx2Context
    from termin.editor_core.application_icon import apply_editor_window_icon

    graphics_session = WindowedGraphicsSession.create_native()
    window = None
    graphics = None
    app = None
    try:
        window = graphics_session.create_window("Termin Launcher — tcgui", 1024, 640)
        apply_editor_window_icon(window)
        graphics = Tgfx2Context.from_runtime(graphics_session.graphics)

        app = LauncherApp(graphics=graphics, controller=controller)
        presenting = False

        def present_ui() -> None:
            nonlocal presenting
            if presenting:
                return
            presenting = True
            try:
                vw, vh = _get_drawable_size_from_backend(window)
                if vw <= 0 or vh <= 0:
                    return
                tex = app.ui.render_compose(vw, vh, background_color=(0.08, 0.08, 0.10, 1.0))
                if tex is not None:
                    window.present(tex)
            finally:
                presenting = False

        app.ui.on_present_requested = present_ui
        present_ui()

        start_text_input()
        running = True

        def dispatch_event(ev):
            nonlocal running
            etype = ev.get("type")
            if etype == "quit":
                running = False
            elif etype == "window_close":
                running = False
            elif etype == "mouse_move":
                app.ui.mouse_move(float(ev.get("x", 0.0)), float(ev.get("y", 0.0)), int(ev.get("mods", 0)))
            elif etype == "mouse_down":
                app.ui.mouse_down(float(ev.get("x", 0.0)), float(ev.get("y", 0.0)), _event_button(int(ev.get("button", MouseButton.LEFT.value))), int(ev.get("mods", 0)))
            elif etype == "mouse_up":
                app.ui.mouse_up(float(ev.get("x", 0.0)), float(ev.get("y", 0.0)), _event_button(int(ev.get("button", MouseButton.LEFT.value))), int(ev.get("mods", 0)))
            elif etype == "key_down":
                app.ui.key_down(_event_key(int(ev.get("key", Key.UNKNOWN.value))), int(ev.get("mods", 0)))
            elif etype == "text_input":
                app.ui.text_input(str(ev.get("text", "")))

        while running and not app.should_quit:
            for event in wait_sdl_events_timeout(500):
                dispatch_event(event)
            if running:
                present_ui()
    finally:
        if window is not None:
            window.close()
        try:
            graphics_session.close()
        finally:
            quit_sdl()


def run():
    """Parse arguments and route to the native or explicit legacy projection."""
    project, ui_backend = _parse_launcher_args()
    if project == "__help__":
        return
    if project == "__error__":
        return

    if project is not None:
        # Direct launch: skip UI, open editor with given project
        _create_launcher_controller().open_project(project)
        return

    controller = _create_launcher_controller()
    if ui_backend == "tcgui":
        _run_tcgui(controller)
        return

    from termin.launcher.native_app import run_native_launcher

    run_native_launcher(controller)


if __name__ == "__main__":
    run()
