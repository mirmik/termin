"""termin-gui-native standalone application for procedural CSG documents."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from termin.base import log
from termin.gui_native import (
    CommandData,
    CommandKind,
    CommandModel,
    FileDialogMode,
    FileDialogModel,
    MenuBarEntry,
    Rect,
    Size,
    TcDocument,
    tc_ui_document_create,
    tc_ui_document_destroy,
)

from termin.csg.cad_model import StandaloneCsgModel
from termin.csg.cad_state import CAD_STATE_FILTER
from termin.csg.cad_viewer import CsgSceneRenderer
from termin.csg.native_cad_viewport import NativeCadViewportSurface
from termin.csg.native_editor_panel import build_native_csg_editor_panel


class CadApp:
    """Compose the shared CSG model into one native standalone document."""

    def __init__(
        self,
        ui_document: TcDocument | None = None,
        *,
        request_render: Callable[[], None] | None = None,
    ) -> None:
        self._owns_ui_document = ui_document is None
        self.ui_document = ui_document if ui_document is not None else tc_ui_document_create()
        self._external_request_render = request_render if request_render is not None else (lambda: None)
        self.model = StandaloneCsgModel(self._request_render)
        self.controller = self.model.controller
        self.camera = self.model.camera
        self.surface = NativeCadViewportSurface(self.camera)
        self.surface.on_changed = self.model.request_render
        self.surface.on_scene_mouse_down = self.model.scene_mouse_down
        self.surface.on_scene_mouse_move = self.model.scene_mouse_move
        self.surface.on_scene_mouse_up = self.model.scene_mouse_up
        self.surface.on_scene_click = self.model.scene_click
        self.root = None
        self.viewport = None
        self.editor_panel = None
        self.menu_bar = None
        self.file_label = None
        self.wireframe_check = None
        self._dialogs: dict[int, object] = {}
        self._closed = False

    @property
    def document(self):
        return self.controller.document

    @document.setter
    def document(self, value) -> None:
        self.controller.replace_document(value)
        self.model.request_preview_rebuild()

    @property
    def draft(self):
        return self.controller.draft

    @draft.setter
    def draft(self, value) -> None:
        self.controller.draft = value

    @property
    def selected_node_data(self) -> tuple[str, str] | None:
        return self.controller.selection

    @selected_node_data.setter
    def selected_node_data(self, value: tuple[str, str] | None) -> None:
        self.controller.selection = value

    @property
    def mode(self) -> str:
        return self.controller.mode

    @mode.setter
    def mode(self, value: str) -> None:
        self.controller.mode = str(value)

    @property
    def current_path(self) -> Path | None:
        return self.model.current_path

    @current_path.setter
    def current_path(self, value: Path | None) -> None:
        self.model.current_path = value

    @property
    def last_directory(self) -> Path:
        return self.model.last_directory

    @last_directory.setter
    def last_directory(self, value: Path) -> None:
        self.model.last_directory = value

    @property
    def show_wireframe(self) -> bool:
        return self.model.show_wireframe

    @show_wireframe.setter
    def show_wireframe(self, visible: bool) -> None:
        self.model.show_wireframe = bool(visible)

    @property
    def dirty(self) -> bool:
        return self.model.dirty

    @property
    def preview_revision(self) -> int:
        return self.model.preview_revision

    def build_ui(self):
        if self.root is not None:
            return self.root

        document = self.ui_document
        root = document.create_vstack("native-csg-cad-root")
        root.stable_id = "csg.cad.root"
        root.preferred_size = Size(1200.0, 760.0)
        root.set_layout_spacing(0.0)

        file_commands = CommandModel()
        file_commands.append(CommandData("new", "New", shortcut="Ctrl+N"))
        file_commands.append(CommandData("open", "Open...", shortcut="Ctrl+O"))
        file_commands.append(CommandData("separator", kind=CommandKind.Separator))
        file_commands.append(CommandData("save", "Save", shortcut="Ctrl+S"))
        file_commands.append(CommandData("save-as", "Save As...", shortcut="Ctrl+Shift+S"))
        menu_bar = document.create_menu_bar()
        menu_bar.entries = [MenuBarEntry("file", "File", file_commands)]
        menu_bar.connect_activated(self._menu_activated)
        root.add_fixed_child(menu_bar.widget, 30.0)

        self.viewport = document.create_viewport3d()
        self.viewport.widget.stable_id = "csg.cad.viewport"
        self.viewport.widget.preferred_size = Size(640.0, 600.0)
        self.viewport.set_surface_host(self.surface)

        panel = build_native_csg_editor_panel(
            document,
            self.model,
            separate=True,
            viewport=self._viewport_rect,
        )

        center = document.create_vstack("native-csg-cad-center")
        center.set_layout_spacing(4.0)
        controls = document.create_hstack("native-csg-cad-view-controls")
        controls.set_layout_spacing(6.0)
        fit = document.create_button("Fit", "native-csg-cad-fit")
        fit.connect_clicked(self.model.fit_camera)
        wireframe_label = document.create_label("Wireframe", "native-csg-cad-wireframe-label")
        wireframe = document.create_checkbox(self.model.show_wireframe)
        wireframe.widget.debug_name = "native-csg-cad-wireframe"
        wireframe.connect_changed(self.model.set_wireframe_visible)
        file_label = document.create_status_bar("File: <unsaved>")
        file_label.widget.debug_name = "native-csg-cad-file"
        controls.add_fixed_child(fit.widget, 72.0)
        controls.add_fixed_child(wireframe_label, 76.0)
        controls.add_fixed_child(wireframe.widget, 28.0)
        controls.add_stretch_child(file_label.widget)
        center.add_fixed_child(controls, 30.0)
        center.add_stretch_child(self.viewport.widget)

        right = document.create_scroll_area("native-csg-cad-inspector-scroll")
        right.set_scroll_axes(False, True)
        right.set_content(panel.inspector_root)

        center_right = document.create_splitter(True, "native-csg-cad-center-right")
        center_right.set_first(center)
        center_right.set_second(right.widget)
        center_right.set_split_fraction(0.70)
        center_right.set_min_extents(360.0, 300.0)
        body = document.create_splitter(True, "native-csg-cad-body")
        body.set_first(panel.tree_root)
        body.set_second(center_right.widget)
        body.set_split_fraction(0.22)
        body.set_min_extents(240.0, 640.0)
        root.add_stretch_child(body.widget)

        if not document.add_root(root.handle):
            panel.close()
            raise RuntimeError("failed to add native CSG CAD root")

        self.root = root
        self.editor_panel = panel
        self.menu_bar = menu_bar
        self.file_label = file_label
        self.wireframe_check = wireframe
        self.model.set_changed_handler(self._snapshot_changed)
        self.model.request_render()
        return root

    def dispatch_shortcut(self, event) -> bool:
        menu_bar = self.menu_bar
        return False if menu_bar is None else bool(menu_bar.dispatch_shortcut(event))

    def render_scene(self, renderer: CsgSceneRenderer) -> None:
        texture = renderer.render_document(
            self.controller.document,
            self.camera,
            self.surface.width,
            self.surface.height,
            self.controller.draft.points,
            self.controller.selection,
            self.model.show_wireframe,
            (self.model.preview_revision, self.model.show_wireframe),
        )
        self.surface.publish_texture(texture)
        self.model.dirty = False

    def request_render(self) -> None:
        self.model.request_render()

    def request_preview_rebuild(self) -> None:
        self.model.request_preview_rebuild()

    def _on_wireframe_changed(self, checked: bool) -> None:
        self.model.set_wireframe_visible(checked)

    def _on_scene_click(self, x: float, y: float, width: int, height: int) -> bool:
        return self.model.scene_click(x, y, width, height)

    def new_document(self) -> bool:
        return self.model.new_document()

    def open_state_dialog(self) -> None:
        self._show_file_dialog(FileDialogMode.OpenFile, "Open termin-csg CAD State", self._on_open_path)

    def save_state(self) -> bool:
        if self.model.current_path is None:
            self.save_state_as_dialog()
            return False
        return self.model.save_state()

    def save_state_as_dialog(self) -> None:
        self._show_file_dialog(
            FileDialogMode.SaveFile,
            "Save termin-csg CAD State",
            self._on_save_path,
            default_name=(self.model.current_path.name if self.model.current_path is not None else "model.tcsg.json"),
        )

    def save_state_to_path(self, path: str | Path) -> bool:
        return self.model.save_state(path)

    def load_state_from_path(self, path: str | Path) -> bool:
        return self.model.load_state(path)

    def start_draw_sketch(self) -> bool:
        return self.model.start_draw_sketch()

    def start_add_outer_contour(self) -> bool:
        return self.model.start_add_outer_contour()

    def start_add_hole_contour(self) -> bool:
        return self.model.start_add_hole_contour()

    def start_add_wall_path(self) -> bool:
        return self.model.start_add_wall_path()

    def close_contour(self) -> bool:
        return self.model.close_contour()

    def finish_wall_path(self) -> bool:
        return self.model.finish_wall_path()

    def extrude_selected(self) -> bool:
        return self.model.extrude_selected()

    def wall_selected(self) -> bool:
        return self.model.wall_selected()

    def add_boolean_operation(self, kind: str) -> bool:
        return self.model.add_boolean_operation(kind)

    def add_primitive(self, kind: str) -> bool:
        return self.model.add_primitive(kind)

    def fit_camera(self) -> None:
        self.model.fit_camera()

    def clear_document(self) -> bool:
        return self.model.clear_document()

    def refresh_tree(self) -> None:
        if self.editor_panel is not None:
            self.editor_panel.refresh()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.model.set_changed_handler(None)
        for dialog in tuple(self._dialogs.values()):
            if self.ui_document.is_alive(dialog.handle):
                self.ui_document.destroy_widget_recursive(dialog.handle)
        self._dialogs.clear()
        if self.viewport is not None:
            self.viewport.detach_surface()
        self.surface.close()
        if self.editor_panel is not None:
            self.editor_panel.close()
        if self.root is not None and self.root.alive:
            self.ui_document.destroy_widget_recursive(self.root.handle)
        self.root = None
        if self._owns_ui_document and self.ui_document.valid:
            tc_ui_document_destroy(self.ui_document)

    def _request_render(self) -> None:
        if not self._closed:
            self._external_request_render()

    def _menu_activated(self, _menu_index: int, _command_id: int, command) -> None:
        actions = {
            "new": self.new_document,
            "open": self.open_state_dialog,
            "save": self.save_state,
            "save-as": self.save_state_as_dialog,
        }
        action = actions.get(command.stable_id)
        if action is not None:
            action()

    def _snapshot_changed(self, _snapshot) -> None:
        if self.editor_panel is not None:
            self.editor_panel.apply_snapshot(_snapshot)
        if self.file_label is not None:
            self.file_label.text = (
                "File: <unsaved>" if self.model.current_path is None else f"File: {self.model.current_path.name}"
            )
        self._external_request_render()

    def _viewport_rect(self) -> Rect:
        if self.root is None:
            return Rect(0.0, 0.0, 1200.0, 760.0)
        bounds = self.root.bounds
        if bounds.width <= 0.0 or bounds.height <= 0.0:
            return Rect(0.0, 0.0, 1200.0, 760.0)
        return bounds

    def _show_file_dialog(
        self,
        mode: FileDialogMode,
        title: str,
        callback: Callable[[str | None], None],
        *,
        default_name: str = "",
    ) -> None:
        dialog = self.ui_document.create_file_dialog(mode)
        dialog.title = title
        dialog.set_initial_directory(str(self.model.file_dialog_directory()))
        dialog.set_filters(FileDialogModel.parse_filter_string(CAD_STATE_FILTER))
        if default_name:
            dialog.set_file_name(default_name)
        key = id(dialog)
        self._dialogs[key] = dialog

        def finished(path: str | None) -> None:
            retained = self._dialogs.pop(key, None)
            try:
                callback(path)
            finally:
                if retained is not None and self.ui_document.is_alive(retained.handle):
                    self.ui_document.destroy_widget_recursive(retained.handle)
                self.model.request_render()

        dialog.connect_path_finished(finished)
        if not dialog.show(self._viewport_rect()):
            self._dialogs.pop(key, None)
            self.ui_document.destroy_widget_recursive(dialog.handle)
            log.error(f"[CsgCad] failed to show native file dialog '{title}'")
            raise RuntimeError(f"failed to show native file dialog: {title}")
        self.model.request_render()

    def _on_open_path(self, path: str | None) -> None:
        if path is None:
            self.model.set_status("Open cancelled")
        else:
            self.model.load_state(path)

    def _on_save_path(self, path: str | None) -> None:
        if path is None:
            self.model.set_status("Save cancelled")
        else:
            self.model.save_state(path)


def run_cad_app(title: str = "termin-csg CAD", size: tuple[int, int] = (1200, 760)) -> None:
    from termin.csg.cad_runtime import run_cad_app as run_native_cad_app

    run_native_cad_app(title, size)


__all__ = ["CadApp", "run_cad_app"]
