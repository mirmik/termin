"""Standalone mini CAD application for procedural CSG documents."""

from __future__ import annotations

import ctypes

import sdl2

from tcbase import MouseButton, log
from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.panel import Panel
from tcgui.widgets.splitter import Splitter
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.ui import UI
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack
from termin.display import SDLBackendWindow
from tgfx import Tgfx2Context

from termin.csg.cad_viewer import CadViewportWidget, CsgSceneRenderer, document_bounds
from termin.csg.document_tree_model import DocumentTreeNode, build_document_tree, document_summary
from termin.csg.procedural_document import ProceduralMeshDocument, ProceduralPlane
from termin.csg.viewer_camera import OrbitCamera


_SDL_BUTTON_MAP = {1: MouseButton.LEFT, 2: MouseButton.MIDDLE, 3: MouseButton.RIGHT}


class CadApp:
    def __init__(self) -> None:
        self.document = ProceduralMeshDocument()
        self.camera = OrbitCamera()
        self.viewport = CadViewportWidget(self.camera)
        self.mode = "idle"
        self.draft_points: list[tuple[float, float, float]] = []
        self.draft_plane = ProceduralPlane()
        self.selected_node_data: tuple[str, str] | None = None

        self.mode_label = Label()
        self.summary_label = Label()
        self.selection_label = Label()
        self.tree = TreeWidget()
        self.dirty = True
        self.preview_revision = 0

    def build_ui(self):
        root = HStack()
        root.spacing = 0

        self.viewport.stretch = True
        self.viewport.on_changed = self.request_render
        self.viewport.on_scene_click = self._on_scene_click
        root.add_child(self.viewport)

        side = Panel()
        side.preferred_width = px(360)
        side.padding = 10
        side.background_color = (0.14, 0.145, 0.16, 1.0)
        side.add_child(self._build_side_panel())

        root.add_child(Splitter(side, "left"))
        root.add_child(side)
        self.refresh_tree()
        return root

    def render_scene(self, renderer: CsgSceneRenderer) -> None:
        width = max(int(self.viewport.width), 1)
        height = max(int(self.viewport.height), 1)
        texture = renderer.render_document(
            self.document,
            self.camera,
            width,
            height,
            self.draft_points,
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

    def start_draw_sketch(self) -> None:
        self.mode = "draw_sketch"
        self.draft_points = []
        self.draft_plane = ProceduralPlane()
        self._refresh_labels()
        self.request_preview_rebuild()
        log.info("[CsgCad] mode=draw_sketch")

    def close_contour(self) -> None:
        if len(self.draft_points) < 3:
            log.error(f"[CsgCad] cannot close contour: need 3 points, got {len(self.draft_points)}")
            return
        contour = self.document.add_contour_on_plane_from_points(self.draft_points[:], self.draft_plane)
        if contour is None:
            return
        if self.document.items:
            self.selected_node_data = ("sketch", self.document.items[0].id)
        self.draft_points = []
        self.refresh_tree()
        self.request_preview_rebuild()
        log.info(f"[CsgCad] contour closed id='{contour.id}'")

    def extrude_selected(self) -> None:
        sketch_id = self._selected_sketch_id()
        if not sketch_id:
            log.error("[CsgCad] cannot extrude: select a sketch")
            return
        operation = self.document.add_extrude_operation_for_sketch(sketch_id, 1.0)
        if operation is None:
            return
        self.selected_node_data = ("operation", operation.id)
        self.refresh_tree()
        self.fit_camera()
        self.request_preview_rebuild()
        log.info(f"[CsgCad] extrude added id='{operation.id}' sketch='{sketch_id}'")

    def fit_camera(self) -> None:
        lo, hi = document_bounds(self.document)
        self.camera.fit_bounds(lo, hi)
        self.request_render()

    def clear_document(self) -> None:
        self.document = ProceduralMeshDocument()
        self.draft_points = []
        self.selected_node_data = None
        self.refresh_tree()
        self.fit_camera()
        self.request_preview_rebuild()
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
        point = self.camera.world_point_on_z_plane(x, y, width, height, 0.0)
        if point is None:
            log.error("[CsgCad] draw sketch click ignored: ray does not hit OXY plane")
            return True
        self.draft_points.append(point)
        self._refresh_labels()
        self.request_preview_rebuild()
        log.info(
            "[CsgCad] draft point added "
            f"point=({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f}) "
            f"count={len(self.draft_points)}"
        )
        return True

    def _selected_sketch_id(self) -> str:
        data = self.selected_node_data
        if data is None:
            if self.document.items:
                return self.document.items[0].id
            return ""
        if data[0] == "sketch":
            return data[1]
        if data[0] == "operation":
            for operation in self.document.operations:
                if operation.id == data[1]:
                    return str(operation.params.get("source_sketch_id", ""))
        return ""

    def _refresh_labels(self) -> None:
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
        return f"Mode: {self.mode}; draft points: {len(self.draft_points)}"


def run_cad_app(title: str = "termin-csg CAD", size: tuple[int, int] = (1200, 760)) -> None:
    window = SDLBackendWindow(title, int(size[0]), int(size[1]))
    graphics = Tgfx2Context.from_window(window.device_ptr(), window.context_ptr())
    ui = UI(graphics=graphics)
    app = CadApp()
    ui.root = app.build_ui()
    scene_renderer = CsgSceneRenderer(graphics)

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
        if ev.key.keysym.scancode == sdl2.SDL_SCANCODE_ESCAPE:
            window.set_should_close(True)
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
        )
    elif event_type == sdl2.SDL_MOUSEBUTTONUP:
        ui.mouse_up(
            float(ev.button.x),
            float(ev.button.y),
            _SDL_BUTTON_MAP.get(ev.button.button, MouseButton.LEFT),
        )
    elif event_type == sdl2.SDL_MOUSEWHEEL:
        mx, my = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
        ui.mouse_wheel(float(ev.wheel.x), float(ev.wheel.y), float(mx.value), float(my.value))


__all__ = [
    "CadApp",
    "run_cad_app",
]
