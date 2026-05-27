"""Standalone mini CAD application for procedural CSG documents."""

from __future__ import annotations

import ctypes
from pathlib import Path

import sdl2

from tcbase import Key, Mods, MouseButton, log
from tcgui.widgets.button import Button
from tcgui.widgets.file_dialog_overlay import show_open_file_dialog, show_save_file_dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.panel import Panel
from tcgui.widgets.splitter import Splitter
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.ui import UI
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack
from termin.display import SDLBackendWindow
from tgfx import Tgfx2Context

from termin.csg.cad_viewer import CadViewportWidget, CsgSceneRenderer, document_bounds
from termin.csg.cad_state import CAD_STATE_FILTER, CadState, load_cad_state, save_cad_state
from termin.csg.document_edit import (
    SketchDraft,
    add_draft_point_from_ray,
    add_extrude_for_selection,
    clear_document,
    close_draft_contour,
    selected_sketch_id,
    start_sketch_draft,
)
from termin.csg.document_tree_model import DocumentTreeNode, build_document_tree, document_summary
from termin.csg.procedural_document import ProceduralMeshDocument, ProceduralPlane
from termin.csg.viewer_camera import OrbitCamera


_SDL_BUTTON_MAP = {1: MouseButton.LEFT, 2: MouseButton.MIDDLE, 3: MouseButton.RIGHT}
_KEY_MAP = {
    sdl2.SDL_SCANCODE_BACKSPACE: Key.BACKSPACE,
    sdl2.SDL_SCANCODE_DELETE: Key.DELETE,
    sdl2.SDL_SCANCODE_LEFT: Key.LEFT,
    sdl2.SDL_SCANCODE_RIGHT: Key.RIGHT,
    sdl2.SDL_SCANCODE_UP: Key.UP,
    sdl2.SDL_SCANCODE_DOWN: Key.DOWN,
    sdl2.SDL_SCANCODE_HOME: Key.HOME,
    sdl2.SDL_SCANCODE_END: Key.END,
    sdl2.SDL_SCANCODE_RETURN: Key.ENTER,
    sdl2.SDL_SCANCODE_ESCAPE: Key.ESCAPE,
    sdl2.SDL_SCANCODE_TAB: Key.TAB,
    sdl2.SDL_SCANCODE_SPACE: Key.SPACE,
}


