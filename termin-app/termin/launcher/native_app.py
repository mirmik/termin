"""Native projection and host for the toolkit-neutral launcher controller."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Callable

from termin.gui_native import (
    CollectionItem,
    CollectionModel,
    Color,
    Document,
    EdgeInsets,
    ImageFit,
    StyleField,
    StyleOverride,
    StyleRole,
)
from termin.launcher.controller import LauncherController, LauncherScreen


_logger = logging.getLogger(__name__)


class NativeLauncherProjection:
    """Project launcher screens expressed entirely with native widgets."""

    def __init__(
        self,
        document: Document,
        controller: LauncherController,
        *,
        request_render: Callable[[], None] = lambda: None,
    ) -> None:
        self.document = document
        self.controller = controller
        self.request_render = request_render
        self.root = None
        self.widgets: dict[str, object] = {}
        self.models: dict[str, object] = {}
        self._recent_paths: tuple[str, ...] = ()
        self._configure_theme()
        self._build_current_screen()

    def _configure_theme(self) -> None:
        theme = self.document.theme
        button = theme.role(StyleRole.Button)
        button.base.background = Color(0.25, 0.25, 0.30, 1.0)
        button.base.foreground = Color(1.0, 1.0, 1.0, 1.0)
        button.base.corner_radius = 6.0
        button.hovered.value.background = Color(0.35, 0.35, 0.40, 1.0)
        button.pressed.value.background = Color(0.18, 0.18, 0.22, 1.0)
        button.disabled.value.background = Color(0.18, 0.18, 0.20, 0.60)
        button.disabled.value.foreground = Color(0.50, 0.50, 0.50, 1.0)

        text_input = theme.role(StyleRole.TextInput)
        text_input.base.background = Color(0.105, 0.105, 0.125, 0.96)
        text_input.base.foreground = Color(0.92, 0.93, 0.96, 1.0)
        text_input.base.border_width = 0.0
        self.document.theme = theme

    @staticmethod
    def _style(
        widget,
        *,
        font_size: float | None = None,
        foreground: Color | None = None,
        background: Color | None = None,
        corner_radius: float | None = None,
    ) -> None:
        style = StyleOverride()
        fields = 0
        if font_size is not None:
            fields |= StyleField.FontSize
            style.value.font_size = font_size
        if foreground is not None:
            fields |= StyleField.Foreground
            style.value.foreground = foreground
        if background is not None:
            fields |= StyleField.Background
            style.value.background = background
        if corner_radius is not None:
            fields |= StyleField.CornerRadius
            style.value.corner_radius = corner_radius
        style.fields = fields
        widget.style_override = style

    def _replace_root(self, root) -> None:
        if self.root is not None and self.document.is_alive(self.root.handle):
            self.document.destroy_widget_recursive(self.root.handle)
        self.root = root
        if not self.document.add_root(root.handle):
            raise RuntimeError("failed to add native launcher root")
        self.request_render()

    def _screen_frame(self, stable_id: str, panel_height: float | None = None):
        root = self.document.create_vstack(f"native-{stable_id}")
        root.stable_id = stable_id
        row = self.document.create_hstack(f"{stable_id}-center-row")
        left = self.document.create_hstack(f"{stable_id}-left-space")
        right = self.document.create_hstack(f"{stable_id}-right-space")
        panel = self.document.create_vstack(f"{stable_id}-panel")
        panel.stable_id = f"{stable_id}.panel"
        panel.set_layout_background(Color(0.12, 0.12, 0.16, 0.90))
        panel.set_layout_corner_radius(12.0)
        panel.set_layout_padding(EdgeInsets(30.0, 28.0, 30.0, 28.0))
        panel.set_layout_spacing(12.0)

        row.add_stretch_child(left)
        row.add_fixed_child(panel, 684.0)
        row.add_stretch_child(right)
        if panel_height is None:
            root.add_stretch_child(row)
        else:
            top = self.document.create_vstack(f"{stable_id}-top-space")
            bottom = self.document.create_vstack(f"{stable_id}-bottom-space")
            root.add_stretch_child(top)
            root.add_fixed_child(row, panel_height)
            root.add_stretch_child(bottom)
        return root, panel

    def _button(self, text: str, stable_id: str, callback: Callable[[], None]):
        button = self.document.create_button(text, stable_id)
        button.widget.stable_id = stable_id
        button.connect_clicked(callback)
        return button

    def _add_heading(self, panel, title: str, subtitle: str) -> None:
        heading = self.document.create_label(title, "launcher-heading")
        heading.stable_id = "launcher.heading"
        self._style(heading, font_size=28.0, foreground=Color(1.0, 1.0, 1.0, 1.0))
        subheading = self.document.create_label(subtitle, "launcher-subheading")
        subheading.stable_id = "launcher.subheading"
        self._style(
            subheading,
            font_size=14.0,
            foreground=Color(0.55, 0.60, 0.70, 1.0),
        )
        panel.add_fixed_child(heading, 42.0)
        panel.add_fixed_child(subheading, 24.0)
        panel.add_fixed_child(self._separator(horizontal=True), 1.0)

    def _section_label(self, text: str):
        label = self.document.create_label(text)
        self._style(label, font_size=13.0, foreground=Color(0.60, 0.60, 0.65, 1.0))
        return label

    def _separator(self, *, horizontal: bool):
        separator = (
            self.document.create_hstack("launcher-horizontal-separator")
            if horizontal
            else self.document.create_vstack("launcher-vertical-separator")
        )
        separator.set_layout_background(Color(0.30, 0.30, 0.35, 1.0))
        return separator

    def _add_error(self, panel) -> None:
        error = self.document.create_label("", "launcher-error")
        error.stable_id = "launcher.error"
        panel.add_fixed_child(error, 30.0)
        self.widgets["error"] = error
        self._sync_error()

    def _build_current_screen(self) -> None:
        self.widgets = {}
        self.models = {}
        if self.controller.state.screen == LauncherScreen.NEW_PROJECT:
            self._build_new_project()
        else:
            self._build_main()

    def close(self) -> None:
        """Release widget callbacks before the owning document shuts down."""
        if self.root is not None and self.document.is_alive(self.root.handle):
            self.document.destroy_widget_recursive(self.root.handle)
        self.root = None
        self.widgets.clear()
        self.models.clear()

    def _build_main(self) -> None:
        root, panel = self._screen_frame("launcher.main")
        self._add_heading(panel, "Termin Engine", "Project Launcher")

        columns = self.document.create_hstack("launcher-main-columns")
        columns.set_layout_spacing(20.0)
        recent_column = self.document.create_vstack("launcher-recent-column")
        recent_column.set_layout_spacing(6.0)
        recent_column.add_fixed_child(self._section_label("Recent Projects"), 26.0)

        model = CollectionModel()
        projects = self.controller.state.recent_projects
        model.set_items(
            [
                CollectionItem(f"recent:{project.path}", project.name, os.path.dirname(project.path))
                for project in projects
            ]
        )
        self._recent_paths = tuple(project.path for project in projects)
        project_list = self.document.create_list_widget(model)
        project_list.widget.stable_id = "launcher.recent-projects"
        self._style(project_list.widget, font_size=14.0)
        recent_column.add_stretch_child(project_list.widget)

        actions = self.document.create_vstack("launcher-actions")
        actions.set_layout_spacing(8.0)
        actions.add_fixed_child(self._section_label("Actions"), 26.0)
        new_button = self._button("New Project", "launcher.action.new", self._show_new_project)
        self._style(
            new_button.widget,
            background=Color(0.20, 0.45, 0.80, 1.0),
            corner_radius=6.0,
        )
        open_button = self._button("Open Project", "launcher.action.open", self._open_selected)
        browse_button = self._button(
            "Open Existing...", "launcher.action.open-existing", self._open_existing
        )
        remove_button = self._button(
            "Remove from List", "launcher.action.remove", self._remove_selected
        )
        for button in (new_button, open_button):
            actions.add_fixed_child(button.widget, 38.0)
        actions.add_fixed_child(self._separator(horizontal=True), 1.0)
        for button in (browse_button, remove_button):
            actions.add_fixed_child(button.widget, 38.0)

        columns.add_stretch_child(recent_column)
        columns.add_fixed_child(self._separator(horizontal=False), 1.0)
        columns.add_fixed_child(actions, 156.0)
        panel.add_stretch_child(columns)
        self.widgets.update(
            {
                "recent_list": project_list,
                "new": new_button,
                "open": open_button,
                "open_existing": browse_button,
                "remove": remove_button,
            }
        )
        self.models["recent"] = model
        project_list.connect_selection_changed(self._selection_changed)
        project_list.connect_activated(self._project_activated)
        self._sync_selection_actions()
        self._add_error(panel)
        self._replace_root(root)

    def _build_new_project(self) -> None:
        root, panel = self._screen_frame("launcher.new-project", 470.0)
        self._add_heading(panel, "New Project", "Create a Termin project")

        name_label = self.document.create_label("Project Name")
        name_input = self.document.create_text_input(self.controller.state.new_project_name)
        name_input.widget.stable_id = "launcher.new-project.name"
        location_label = self.document.create_label("Location")
        location_row = self.document.create_hstack("launcher-location-row")
        location_row.set_layout_spacing(8.0)
        location_input = self.document.create_text_input(
            self.controller.state.new_project_location
        )
        location_input.widget.stable_id = "launcher.new-project.location"
        browse = self._button(
            "Browse...", "launcher.new-project.browse", self._choose_location
        )
        location_row.add_stretch_child(location_input.widget)
        location_row.add_fixed_child(browse.widget, 120.0)

        actions = self.document.create_hstack("launcher-new-project-actions")
        actions.set_layout_spacing(10.0)
        actions.add_stretch_child(self.document.create_label(""))
        create = self._button("Create", "launcher.new-project.create", self._create_project)
        back = self._button("Back", "launcher.new-project.back", self._show_main)
        actions.add_fixed_child(create.widget, 120.0)
        actions.add_fixed_child(back.widget, 120.0)

        panel.add_fixed_child(name_label, 24.0)
        panel.add_fixed_child(name_input.widget, 38.0)
        panel.add_fixed_child(location_label, 24.0)
        panel.add_fixed_child(location_row, 38.0)
        panel.add_stretch_child(self.document.create_vstack("launcher-form-space"))
        panel.add_fixed_child(actions, 40.0)
        self.widgets.update(
            {
                "name": name_input,
                "location": location_input,
                "browse": browse,
                "create": create,
                "back": back,
            }
        )
        name_input.connect_changed(self.controller.set_new_project_name)
        location_input.connect_changed(self.controller.set_new_project_location)
        name_input.connect_submitted(lambda _text: self._create_project())
        location_input.connect_submitted(lambda _text: self._create_project())
        self._add_error(panel)
        self._replace_root(root)

    def _sync_error(self) -> None:
        error = self.widgets.get("error")
        if error is None:
            return
        message = self.controller.state.last_error or ""
        error.text = message
        error.visible = bool(message)

    def _sync_selection_actions(self) -> None:
        enabled = self.controller.state.can_open_selected
        self.widgets["open"].widget.enabled = enabled
        self.widgets["remove"].widget.enabled = enabled

    def _selection_changed(self, selected: list[int]) -> None:
        path = self._recent_paths[selected[0]] if selected else None
        self.controller.select_project(path)
        self._sync_selection_actions()
        self.request_render()

    def _project_activated(self, index: int, _item: CollectionItem) -> None:
        opened = self.controller.open_project(self._recent_paths[index])
        if opened and not self.controller.state.should_quit:
            self._build_current_screen()
            return
        self._sync_error()
        self.request_render()

    def _show_new_project(self) -> None:
        self.controller.show_new_project_screen()
        self._build_current_screen()

    def _show_main(self) -> None:
        self.controller.show_main_screen()
        self._build_current_screen()

    def _open_selected(self) -> None:
        opened = self.controller.open_selected_project()
        if opened and not self.controller.state.should_quit:
            self._build_current_screen()
            return
        self._sync_error()
        self.request_render()

    def _open_existing(self) -> None:
        opened = self.controller.open_existing_project()
        if opened and not self.controller.state.should_quit:
            self._build_current_screen()
            return
        self._sync_error()
        self.request_render()

    def _remove_selected(self) -> None:
        if self.controller.remove_selected_project():
            self._build_current_screen()
        else:
            self._sync_error()
            self.request_render()

    def _choose_location(self) -> None:
        chosen = self.controller.choose_new_project_location()
        if chosen is not None:
            location = self.widgets["location"]
            location.text = chosen
            location.caret = len(chosen)
        self._sync_error()
        self.request_render()

    def _create_project(self) -> None:
        self.controller.create_new_project()
        self._sync_error()
        self.request_render()


def _install_background(host) -> Callable[[], None] | None:
    image_path = Path(__file__).with_name("back.png")
    if not image_path.is_file():
        _logger.warning("Native launcher background is missing: %s", image_path)
        return None
    try:
        from termin.image import decode_rgba8_file

        pixels = decode_rgba8_file(image_path).to_numpy()
        image = host.document.create_image_widget()
        image.widget.stable_id = "launcher.background"
        image.widget.mouse_transparent = True
        image.fit = ImageFit.Cover
        if not host.document.add_root(image.handle):
            raise RuntimeError("failed to add native launcher background root")
        return host.register_image_preview(image, pixels, max_dimension=None)
    except Exception:
        _logger.exception("Failed to load native launcher background")
        return None


def _smoke_frame_limit() -> int:
    raw = os.environ.get("TERMIN_LAUNCHER_NATIVE_SMOKE_FRAMES", "0")
    try:
        value = int(raw)
    except ValueError:
        _logger.error("Invalid TERMIN_LAUNCHER_NATIVE_SMOKE_FRAMES=%r", raw)
        return 0
    return max(0, value)


def run_native_launcher(controller: LauncherController) -> None:
    """Own the native launcher window until an editor starts or it closes."""
    from termin.display import WindowManager, WindowedGraphicsSession, quit_sdl
    from termin.editor_core.application_icon import apply_editor_window_icon
    from termin.editor_core.shader_runtime import configure_sdk_shader_runtime
    from termin.editor_native.ui_host import NativeWidgetContent
    from tgfx import Tgfx2Context

    configure_sdk_shader_runtime("launcher-native")
    graphics_session = WindowedGraphicsSession.create_native()
    window_manager = None
    window = None
    host = None
    release_background = None
    projection = None
    try:
        graphics = Tgfx2Context.from_runtime(graphics_session.graphics)
        window_manager = WindowManager(graphics_session)
        window_handle = window_manager.create_window(
            "Termin Launcher",
            1024,
            640,
        )
        host = NativeWidgetContent(
            window_manager,
            window_handle,
            graphics=graphics,
        )
        window = host.window
        apply_editor_window_icon(window)
        release_background = _install_background(host)
        projection = NativeLauncherProjection(
            host.document,
            controller,
            request_render=host.request_render_update,
        )
        frame_limit = _smoke_frame_limit()
        frame_count = 0
        host.render()
        while not window.should_close() and not controller.state.should_quit:
            window_manager.pump_events()
            keep_running, _event_count = host.poll_events()
            if not keep_running:
                break
            if host.render_requested:
                host.render()
            else:
                time.sleep(0.01)
            frame_count += 1
            if frame_limit > 0 and frame_count >= frame_limit:
                window.set_should_close(True)
        _ = projection
    finally:
        if projection is not None:
            projection.close()
        if release_background is not None:
            release_background()
        if host is not None:
            host.close()
        if window_manager is not None:
            window_manager.close()
        try:
            graphics_session.close()
        finally:
            quit_sdl()


__all__ = ["NativeLauncherProjection", "run_native_launcher"]