class CadApp:
    def __init__(self) -> None:
        self.ui: UI | None = None
        self.document = ProceduralMeshDocument()
        self.camera = OrbitCamera()
        self.viewport = CadViewportWidget(self.camera)
        self.mode = "idle"
        self.draft: SketchDraft = start_sketch_draft()
        self.selected_node_data: tuple[str, str] | None = None
        self.current_path: Path | None = None
        self.last_directory = Path.cwd()

        self.mode_label = Label()
        self.file_label = Label()
        self.summary_label = Label()
        self.selection_label = Label()
        self.status_label = Label()
        self.tree = TreeWidget()
        self.dirty = True
        self.preview_revision = 0

    def build_ui(self, ui: UI):
        self.ui = ui

        root = VStack()
        root.spacing = 0

        menu_bar = self._build_menu_bar()
        root.add_child(menu_bar)

        content = HStack()
        content.spacing = 0
        content.stretch = True

        self.viewport.stretch = True
        self.viewport.on_changed = self.request_render
        self.viewport.on_scene_click = self._on_scene_click
        content.add_child(self.viewport)

        side = Panel()
        side.preferred_width = px(360)
        side.padding = 10
        side.background_color = (0.14, 0.145, 0.16, 1.0)
        side.add_child(self._build_side_panel())

        content.add_child(Splitter(side, "left"))
        content.add_child(side)
        root.add_child(content)

        menu_bar.register_shortcuts(ui)
        self.refresh_tree()
        return root

    def _build_menu_bar(self) -> MenuBar:
        menu_bar = MenuBar()

        file_menu = Menu()
        file_menu.items = [
            MenuItem("New", shortcut="Ctrl+N", on_click=self.new_document),
            MenuItem("Open...", shortcut="Ctrl+O", on_click=self.open_state_dialog),
            MenuItem.sep(),
            MenuItem("Save", shortcut="Ctrl+S", on_click=self.save_state),
            MenuItem("Save As...", shortcut="Ctrl+Shift+S", on_click=self.save_state_as_dialog),
        ]
        menu_bar.add_menu("File", file_menu)
        return menu_bar

    def render_scene(self, renderer: CsgSceneRenderer) -> None:
        width = max(int(self.viewport.width), 1)
        height = max(int(self.viewport.height), 1)
        texture = renderer.render_document(
            self.document,
            self.camera,
            width,
            height,
            self.draft.points,
            self.selected_node_data,
            self.preview_revision,
        )
        self.viewport.texture = texture
        self.viewport.texture_size = (width, height)
        self.dirty = False

    def request_render(self) -> None:
        self.dirty = True

    def request_preview_rebuild(self) -> None:
        self.preview_revision += 1
        self.request_render()

    def _build_side_panel(self):
        root = VStack()
        root.spacing = 6

        title = Label()
        title.text = "CSG CAD"
        root.add_child(title)

        self.file_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.file_label)

        self.mode_label.text = self._mode_text()
        self.mode_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.mode_label)

        row = HStack()
        row.spacing = 4
        row.preferred_height = px(28)
        row.add_child(self._button("Draw Sketch", self.start_draw_sketch))
        row.add_child(self._button("Close Contour", self.close_contour))
        root.add_child(row)

        row2 = HStack()
        row2.spacing = 4
        row2.preferred_height = px(28)
        row2.add_child(self._button("Extrude", self.extrude_selected))
        row2.add_child(self._button("Fit", self.fit_camera))
        row2.add_child(self._button("Clear", self.clear_document))
        root.add_child(row2)

        self.summary_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.summary_label)

        self.selection_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.selection_label)

        self.status_label.text = "Ready"
        self.status_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.status_label)

        self.tree.row_height = 22
        self.tree.indent_size = 22
        self.tree.stretch = True
        self.tree.on_select = self._on_tree_select
        root.add_child(self.tree)
        return root

    def _button(self, text: str, callback) -> Button:
        button = Button()
        button.text = text
        button.on_click = callback
        return button

    def new_document(self) -> None:
        self.document = clear_document()
        self.draft = start_sketch_draft()
        self.selected_node_data = None
        self.current_path = None
        self.mode = "idle"
        self.refresh_tree()
        self.fit_camera()
        self.request_preview_rebuild()
        self._set_status("New document")
        log.info("[CsgCad] new document")

    def open_state_dialog(self) -> None:
        ui = self.ui
        if ui is None:
            log.error("[CsgCad] cannot open file dialog: UI is not available")
            return
        show_open_file_dialog(
            ui,
            self._on_open_state_path,
            title="Open termin-csg CAD State",
            directory=str(self._file_dialog_directory()),
            filter_str=CAD_STATE_FILTER,
        )

    def save_state(self) -> None:
        if self.current_path is None:
            self.save_state_as_dialog()
            return
        self.save_state_to_path(self.current_path)

    def save_state_as_dialog(self) -> None:
        ui = self.ui
        if ui is None:
            log.error("[CsgCad] cannot open save dialog: UI is not available")
            return
        show_save_file_dialog(
            ui,
            self._on_save_state_path,
            title="Save termin-csg CAD State",
            directory=str(self._file_dialog_directory()),
            filter_str=CAD_STATE_FILTER,
        )

    def save_state_to_path(self, path: str | Path) -> bool:
        try:
            saved_path = save_cad_state(
                path,
                CadState.from_app_state(
                    self.document,
                    self.camera,
                    self.selected_node_data,
                ),
            )
        except Exception as e:
            self._set_status("Save failed")
            log.error(f"[CsgCad] failed to save state path='{path}': {e}")
            return False

        self.current_path = saved_path
        self.last_directory = saved_path.parent
        self._refresh_labels()
        self._set_status(f"Saved: {saved_path.name}")
        log.info(f"[CsgCad] state saved path='{saved_path}'")
        return True

    def load_state_from_path(self, path: str | Path) -> bool:
        try:
            state = load_cad_state(path)
        except Exception as e:
            self._set_status("Open failed")
            log.error(f"[CsgCad] failed to load state path='{path}': {e}")
            return False

        self.document = state.document
        state.camera.apply_to(self.camera)
        self.selected_node_data = self._validated_selection(state.selection)
        self.draft = start_sketch_draft()
        self.mode = "idle"
        self.current_path = Path(path).expanduser()
        self.last_directory = self.current_path.parent
        self.refresh_tree()
        self.request_preview_rebuild()
        self._set_status(f"Opened: {self.current_path.name}")
        log.info(f"[CsgCad] state loaded path='{self.current_path}'")
        return True

    def _on_open_state_path(self, path: str | None) -> None:
        if path is None:
            self._set_status("Open cancelled")
            return
        self.load_state_from_path(path)

    def _on_save_state_path(self, path: str | None) -> None:
        if path is None:
            self._set_status("Save cancelled")
            return
        self.save_state_to_path(path)

    def start_draw_sketch(self) -> None:
        self.mode = "draw_sketch"
        self.draft = start_sketch_draft()
        self._refresh_labels()
        self.request_preview_rebuild()
        log.info("[CsgCad] mode=draw_sketch")

    def close_contour(self) -> None:
        result = close_draft_contour(self.document, self.draft)
        if not result.success:
            return
        self.selected_node_data = result.selection
        self.refresh_tree()
        self.request_preview_rebuild()
        contour_id = ""
        if result.contour is not None:
            contour_id = result.contour.id
        log.info(f"[CsgCad] contour closed id='{contour_id}'")

    def extrude_selected(self) -> None:
        sketch_id = selected_sketch_id(self.document, self.selected_node_data)
        result = add_extrude_for_selection(self.document, self.selected_node_data, 1.0)
        if not result.success:
            return
        self.selected_node_data = result.selection
        self.refresh_tree()
        self.fit_camera()
        self.request_preview_rebuild()
        operation_id = ""
        if result.operation is not None:
            operation_id = result.operation.id
        log.info(f"[CsgCad] extrude added id='{operation_id}' sketch='{sketch_id}'")

    def fit_camera(self) -> None:
        lo, hi = document_bounds(self.document)
        self.camera.fit_bounds(lo, hi)
        self.request_render()

    def clear_document(self) -> None:
        self.document = clear_document()
        self.draft = start_sketch_draft()
        self.selected_node_data = None
        self.current_path = None
        self.mode = "idle"
        self.refresh_tree()
        self.fit_camera()
        self.request_preview_rebuild()
        self._set_status("Cleared")
        log.info("[CsgCad] document cleared")

    def refresh_tree(self) -> None:
        self.tree.clear()
        roots = build_document_tree(self.document)
        for root in roots:
            self.tree.add_root(self._to_tree_node(root))
        self._restore_tree_selection(self.tree.root_nodes)
        self._refresh_labels()
        if self.tree._ui is not None:
            self.tree._ui.request_layout()

    def _to_tree_node(self, source: DocumentTreeNode) -> TreeNode:
        label = Label()
        label.text = source.text
        label.color = (0.70, 0.74, 0.80, 1.0)
        node = TreeNode(label)
        node.data = (source.kind, source.item_id)
        node.expanded = True
        for child in source.children:
            node.add_node(self._to_tree_node(child))
        return node

    def _restore_tree_selection(self, roots: list[TreeNode]) -> None:
        for root in roots:
            selected = self._find_tree_node(root, self.selected_node_data)
            if selected is not None:
                self.tree.selected_node = selected
                selected._selected = True
                return

    def _find_tree_node(self, root: TreeNode, data: tuple[str, str] | None) -> TreeNode | None:
        if data is None:
            return None
        if root.data == data:
            return root
        for child in root.subnodes:
            found = self._find_tree_node(child, data)
            if found is not None:
                return found
        return None

    def _on_tree_select(self, node: TreeNode) -> None:
        self.selected_node_data = node.data
        self._refresh_labels()
        self.request_preview_rebuild()

    def _on_scene_click(self, x: float, y: float, width: int, height: int) -> bool:
        if self.mode != "draw_sketch":
            return False
        ray_origin, ray_direction = self.camera.screen_ray(x, y, width, height)
        fallback_point = self.camera.world_point_on_z_plane(x, y, width, height, 0.0)
        result = add_draft_point_from_ray(
            self.document,
            self.draft,
            ray_origin,
            ray_direction,
            fallback_point=fallback_point,
            fallback_plane=ProceduralPlane(),
            fallback_kind="oxy",
        )
        if not result.success or result.point is None:
            return True
        self._refresh_labels()
        self.request_preview_rebuild()
        point = result.point
        log.info(
            "[CsgCad] draft point added "
            f"kind={result.kind} "
            f"point=({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f}) "
            f"count={len(self.draft.points)}"
        )
        return True

    def _refresh_labels(self) -> None:
        if self.current_path is None:
            self.file_label.text = "File: <unsaved>"
        else:
            self.file_label.text = f"File: {self.current_path.name}"
        self.mode_label.text = self._mode_text()
        self.summary_label.text = document_summary(self.document)
        if self.selected_node_data is None:
            self.selection_label.text = "Selection: <none>"
        else:
            self.selection_label.text = (
                f"Selection: {self.selected_node_data[0]} "
                f"{self.selected_node_data[1][:10]}"
            )

    def _mode_text(self) -> str:
        return f"Mode: {self.mode}; draft points: {len(self.draft.points)}"

    def _set_status(self, text: str) -> None:
        self.status_label.text = f"Status: {text}"

    def _file_dialog_directory(self) -> Path:
        if self.current_path is not None:
            return self.current_path.parent
        return self.last_directory

    def _validated_selection(self, selection: tuple[str, str] | None) -> tuple[str, str] | None:
        if selection is None:
            return None
        kind, item_id = selection
        if kind == "sketch" and self.document.find_sketch(item_id) is not None:
            return selection
        if kind == "operation" and self.document.find_operation(item_id) is not None:
            return selection
        if kind == "contour":
            for item in self.document.items:
                for contour in item.contours:
                    if contour.id == item_id:
                        return selection
        log.error(f"[CsgCad] saved selection is missing kind='{kind}' id='{item_id}'")
        return None


def run_cad_app(title: str = "termin-csg CAD", size: tuple[int, int] = (1200, 760)) -> None:
    window = SDLBackendWindow(title, int(size[0]), int(size[1]))
    graphics = Tgfx2Context.from_window(window.device_ptr(), window.context_ptr())
    ui = UI(graphics=graphics)
    app = CadApp()
    ui.root = app.build_ui(ui)
    scene_renderer = CsgSceneRenderer(graphics)

    sdl2.SDL_StartTextInput()
    event = sdl2.SDL_Event()
    try:
        while not window.should_close():
            if sdl2.SDL_WaitEventTimeout(ctypes.byref(event), 16):
                _dispatch_event(window, ui, event)
                while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
                    _dispatch_event(window, ui, event)

            width, height = window.framebuffer_size()
            if width <= 0 or height <= 0:
                continue
            if app.dirty:
                app.render_scene(scene_renderer)
            texture = ui.render_compose(width, height, background_color=(0.10, 0.10, 0.12, 1.0))
            ui.process_deferred()
            if texture is not None:
                window.present(texture)
    finally:
        scene_renderer.close()
        window.close()
        sdl2.SDL_Quit()


def _dispatch_event(window, ui: UI, ev) -> None:
    event_type = ev.type
    if event_type == sdl2.SDL_QUIT:
        window.set_should_close(True)
    elif event_type == sdl2.SDL_KEYDOWN:
        key = _translate_key(ev.key.keysym.scancode)
        mods = _translate_mods(sdl2.SDL_GetModState())
        if ui.key_down(key, mods):
            return
        if key == Key.ESCAPE:
            window.set_should_close(True)
    elif event_type == sdl2.SDL_TEXTINPUT:
        ui.text_input(ev.text.text.decode("utf-8"))
    elif event_type == sdl2.SDL_WINDOWEVENT:
        if ev.window.event == sdl2.SDL_WINDOWEVENT_CLOSE:
            window.set_should_close(True)
    elif event_type == sdl2.SDL_MOUSEMOTION:
        ui.mouse_move(float(ev.motion.x), float(ev.motion.y))
    elif event_type == sdl2.SDL_MOUSEBUTTONDOWN:
        ui.mouse_down(
            float(ev.button.x),
            float(ev.button.y),
            _SDL_BUTTON_MAP.get(ev.button.button, MouseButton.LEFT),
            _translate_mods(sdl2.SDL_GetModState()),
        )
    elif event_type == sdl2.SDL_MOUSEBUTTONUP:
        ui.mouse_up(
            float(ev.button.x),
            float(ev.button.y),
            _SDL_BUTTON_MAP.get(ev.button.button, MouseButton.LEFT),
            _translate_mods(sdl2.SDL_GetModState()),
        )
    elif event_type == sdl2.SDL_MOUSEWHEEL:
        mx, my = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
        ui.mouse_wheel(
            float(ev.wheel.x),
            float(ev.wheel.y),
            float(mx.value),
            float(my.value),
            _translate_mods(sdl2.SDL_GetModState()),
        )


def _translate_key(scancode: int) -> Key:
    if scancode in _KEY_MAP:
        return _KEY_MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if ord("a") <= keycode <= ord("z"):
        keycode -= 32
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            return Key.UNKNOWN
    return Key.UNKNOWN


def _translate_mods(sdl_mods: int) -> int:
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= Mods.SHIFT.value
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= Mods.CTRL.value
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= Mods.ALT.value
    return result


__all__ = [
    "CadApp",
    "run_cad_app",
]
