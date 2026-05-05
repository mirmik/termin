"""EditorWindow — main orchestrator for the diffusion editor (tcgui version)."""

from __future__ import annotations

from dataclasses import dataclass
import os
import random

import numpy as np
from PIL import Image
from tcbase import log

from tcgui.widgets.ui import UI
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.panel import Panel
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.menu import MenuItem, Menu
from tcgui.widgets.tool_bar import ToolBar
from tcgui.widgets.status_bar import StatusBar
from tcgui.widgets.message_box import MessageBox, Buttons
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.units import px, pct
from tcgui.widgets.splitter import Splitter

from .agent_chat import DEFAULT_AGENT_BASE_URL, DEFAULT_AGENT_MODEL, AgentChatPanel
from .agent_tools import create_editor_tool_registry
from .grounding_dialog import GroundingDialog
from .layer_stack import LayerStack
from .mask import coerce_mask_data
from .layer import Layer
from .tool import DiffusionTool, LamaTool, InstructTool
from .brush import BrushToolMode
from .editor_canvas import EditorCanvas
from .layer_panel import LayerPanel
from .brush_panel import BrushPanel
from .diffusion_panel import DiffusionPanel
from .lama_panel import LamaPanel
from .instruct_panel import InstructPanel
from .selection_panel import SelectionPanel
from .diffusion_engine import DiffusionEngine
from .lama_engine import LamaEngine
from .instruct_engine import InstructEngine
from .segmentation import SegmentationEngine
from .diffusion_brush import extract_patch, extract_mask_patch
from .file_dialog import open_file_dialog, save_file_dialog, open_directory_dialog
from .settings import Settings
from .history import HistoryManager
from .document_service import DocumentService
from .commands import (
    AddLayerCommand, RemoveLayerCommand,
    MoveLayerCommand, SetLayerVisibilityCommand, SetLayerOpacityCommand,
    FlattenLayersCommand, ClearLayerMaskCommand,
    AttachLayerToolCommand, DetachLayerToolCommand,
    SetIpAdapterRectCommand, ClearIpAdapterRectCommand,
    SetManualPatchRectCommand, ClearManualPatchRectCommand,
    ClearSelectionCommand, InvertSelectionCommand, SelectAllCommand,
    SetLayerSelectionCommand,
)
from .engine_result_mapper import (
    map_segmentation_result, map_lama_result,
    map_instruct_result, map_diffusion_result,
)

_BYTES_PER_GIB = 1024 * 1024 * 1024
_DEFAULT_HISTORY_MEMORY_LIMIT_BYTES = 5 * _BYTES_PER_GIB
_MIN_HISTORY_MEMORY_LIMIT_GIB = 0.25
_MAX_HISTORY_MEMORY_LIMIT_GIB = 256.0


@dataclass
class ExternalEditContext:
    label: str
    layer_path: str
    target: str
    before_arr: np.ndarray


class EditorWindow:
    """Non-widget orchestrator: assembles UI, wires callbacks, handles logic."""

    def __init__(self, ctx=None):
        # Optional borrowed tgfx2 context. When given (typically by
        # main.py, which owns a BackendWindow and wants every renderer
        # to share one IRenderDevice), the UI draws through it; when
        # None, UIRenderer falls back to its own owning Tgfx2Context.
        # Required to be non-None under TERMIN_BACKEND=vulkan because
        # cross-widget TextureHandle sharing and swapchain presentation
        # both assume a single process-global device.
        self._ctx = ctx
        self._running = True
        self._closed = False
        self._settings = Settings()
        self._project_path: str | None = None
        self._last_dir: str = self._settings.get("last_dir", "")
        self._history_memory_limit_bytes = self._load_history_memory_limit_bytes()
        self._models_dir = self._load_models_dir()
        self._pending_request = None
        self._pending_lama_layer = None
        self._pending_instruct_layer = None
        self._pending_grounding_result = None
        self._history_replaying = False
        self._external_edit_ctx: ExternalEditContext | None = None

        # Layer stack
        self._layer_stack = LayerStack()

        # Engines
        self._engine = DiffusionEngine()
        self._seg_engine = SegmentationEngine()
        self._lama_engine = LamaEngine()
        self._instruct_engine = InstructEngine()
        self._history = HistoryManager(
            self._apply_snapshot,
            max_memory_bytes=self._history_memory_limit_bytes,
        )
        self._document = DocumentService(
            self._layer_stack,
            self._history,
            self._apply_snapshot,
        )

        # Agent tool registry (created once, reused across chat clear/reset)
        self._agent_tool_registry = create_editor_tool_registry()

        # Build UI
        self._build_ui()

        # Wire callbacks
        self._wire_callbacks()
        self._menu_bar.register_shortcuts(self.ui)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = VStack()
        root.preferred_width = pct(100)
        root.preferred_height = pct(100)
        root.spacing = 0

        # Menu bar
        self._menu_bar = MenuBar()
        self._setup_menu()
        root.add_child(self._menu_bar)

        # Toolbar
        self._toolbar = ToolBar()
        self._toolbar.add_action(text="Open", on_click=self.open_file)
        self._toolbar.add_action(text="Save", on_click=self.save_file)
        self._toolbar.add_separator()
        self._toolbar.add_action(text="Fit", on_click=self._fit)
        self._toolbar.add_separator()
        self._toolbar.add_action(text="Sel All", on_click=self._select_all)
        self._toolbar.add_action(text="Sel Clear", on_click=self._clear_selection)
        self._toolbar.add_action(text="Sel Inv", on_click=self._invert_selection)
        root.add_child(self._toolbar)

        # Main content area: left panel | canvas | right panel
        main_area = HStack()
        main_area.stretch = True
        main_area.spacing = 0

        # Left panel container
        self._left_container = VStack()
        self._left_container.preferred_width = px(260)
        self._left_container.clip = True

        # Brush is always available; the selected layer's attached tool panel
        # appears below it when a tool is present.
        self._brush_panel = BrushPanel(self._canvas_placeholder_brush())
        self._diffusion_panel = DiffusionPanel()
        self._diffusion_panel.set_models_dir(self._models_dir)
        self._lama_panel = LamaPanel()
        self._instruct_panel = InstructPanel()
        self._selection_panel = SelectionPanel()
        self._selection_panel.visible = True

        self._left_container.spacing = 6
        self._brush_panel.visible = True
        self._left_container.add_child(self._brush_panel)
        self._left_container.add_child(self._selection_panel)
        for p in (self._diffusion_panel, self._lama_panel, self._instruct_panel):
            p.visible = False
            p.stretch = True
            self._left_container.add_child(p)

        main_area.add_child(self._left_container)
        main_area.add_child(Splitter(target=self._left_container, side="right"))

        # Canvas (center, stretches to fill remaining space)
        self._canvas = EditorCanvas(self._layer_stack, ctx=self._ctx)
        self._canvas.stretch = True
        # Give brush reference now
        self._brush_panel._brush = self._canvas.brush
        main_area.add_child(self._canvas)

        # Right panels: layer panel | agent chat
        self._layer_panel = LayerPanel(self._layer_stack)
        main_area.add_child(Splitter(target=self._layer_panel, side="left"))
        main_area.add_child(self._layer_panel)

        self._agent_chat_panel = AgentChatPanel(
            self._settings,
            tool_registry=self._agent_tool_registry,
            layer_stack=self._layer_stack,
            document_service=self._document,
        )
        self._agent_chat_panel.preferred_width = px(320)
        self._agent_chat_panel.preferred_height = pct(100)
        main_area.add_child(Splitter(target=self._agent_chat_panel, side="left"))
        main_area.add_child(self._agent_chat_panel)

        root.add_child(main_area)

        # Status bar
        self._statusbar = StatusBar()
        self._statusbar.text = "Ready"
        root.add_child(self._statusbar)

        self.ui = UI(graphics=self._ctx)
        self.ui.root = root

    def _canvas_placeholder_brush(self):
        """Temporary brush for panel construction (replaced after canvas created)."""
        from .brush import Brush
        return Brush()

    def _setup_menu(self):
        # File menu
        file_menu = Menu()
        file_menu.add_item(MenuItem("New...", shortcut="Ctrl+N", on_click=self.new_project))
        file_menu.add_item(MenuItem("New From Image...", on_click=self.new_project_from_image))
        file_menu.add_item(MenuItem(separator=True))
        file_menu.add_item(MenuItem("Open...", shortcut="Ctrl+O", on_click=self.open_file))
        file_menu.add_item(MenuItem("Save", shortcut="Ctrl+S", on_click=self.save_file))
        file_menu.add_item(MenuItem("Save As...", shortcut="Ctrl+Shift+S", on_click=self.save_file_as))
        file_menu.add_item(MenuItem(separator=True))
        file_menu.add_item(MenuItem("Import Image...", shortcut="Ctrl+I", on_click=self.import_image))
        file_menu.add_item(MenuItem("Export Image...", shortcut="Ctrl+E", on_click=self.export_image))
        file_menu.add_item(MenuItem(separator=True))
        file_menu.add_item(MenuItem("Quit", shortcut="Ctrl+Q", on_click=self._quit))
        self._menu_bar.add_menu("File", file_menu)

        # Edit menu
        edit_menu = Menu()
        edit_menu.add_item(MenuItem("Undo", shortcut="Ctrl+Z", on_click=self.undo))
        edit_menu.add_item(MenuItem("Redo", shortcut="Ctrl+Shift+Z", on_click=self.redo))
        edit_menu.add_item(MenuItem("Redo", shortcut="Ctrl+Y", on_click=self.redo))
        edit_menu.add_item(MenuItem(separator=True))
        edit_menu.add_item(MenuItem("Settings...", on_click=self._show_settings_dialog))
        self._menu_bar.add_menu("Edit", edit_menu)

        # Select menu
        select_menu = Menu()
        select_menu.add_item(MenuItem("Select All", shortcut="Ctrl+A", on_click=self._select_all))
        select_menu.add_item(MenuItem("Clear Selection", shortcut="Ctrl+D", on_click=self._clear_selection))
        select_menu.add_item(MenuItem(separator=True))
        select_menu.add_item(MenuItem("Invert Selection", shortcut="Ctrl+Shift+I", on_click=self._invert_selection))
        self._menu_bar.add_menu("Select", select_menu)

        # Layer menu
        layer_menu = Menu()
        layer_menu.add_item(MenuItem("New Layer", shortcut="Ctrl+Shift+N", on_click=self._new_layer))
        layer_menu.add_item(MenuItem("Remove Layer", on_click=self._remove_layer))
        layer_menu.add_item(MenuItem(separator=True))
        layer_menu.add_item(MenuItem("Flatten", on_click=self._flatten_layers))
        layer_menu.add_item(MenuItem(separator=True))
        layer_menu.add_item(MenuItem("Detect Objects...", on_click=self._show_grounding_dialog))
        self._menu_bar.add_menu("Layer", layer_menu)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _wire_callbacks(self):
        # Layer stack
        old_on_changed = self._layer_stack.on_changed

        def _on_stack_changed():
            if old_on_changed:
                old_on_changed()
            self._on_layer_changed()
            self._layer_panel.sync_from_stack()
        self._layer_stack.on_changed = _on_stack_changed

        # Canvas
        self._canvas.on_mouse_moved = self._on_mouse_moved
        self._canvas.on_color_picked = self._on_color_picked
        self._canvas.on_edit_begin = self._begin_external_edit
        self._canvas.on_edit_end = self._end_external_edit

        # Brush panel
        self._brush_panel.on_tool_changed = self._set_canvas_tool
        self._brush_panel.on_eraser_toggled = self._canvas.set_brush_eraser

        # Selection panel
        self._selection_panel.on_edit_mode_toggled = self._canvas.set_selection_mode
        self._selection_panel.on_rect_mode_toggled = self._canvas.set_selection_rect_mode
        self._selection_panel.on_brush_changed = self._canvas.set_selection_brush
        self._selection_panel.on_eraser_toggled = self._canvas.set_selection_eraser
        self._selection_panel.on_show_selection_toggled = self._canvas.set_show_selection

        # Diffusion panel
        self._diffusion_panel.on_load_model = self._on_load_model
        self._diffusion_panel.on_regenerate = self._on_regenerate
        self._diffusion_panel.on_new_seed = self._on_new_seed
        self._diffusion_panel.on_clear_mask = self._on_clear_mask
        self._diffusion_panel.on_mask_brush_changed = self._set_mask_brush
        self._diffusion_panel.on_mask_eraser_toggled = self._set_mask_eraser
        self._diffusion_panel.on_show_mask_toggled = self._canvas.set_show_mask
        self._diffusion_panel.on_load_ip_adapter = self._on_load_ip_adapter
        self._diffusion_panel.on_draw_rect_toggled = self._canvas.set_ref_rect_mode
        self._diffusion_panel.on_show_rect_toggled = self._canvas.set_show_ref_rect
        self._diffusion_panel.on_clear_rect = self._on_clear_ref_rect
        self._diffusion_panel.on_select_background = self._on_select_background
        self._diffusion_panel.on_draw_patch_toggled = self._canvas.set_patch_rect_mode
        self._diffusion_panel.on_show_patch_toggled = self._canvas.set_show_patch_rect
        self._diffusion_panel.on_clear_patch = self._on_clear_patch_rect
        self._canvas.on_ref_rect_drawn = self._on_ref_rect_drawn
        self._canvas.on_patch_rect_drawn = self._on_patch_rect_drawn
        self._canvas.on_selection_rect_drawn = self._on_selection_rect_drawn

        # Layer panel
        self._layer_panel.on_attach_tool = self._attach_tool_to_layer
        self._layer_panel.on_detach_tool = self._detach_tool_from_layer
        self._layer_panel.on_add_layer = self._new_layer
        self._layer_panel.on_remove_layer = self._remove_layer
        self._layer_panel.on_flatten_layers = self._flatten_layers
        self._layer_panel.on_move_layer = self._move_layer
        self._layer_panel.on_toggle_visibility = self._set_layer_visibility
        self._layer_panel.on_opacity_changed = self._set_layer_opacity

        # LaMa panel
        self._lama_panel.on_remove = self._on_lama_remove
        self._lama_panel.on_clear_mask = self._on_lama_clear_mask
        self._lama_panel.on_mask_brush_changed = self._set_mask_brush
        self._lama_panel.on_mask_eraser_toggled = self._set_mask_eraser
        self._lama_panel.on_show_mask_toggled = self._canvas.set_show_mask
        self._lama_panel.on_select_background = self._on_lama_select_background

        # Instruct panel
        self._instruct_panel.on_load_model = self._on_instruct_load_model
        self._instruct_panel.on_apply = self._on_instruct_apply
        self._instruct_panel.on_new_seed = self._on_instruct_new_seed
        self._instruct_panel.on_clear_mask = self._on_instruct_clear_mask
        self._instruct_panel.on_mask_brush_changed = self._set_mask_brush
        self._instruct_panel.on_mask_eraser_toggled = self._set_mask_eraser
        self._instruct_panel.on_show_mask_toggled = self._canvas.set_show_mask
        self._instruct_panel.on_draw_patch_toggled = self._canvas.set_patch_rect_mode
        self._instruct_panel.on_show_patch_toggled = self._canvas.set_show_patch_rect
        self._instruct_panel.on_clear_patch = self._on_instruct_clear_patch_rect

    def _set_canvas_tool(self, mode: BrushToolMode | str):
        self._canvas.set_brush_tool(mode)
        self._brush_panel.set_tool_mode(self._canvas.brush_tool_mode)

    def _set_mask_brush(self, size: int, hardness: float, flow: float = 1.0):
        self._canvas.set_mask_brush(size, hardness, flow)
        self._brush_panel.set_tool_mode(self._canvas.brush_tool_mode)

    def _set_mask_eraser(self, eraser: bool):
        self._canvas.set_mask_eraser(eraser)
        self._brush_panel.set_tool_mode(self._canvas.brush_tool_mode)

    # ------------------------------------------------------------------
    # Panel switching
    # ------------------------------------------------------------------

    def _on_layer_changed(self):
        layer = self._layer_stack.active_layer
        self._brush_panel.visible = True
        self._diffusion_panel.visible = False
        self._lama_panel.visible = False
        self._instruct_panel.visible = False

        if layer is None:
            pass
        elif isinstance(layer.tool, DiffusionTool):
            self._diffusion_panel.show_diffusion_layer(layer)
            self._diffusion_panel.visible = True
        elif isinstance(layer.tool, LamaTool):
            self._lama_panel.show_lama_layer(layer)
            self._lama_panel.visible = True
        elif isinstance(layer.tool, InstructTool):
            self._instruct_panel.show_instruct_layer(layer)
            self._instruct_panel.visible = True
        self.ui.request_layout()

        # Debug: print visible panel coords after next layout
        for name, p in [("brush", self._brush_panel), ("diffusion", self._diffusion_panel),
                         ("lama", self._lama_panel), ("instruct", self._instruct_panel)]:
            if p.visible:
                log.debug(
                    f"[panel] {name}: x={p.x:.0f} y={p.y:.0f} w={p.width:.0f} h={p.height:.0f}"
                )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_bytes(n: int) -> str:
        if n < 1024:
            return f"{n}B"
        if n < 1024 * 1024:
            return f"{n / 1024:.0f}K"
        return f"{n / (1024 * 1024):.1f}M"

    def _load_history_memory_limit_bytes(self) -> int:
        raw = self._settings.get("history_memory_limit_bytes", _DEFAULT_HISTORY_MEMORY_LIMIT_BYTES)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return _DEFAULT_HISTORY_MEMORY_LIMIT_BYTES
        if value <= 0:
            return _DEFAULT_HISTORY_MEMORY_LIMIT_BYTES
        return value

    def _set_history_memory_limit_bytes(self, limit_bytes: int) -> None:
        limit_bytes = max(int(limit_bytes), int(_MIN_HISTORY_MEMORY_LIMIT_GIB * _BYTES_PER_GIB))
        self._history_memory_limit_bytes = limit_bytes
        self._document.set_history_memory_limit_bytes(limit_bytes)
        self._settings.set("history_memory_limit_bytes", limit_bytes)

    def _load_models_dir(self) -> str:
        raw = self._settings.get("models_dir", DiffusionPanel.default_models_dir())
        if not isinstance(raw, str):
            return DiffusionPanel.default_models_dir()
        value = os.path.expanduser(raw.strip())
        if not value:
            return DiffusionPanel.default_models_dir()
        return value

    def _set_models_dir(self, models_dir: str) -> None:
        value = os.path.expanduser(models_dir.strip())
        if not value:
            value = DiffusionPanel.default_models_dir()
        self._models_dir = value
        self._diffusion_panel.set_models_dir(value)
        self._settings.set("models_dir", value)

    def _show_settings_dialog(self):
        if self.ui is None:
            return

        dlg = Dialog()
        dlg.title = "Settings"
        dlg.buttons = ["OK", "Cancel"]
        dlg.default_button = "OK"
        dlg.cancel_button = "Cancel"

        content = VStack()
        content.spacing = 8

        models_title = Label()
        models_title.text = "Stable Diffusion models directory"
        content.add_child(models_title)

        models_row = HStack()
        models_row.spacing = 6

        models_dir_input = TextInput()
        models_dir_input.text = self._models_dir
        models_dir_input.preferred_width = px(420)
        models_row.add_child(models_dir_input)

        browse_btn = Button()
        browse_btn.text = "Browse..."
        browse_btn.preferred_width = px(90)

        def _browse_models_dir():
            def _on_result(selected):
                if selected:
                    models_dir_input.text = selected
                    self._last_dir = selected
                    self._settings.set("last_dir", self._last_dir)
            open_directory_dialog(
                self.ui, _on_result,
                title="Select models directory",
                directory=models_dir_input.text or self._last_dir,
            )

        browse_btn.on_click = _browse_models_dir
        models_row.add_child(browse_btn)
        content.add_child(models_row)

        title = Label()
        title.text = "Undo/Redo memory limit (GiB)"
        content.add_child(title)

        limit_input = SpinBox()
        limit_input.decimals = 2
        limit_input.step = 0.25
        limit_input.min_value = _MIN_HISTORY_MEMORY_LIMIT_GIB
        limit_input.max_value = _MAX_HISTORY_MEMORY_LIMIT_GIB
        limit_input.value = self._history_memory_limit_bytes / _BYTES_PER_GIB
        limit_input.preferred_width = px(220)
        content.add_child(limit_input)

        note = Label()
        note.text = "Older history entries are removed when the limit is exceeded."
        content.add_child(note)

        agent_title = Label()
        agent_title.text = "Agent Chat API"
        content.add_child(agent_title)

        agent_base_url_label = Label()
        agent_base_url_label.text = "Base URL"
        agent_base_url_label.font_size = 12
        content.add_child(agent_base_url_label)

        agent_base_url_input = TextInput()
        agent_base_url_input.text = str(
            self._settings.get("agent_api_base_url", DEFAULT_AGENT_BASE_URL)
        )
        agent_base_url_input.placeholder = DEFAULT_AGENT_BASE_URL
        agent_base_url_input.preferred_width = px(420)
        content.add_child(agent_base_url_input)

        agent_key_label = Label()
        agent_key_label.text = "API key"
        agent_key_label.font_size = 12
        content.add_child(agent_key_label)

        agent_key_input = TextInput()
        agent_key_input.text = str(self._settings.get("agent_api_key", ""))
        agent_key_input.placeholder = "API key"
        agent_key_input.preferred_width = px(420)
        content.add_child(agent_key_input)

        agent_model_label = Label()
        agent_model_label.text = "Model"
        agent_model_label.font_size = 12
        content.add_child(agent_model_label)

        agent_model_input = TextInput()
        agent_model_input.text = str(self._settings.get("agent_model", DEFAULT_AGENT_MODEL))
        agent_model_input.placeholder = DEFAULT_AGENT_MODEL
        agent_model_input.preferred_width = px(260)
        content.add_child(agent_model_input)

        agent_params_row = HStack()
        agent_params_row.spacing = 8

        temperature_box = VStack()
        temperature_box.spacing = 3
        temperature_label = Label()
        temperature_label.text = "Temperature"
        temperature_label.font_size = 12
        temperature_box.add_child(temperature_label)

        agent_temperature_input = SpinBox()
        agent_temperature_input.decimals = 2
        agent_temperature_input.step = 0.05
        agent_temperature_input.min_value = 0.0
        agent_temperature_input.max_value = 2.0
        agent_temperature_input.value = float(self._settings.get("agent_temperature", 0.7))
        agent_temperature_input.preferred_width = px(120)
        temperature_box.add_child(agent_temperature_input)
        agent_params_row.add_child(temperature_box)

        max_tokens_box = VStack()
        max_tokens_box.spacing = 3
        max_tokens_label = Label()
        max_tokens_label.text = "Max tokens"
        max_tokens_label.font_size = 12
        max_tokens_box.add_child(max_tokens_label)

        agent_max_tokens_input = SpinBox()
        agent_max_tokens_input.decimals = 0
        agent_max_tokens_input.step = 128
        agent_max_tokens_input.min_value = 0
        agent_max_tokens_input.max_value = 131072
        agent_max_tokens_input.value = float(self._settings.get("agent_max_tokens", 1024))
        agent_max_tokens_input.preferred_width = px(140)
        max_tokens_box.add_child(agent_max_tokens_input)
        agent_params_row.add_child(max_tokens_box)

        timeout_box = VStack()
        timeout_box.spacing = 3
        timeout_label = Label()
        timeout_label.text = "Timeout sec"
        timeout_label.font_size = 12
        timeout_box.add_child(timeout_label)

        agent_timeout_input = SpinBox()
        agent_timeout_input.decimals = 0
        agent_timeout_input.step = 5
        agent_timeout_input.min_value = 5
        agent_timeout_input.max_value = 600
        agent_timeout_input.value = float(self._settings.get("agent_timeout_seconds", 60))
        agent_timeout_input.preferred_width = px(120)
        timeout_box.add_child(agent_timeout_input)
        agent_params_row.add_child(timeout_box)

        content.add_child(agent_params_row)

        agent_stream_input = Checkbox()
        agent_stream_input.text = "Stream responses"
        agent_stream_input.checked = bool(self._settings.get("agent_stream", True))
        content.add_child(agent_stream_input)

        dlg.content = content

        def _apply(result: str):
            if result != "OK":
                return
            self._set_models_dir(models_dir_input.text)
            limit_bytes = int(limit_input.value * _BYTES_PER_GIB)
            self._set_history_memory_limit_bytes(limit_bytes)
            self._settings.set("agent_api_base_url", agent_base_url_input.text.strip())
            self._settings.set("agent_api_key", agent_key_input.text.strip())
            self._settings.set("agent_model", agent_model_input.text.strip())
            self._settings.set("agent_temperature", float(agent_temperature_input.value))
            self._settings.set("agent_max_tokens", int(agent_max_tokens_input.value))
            self._settings.set("agent_timeout_seconds", float(agent_timeout_input.value))
            self._settings.set("agent_stream", bool(agent_stream_input.checked))
            self._statusbar.text = (
                f"Saved settings: models dir, history limit {limit_input.value:.2f} GiB, agent API"
            )

        dlg.on_result = _apply
        dlg.show(self.ui)
        self.ui.set_focus(limit_input)

    def _memory_status(self) -> str:
        hist = self._document.memory_bytes()
        cache = self._layer_stack._renderer.cache_memory_bytes()
        return f"Hist:{self._fmt_bytes(hist)} Cache:{self._fmt_bytes(cache)}"

    def _on_mouse_moved(self, x, y):
        if self._layer_stack.width == 0:
            return
        w, h = self._layer_stack.width, self._layer_stack.height
        layer = self._layer_stack.active_layer
        name = layer.name if layer else "-"
        bs = self._canvas.brush.size
        tool = self._canvas.brush_tool_mode.value
        mem = self._memory_status()
        if 0 <= x < w and 0 <= y < h:
            self._statusbar.text = f"{w}x{h} | ({x},{y}) | {name} | {tool}:{bs}px | {mem}"
        else:
            self._statusbar.text = f"{w}x{h} | {name} | {tool}:{bs}px | {mem}"

    def _on_color_picked(self, r, g, b, a):
        self._canvas.brush.set_color(r, g, b, a)
        self._brush_panel.sync_from_brush()

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _apply_snapshot(self, snapshot: bytes):
        self._history_replaying = True
        try:
            self._layer_stack.load_state(snapshot)
        finally:
            self._history_replaying = False
            self._external_edit_ctx = None

    def _clear_history(self):
        self._document.clear_history()
        self._external_edit_ctx = None

    def undo(self):
        label = self._document.undo()
        if label is not None:
            self._statusbar.text = f"Undo: {label}"

    def redo(self):
        label = self._document.redo()
        if label is not None:
            self._statusbar.text = f"Redo: {label}"

    def _begin_external_edit(self, label: str, layer: Layer, target: str):
        if self._history_replaying:
            return
        if self._external_edit_ctx is not None:
            return
        if target == "selection":
            before_arr = self._layer_stack.selection.data.copy()
            self._external_edit_ctx = ExternalEditContext(
                label=label,
                layer_path="",
                target=target,
                before_arr=before_arr,
            )
            return
        layer_path = self._layer_stack.get_layer_path(layer)
        if not layer_path:
            return
        if target == "mask":
            before_arr = layer.mask.data.copy()
        else:
            before_arr = layer.image.copy()
        self._external_edit_ctx = ExternalEditContext(
            label=label,
            layer_path=layer_path,
            target=target,
            before_arr=before_arr,
        )

    def _apply_layer_patch(self, layer_path: str, target: str, rect, patch: np.ndarray):
        if target == "selection":
            x0, y0, x1, y1 = rect
            if x1 <= x0 or y1 <= y0:
                return
            self._layer_stack.selection.data[y0:y1, x0:x1] = coerce_mask_data(patch)
            if self._layer_stack.on_changed:
                self._layer_stack.on_changed()
            return
        layer = self._layer_stack.get_layer_by_path(layer_path)
        if layer is None:
            return
        x0, y0, x1, y1 = rect
        if x1 <= x0 or y1 <= y0:
            return
        if target == "mask":
            layer.mask.data[y0:y1, x0:x1] = coerce_mask_data(patch)
            if self._layer_stack.on_changed:
                self._layer_stack.on_changed()
            return
        layer.image[y0:y1, x0:x1] = patch
        self._layer_stack.mark_layer_dirty(layer, rect=rect)
        if self._layer_stack.on_changed:
            self._layer_stack.on_changed()

    def _end_external_edit(self, layer: Layer, target: str, dirty_rect):
        if self._history_replaying:
            self._external_edit_ctx = None
            return
        if self._external_edit_ctx is None:
            return
        ctx = self._external_edit_ctx
        self._external_edit_ctx = None
        if target == "selection":
            if dirty_rect is None:
                return
            x0, y0, x1, y1 = dirty_rect
            if x1 <= x0 or y1 <= y0:
                return
            before_arr = ctx.before_arr
            after_arr = self._layer_stack.selection.data
            before_patch = before_arr[y0:y1, x0:x1].copy()
            after_patch = after_arr[y0:y1, x0:x1].copy()
            if np.array_equal(before_patch, after_patch):
                return
            rect = (x0, y0, x1, y1)
            label = ctx.label
            self._document.push_callbacks(
                label=label,
                undo_fn=lambda: self._apply_layer_patch("", target, rect, before_patch),
                redo_fn=lambda: self._apply_layer_patch("", target, rect, after_patch),
                size_bytes=before_patch.nbytes + after_patch.nbytes,
            )
            return
        if layer is None:
            return
        layer_path = self._layer_stack.get_layer_path(layer)
        if layer_path != ctx.layer_path or target != ctx.target:
            return
        if dirty_rect is None:
            return
        x0, y0, x1, y1 = dirty_rect
        if x1 <= x0 or y1 <= y0:
            return
        before_arr = ctx.before_arr
        if target == "mask":
            after_arr = layer.mask.data
        else:
            after_arr = layer.image
        before_patch = before_arr[y0:y1, x0:x1].copy()
        after_patch = after_arr[y0:y1, x0:x1].copy()
        if np.array_equal(before_patch, after_patch):
            return
        rect = (x0, y0, x1, y1)
        label = ctx.label
        self._document.push_callbacks(
            label=label,
            undo_fn=lambda: self._apply_layer_patch(layer_path, target, rect, before_patch),
            redo_fn=lambda: self._apply_layer_patch(layer_path, target, rect, after_patch),
            size_bytes=before_patch.nbytes + after_patch.nbytes,
        )

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def new_project(self):
        # Simple: create white 1024x1024
        white = np.full((1024, 1024, 4), 255, dtype=np.uint8)
        self._layer_stack.init_from_image(white)
        self._clear_history()
        self._canvas.fit_in_view()
        self._project_path = None

    def new_project_from_image(self):
        def _on_result(path):
            if not path:
                return
            self._last_dir = os.path.dirname(path)
            self._settings.set("last_dir", self._last_dir)
            img = Image.open(path).convert("RGBA")
            arr = np.array(img, dtype=np.uint8)
            self._layer_stack.init_from_image(arr)
            self._clear_history()
            self._canvas.fit_in_view()
            self._project_path = None
        open_file_dialog(
            self.ui, _on_result,
            title="New From Image", directory=self._last_dir,
            filter_str="Images | *.png *.jpg *.jpeg *.bmp *.tiff *.webp")

    def open_file(self):
        def _on_result(path):
            if not path:
                return
            self._last_dir = os.path.dirname(path)
            self._settings.set("last_dir", self._last_dir)
            self.open_file_path(path)
        open_file_dialog(
            self.ui, _on_result,
            title="Open Project", directory=self._last_dir,
            filter_str="Diffusion Editor Project | *.deproj")

    def open_file_path(self, path: str):
        try:
            self._layer_stack.load_project(path)
            self._clear_history()
            self._canvas.fit_in_view()
            self._project_path = path
            self._statusbar.text = f"Opened: {os.path.basename(path)}"
        except Exception as e:
            log.exception(f"Open project failed: {path}")
            self._statusbar.text = f"Open error: {e}"

    def import_image(self):
        def _on_result(path):
            if not path:
                return
            self._last_dir = os.path.dirname(path)
            self._settings.set("last_dir", self._last_dir)
            self.import_image_path(path)
        open_file_dialog(
            self.ui, _on_result,
            title="Import Image", directory=self._last_dir,
            filter_str="Images | *.png *.jpg *.jpeg *.bmp *.tiff *.webp")

    def import_image_path(self, path: str):
        img = Image.open(path).convert("RGBA")
        arr = np.array(img, dtype=np.uint8)
        self._layer_stack.init_from_image(arr)
        self._clear_history()
        self._canvas.fit_in_view()
        self._project_path = None

    def _new_layer(self):
        self._document.execute(AddLayerCommand(
            name=self._layer_stack.next_name("Layer"),
        ))

    def _remove_layer(self, layer=None):
        if layer is None:
            layer = self._layer_stack.active_layer
        if layer is None:
            return

        def _on_result(btn: str):
            if btn == "Yes":
                self._document.execute(RemoveLayerCommand(layer=layer))

        MessageBox.question(
            self.ui,
            "Delete Layer",
            f"Delete layer \"{layer.name}\"?",
            buttons=Buttons.YES_NO,
            on_result=_on_result,
        )

    def _flatten_layers(self):
        self._document.execute(FlattenLayersCommand())

    def _select_all(self):
        self._document.execute(SelectAllCommand())

    def _clear_selection(self):
        self._document.execute(ClearSelectionCommand())

    def _invert_selection(self):
        self._document.execute(InvertSelectionCommand())

    def _move_layer(self, layer: Layer, new_parent: Layer | None, index: int):
        self._document.execute(MoveLayerCommand(
            layer=layer,
            new_parent=new_parent,
            index=index,
        ))

    def _set_layer_visibility(self, layer: Layer, visible: bool):
        self._document.execute(SetLayerVisibilityCommand(
            layer=layer,
            visible=visible,
        ))

    def _set_layer_opacity(self, layer: Layer, opacity: float):
        self._document.execute(SetLayerOpacityCommand(
            layer=layer,
            opacity=opacity,
        ))

    def save_file(self):
        if self._project_path:
            try:
                self._layer_stack.save_project(self._project_path)
                self._statusbar.text = f"Saved: {self._project_path}"
            except Exception as e:
                log.exception(f"Save project failed: {self._project_path}")
                self._statusbar.text = f"Save error: {e}"
        else:
            self.save_file_as()

    def save_file_as(self):
        def _on_result(path):
            if not path:
                return
            if not path.lower().endswith(".deproj"):
                path += ".deproj"
            self._last_dir = os.path.dirname(path)
            self._settings.set("last_dir", self._last_dir)
            try:
                self._layer_stack.save_project(path)
                self._project_path = path
                self._statusbar.text = f"Saved: {os.path.basename(path)}"
            except Exception as e:
                log.exception(f"Save project failed: {path}")
                self._statusbar.text = f"Save error: {e}"
        save_file_dialog(
            self.ui, _on_result,
            title="Save Project", directory=self._last_dir,
            filter_str="Diffusion Editor Project | *.deproj")

    def export_image(self):
        def _on_result(path):
            if not path:
                return
            self._last_dir = os.path.dirname(path)
            self._settings.set("last_dir", self._last_dir)
            arr = self._canvas.get_composite()
            if arr is None:
                return
            img = Image.fromarray(arr, "RGBA")
            if path.lower().endswith((".jpg", ".jpeg")):
                img = img.convert("RGB")
            try:
                img.save(path)
                self._statusbar.text = f"Exported: {os.path.basename(path)}"
            except Exception as e:
                log.exception(f"Export image failed: {path}")
                self._statusbar.text = f"Export error: {e}"
        save_file_dialog(
            self.ui, _on_result,
            title="Export Image", directory=self._last_dir,
            filter_str="PNG | *.png;;JPEG | *.jpg *.jpeg")

    def _fit(self):
        self._canvas.fit_in_view()

    def _quit(self):
        self._running = False

    # ------------------------------------------------------------------
    # Layer tools
    # ------------------------------------------------------------------

    def _attach_tool_to_layer(self, layer: Layer, tool_type: str):
        if layer is None or layer.tool is not None:
            return
        maker = {
            "diffusion": self._make_diffusion_tool,
            "lama": self._make_lama_tool,
            "instruct": self._make_instruct_tool,
        }.get(tool_type)
        if maker is None:
            return
        tool = maker(layer)
        if tool is None:
            return
        labels = {
            "diffusion": "Attach Diffusion Tool",
            "lama": "Attach LaMa Tool",
            "instruct": "Attach Instruct Tool",
        }
        self._document.execute(AttachLayerToolCommand(
            layer=layer,
            tool=tool,
            label=labels[tool_type],
        ))

    def _detach_tool_from_layer(self, layer: Layer):
        if layer is None or layer.tool is None:
            return
        if self._pending_request is layer:
            self._pending_request = None
        if self._pending_lama_layer is layer:
            self._pending_lama_layer = None
        if self._pending_instruct_layer is layer:
            self._pending_instruct_layer = None
        self._document.execute(DetachLayerToolCommand(layer=layer))

    def _tool_source_composite(self, layer: Layer) -> np.ndarray | None:
        composite = self._canvas.get_composite_below(layer)
        if composite is None:
            composite = self._canvas.get_composite()
        return composite

    # ------------------------------------------------------------------
    # Diffusion
    # ------------------------------------------------------------------

    def _on_load_model(self, path: str, prediction_type: str):
        if self._engine.is_busy:
            return
        pred = prediction_type if prediction_type else None
        self._engine.submit_load(path, pred)

    def _make_diffusion_tool(self, layer: Layer) -> DiffusionTool | None:
        mode = self._diffusion_panel.mode
        center_x, center_y = self._canvas.view_center_image()

        if mode == "txt2img":
            patch_pil = None
            ppx, ppy = 0, 0
            pw = self._layer_stack.width
            ph = self._layer_stack.height
        else:
            composite = self._tool_source_composite(layer)
            if composite is None:
                return None
            patch_pil, ppx, ppy, pw, ph = extract_patch(
                composite, center_x, center_y)

        seed = self._diffusion_panel.seed
        if seed < 0:
            seed = random.randint(0, 2**32 - 1)
            self._diffusion_panel.set_seed(seed)

        return DiffusionTool(
            source_patch=patch_pil,
            patch_x=ppx, patch_y=ppy, patch_w=pw, patch_h=ph,
            prompt=self._diffusion_panel.prompt,
            negative_prompt=self._diffusion_panel.negative_prompt,
            strength=self._diffusion_panel.strength,
            guidance_scale=self._diffusion_panel.guidance_scale,
            steps=self._diffusion_panel.steps,
            seed=seed,
            model_path=self._engine.model_path or "",
            prediction_type=self._diffusion_panel.prediction_type,
            mode=mode,
        )

    def _on_clear_mask(self):
        layer = self._layer_stack.active_layer
        if isinstance(layer.tool, DiffusionTool):
            self._document.execute(ClearLayerMaskCommand(
                layer=layer,
                label="Clear Diffusion Mask",
            ))

    def _sync_panel_to_layer(self, tool: DiffusionTool):
        tool.prompt = self._diffusion_panel.prompt
        tool.negative_prompt = self._diffusion_panel.negative_prompt
        tool.strength = self._diffusion_panel.strength
        tool.guidance_scale = self._diffusion_panel.guidance_scale
        tool.steps = self._diffusion_panel.steps
        tool.seed = self._diffusion_panel.seed
        tool.mode = self._diffusion_panel.mode
        tool.masked_content = self._diffusion_panel.masked_content
        tool.ip_adapter_scale = self._diffusion_panel.ip_adapter_scale
        tool.resize_to_model_resolution = self._diffusion_panel.resize_to_model_resolution
        if self._engine.model_path:
            tool.model_path = self._engine.model_path
        tool.prediction_type = self._diffusion_panel.prediction_type

    def _on_regenerate(self):
        layer = self._layer_stack.active_layer
        if not isinstance(layer.tool, DiffusionTool):
            return
        if self._engine.is_busy:
            return
        tool = layer.tool
        self._sync_panel_to_layer(tool)

        if tool.mode != "txt2img":
            composite = self._canvas.get_composite_below(layer)
            if composite is None:
                return
            if tool.manual_patch_rect is not None:
                x0, y0, x1, y1 = tool.manual_patch_rect
                h, w = composite.shape[:2]
                x0, y0 = max(0, x0), max(0, y0)
                x1, y1 = min(w, x1), min(h, y1)
                if x1 - x0 < 1 or y1 - y0 < 1:
                    return
                patch_pil = Image.fromarray(composite[y0:y1, x0:x1]).convert("RGB")
                tool.source_patch = patch_pil
                tool.patch_x, tool.patch_y = x0, y0
                tool.patch_w, tool.patch_h = x1 - x0, y1 - y0
            elif layer.has_mask():
                bbox = layer.mask_bbox()
                center = layer.mask_center()
                if bbox is not None and center is not None:
                    bx0, by0, bx1, by1 = bbox
                    ps = max(bx1 - bx0, by1 - by0)
                    ps = max(int(ps * 1.25), 512)
                    cx, cy = center
                    patch_pil, ppx, ppy, pw, ph = extract_patch(
                        composite, cx, cy, patch_size=ps)
                    tool.source_patch = patch_pil
                    tool.patch_x, tool.patch_y = ppx, ppy
                    tool.patch_w, tool.patch_h = pw, ph

            if tool.source_patch is None:
                return

        if tool.model_path and tool.model_path != self._engine.model_path:
            self._pending_request = layer
            pred = tool.prediction_type if tool.prediction_type else None
            self._engine.submit_load(tool.model_path, pred)
            self._statusbar.text = "Loading model for regeneration..."
            return

        if not self._engine.is_loaded:
            return
        self._submit_regenerate(layer)

    def _submit_regenerate(self, layer: Layer):
        tool = layer.tool
        self._pending_request = layer
        mask_image = None
        if tool.mode == "inpaint":
            if not layer.has_mask():
                self._statusbar.text = "Inpaint requires a mask"
                return
            mask_image = extract_mask_patch(
                layer.mask.data, tool.patch_x, tool.patch_y,
                tool.patch_w, tool.patch_h)

        ip_adapter_image = None
        if tool.ip_adapter_rect is not None:
            if not self._engine.ip_adapter_loaded:
                self._pending_request = layer
                self._engine.submit_load_ip_adapter()
                self._statusbar.text = "Loading IP-Adapter..."
                return
            composite = self._canvas.get_composite_below(layer)
            if composite is not None:
                x0, y0, x1, y1 = tool.ip_adapter_rect
                h, w = composite.shape[:2]
                x0, x1 = max(0, min(x0, w)), max(0, min(x1, w))
                y0, y1 = max(0, min(y0, h)), max(0, min(y1, h))
                if x1 > x0 and y1 > y0:
                    crop = composite[y0:y1, x0:x1, :3]
                    ip_adapter_image = Image.fromarray(crop, "RGB")

        submit_image = tool.source_patch
        submit_mask = mask_image
        submit_w, submit_h = tool.patch_w, tool.patch_h
        MODEL_RES = 1024
        if tool.resize_to_model_resolution and submit_image is not None:
            longest = max(submit_w, submit_h)
            if longest != MODEL_RES:
                scale = MODEL_RES / longest
                submit_w = max(8, round(tool.patch_w * scale / 8) * 8)
                submit_h = max(8, round(tool.patch_h * scale / 8) * 8)
                submit_image = submit_image.resize((submit_w, submit_h), Image.LANCZOS)
                if submit_mask is not None:
                    submit_mask = submit_mask.resize((submit_w, submit_h), Image.NEAREST)

        self._engine.submit(
            image=submit_image,
            prompt=tool.prompt,
            negative_prompt=tool.negative_prompt,
            strength=tool.strength,
            steps=tool.steps,
            guidance_scale=tool.guidance_scale,
            seed=tool.seed,
            mode=tool.mode,
            mask_image=submit_mask,
            masked_content=tool.masked_content,
            ip_adapter_image=ip_adapter_image,
            ip_adapter_scale=tool.ip_adapter_scale,
            width=submit_w,
            height=submit_h,
        )
        self._statusbar.text = f"Regenerating ({submit_w}x{submit_h})..."

    def _on_new_seed(self):
        layer = self._layer_stack.active_layer
        if not isinstance(layer.tool, DiffusionTool):
            return
        new_seed = random.randint(0, 2**32 - 1)
        layer.tool.seed = new_seed
        self._diffusion_panel.set_seed(new_seed)
        self._on_regenerate()

    def _on_load_ip_adapter(self):
        if self._engine.is_busy or not self._engine.is_loaded:
            return
        self._engine.submit_load_ip_adapter()
        self._statusbar.text = "Loading IP-Adapter..."

    def _on_ref_rect_drawn(self, x0, y0, x1, y1):
        layer = self._layer_stack.active_layer
        if isinstance(layer.tool, DiffusionTool):
            self._document.execute(SetIpAdapterRectCommand(
                layer=layer,
                rect=(x0, y0, x1, y1),
            ))

    def _on_clear_ref_rect(self):
        layer = self._layer_stack.active_layer
        if isinstance(layer.tool, DiffusionTool):
            self._document.execute(ClearIpAdapterRectCommand(layer=layer))

    def _on_patch_rect_drawn(self, x0, y0, x1, y1):
        layer = self._layer_stack.active_layer
        if isinstance(layer.tool, DiffusionTool):
            self._diffusion_panel.set_draw_patch_checked(False)
            self._document.execute(SetManualPatchRectCommand(
                layer=layer,
                rect=(x0, y0, x1, y1),
                label="Set Diffusion Patch Rect",
            ))
        elif isinstance(layer.tool, InstructTool):
            self._instruct_panel.set_draw_patch_checked(False)
            self._document.execute(SetManualPatchRectCommand(
                layer=layer,
                rect=(x0, y0, x1, y1),
                label="Set Instruct Patch Rect",
            ))

    def _on_clear_patch_rect(self):
        layer = self._layer_stack.active_layer
        if isinstance(layer.tool, DiffusionTool):
            self._document.execute(ClearManualPatchRectCommand(
                layer=layer,
                label="Clear Diffusion Patch Rect",
            ))

    def _on_selection_rect_drawn(self, x0: int, y0: int, x1: int, y1: int):
        """Create a rectangular selection from the dragged rect."""
        h, w = self._layer_stack.height, self._layer_stack.width
        if h == 0 or w == 0:
            return
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(w, x1)
        y1 = min(h, y1)
        if x1 <= x0 or y1 <= y0:
            return
        mask = np.zeros((h, w), dtype=np.float32)
        mask[y0:y1, x0:x1] = 1.0
        self._document.execute(SetLayerSelectionCommand(
            mask=mask,
            label="Rect Selection",
        ))
        # Uncheck the rect button in the panel
        self._selection_panel._rect_mode_cb.checked = False

    # ------------------------------------------------------------------
    # LaMa
    # ------------------------------------------------------------------

    def _make_lama_tool(self, layer: Layer) -> LamaTool | None:
        composite = self._tool_source_composite(layer)
        if composite is None:
            return None
        cx, cy = self._canvas.view_center_image()
        patch_pil, ppx, ppy, pw, ph = extract_patch(composite, cx, cy)
        return LamaTool(
            source_patch=patch_pil,
            patch_x=ppx, patch_y=ppy, patch_w=pw, patch_h=ph,
        )

    def _on_lama_remove(self):
        layer = self._layer_stack.active_layer
        if not isinstance(layer.tool, LamaTool):
            return
        tool = layer.tool
        if self._lama_engine.is_busy or not layer.has_mask():
            return

        bbox = layer.mask_bbox()
        center = layer.mask_center()
        if bbox is None or center is None:
            return
        composite = self._canvas.get_composite_below(layer)
        if composite is None:
            return

        bx0, by0, bx1, by1 = bbox
        ps = max(bx1 - bx0, by1 - by0)
        ps = max(int(ps * 1.25), 512)
        cx, cy = center
        patch_pil, ppx, ppy, pw, ph = extract_patch(composite, cx, cy, patch_size=ps)
        tool.source_patch = patch_pil
        tool.patch_x, tool.patch_y = ppx, ppy
        tool.patch_w, tool.patch_h = pw, ph

        mask_pil = extract_mask_patch(layer.mask.data, ppx, ppy, pw, ph)
        self._lama_engine.submit(patch_pil, mask_pil)
        self._pending_lama_layer = layer
        self._statusbar.text = "Removing objects (LaMa)..."

    def _on_lama_clear_mask(self):
        layer = self._layer_stack.active_layer
        if isinstance(layer.tool, LamaTool):
            self._document.execute(ClearLayerMaskCommand(
                layer=layer,
                label="Clear LaMa Mask",
            ))

    def _on_lama_select_background(self):
        layer = self._layer_stack.active_layer
        if not isinstance(layer.tool, LamaTool):
            return
        if self._seg_engine.is_busy:
            return
        composite = self._canvas.get_composite_below(layer)
        if composite is None:
            return
        self._seg_engine.submit(composite, invert=True)
        self._statusbar.text = "Segmenting background..."

    # ------------------------------------------------------------------
    # InstructPix2Pix
    # ------------------------------------------------------------------

    def _make_instruct_tool(self, layer: Layer) -> InstructTool | None:
        composite = self._tool_source_composite(layer)
        if composite is None:
            return None
        cx, cy = self._canvas.view_center_image()
        patch_pil, ppx, ppy, pw, ph = extract_patch(composite, cx, cy)
        seed = self._instruct_panel.seed
        if seed < 0:
            seed = random.randint(0, 2**32 - 1)
            self._instruct_panel.set_seed(seed)
        return InstructTool(
            source_patch=patch_pil,
            patch_x=ppx, patch_y=ppy, patch_w=pw, patch_h=ph,
            instruction=self._instruct_panel.instruction,
            image_guidance_scale=self._instruct_panel.image_guidance_scale,
            guidance_scale=self._instruct_panel.guidance_scale,
            steps=self._instruct_panel.steps,
            seed=seed,
        )

    def _on_instruct_load_model(self):
        if self._instruct_engine.is_busy:
            return
        self._instruct_panel.set_model_loading()
        self._instruct_engine.submit_load()
        self._statusbar.text = "Loading InstructPix2Pix model..."

    def _on_instruct_apply(self):
        layer = self._layer_stack.active_layer
        if not isinstance(layer.tool, InstructTool):
            return
        if self._instruct_engine.is_busy:
            return
        tool = layer.tool

        tool.instruction = self._instruct_panel.instruction
        tool.image_guidance_scale = self._instruct_panel.image_guidance_scale
        tool.guidance_scale = self._instruct_panel.guidance_scale
        tool.steps = self._instruct_panel.steps
        tool.seed = self._instruct_panel.seed

        if not self._instruct_engine.is_loaded:
            self._pending_instruct_layer = layer
            self._on_instruct_load_model()
            return

        composite = self._canvas.get_composite_below(layer)
        if composite is None:
            return

        if tool.manual_patch_rect is not None:
            x0, y0, x1, y1 = tool.manual_patch_rect
            h, w = composite.shape[:2]
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(w, x1), min(h, y1)
            if x1 - x0 < 1 or y1 - y0 < 1:
                return
            patch_pil = Image.fromarray(composite[y0:y1, x0:x1]).convert("RGB")
            tool.source_patch = patch_pil
            tool.patch_x, tool.patch_y = x0, y0
            tool.patch_w, tool.patch_h = x1 - x0, y1 - y0
        elif layer.has_mask():
            bbox = layer.mask_bbox()
            center = layer.mask_center()
            if bbox is not None and center is not None:
                bx0, by0, bx1, by1 = bbox
                ps = max(bx1 - bx0, by1 - by0)
                ps = max(int(ps * 1.25), 512)
                cx, cy = center
                patch_pil, ppx, ppy, pw, ph = extract_patch(
                    composite, cx, cy, patch_size=ps)
                tool.source_patch = patch_pil
                tool.patch_x, tool.patch_y = ppx, ppy
                tool.patch_w, tool.patch_h = pw, ph
        else:
            cx = tool.patch_x + tool.patch_w // 2
            cy = tool.patch_y + tool.patch_h // 2
            patch_pil, ppx, ppy, pw, ph = extract_patch(
                composite, cx, cy, patch_size=max(tool.patch_w, tool.patch_h))
            tool.source_patch = patch_pil
            tool.patch_x, tool.patch_y = ppx, ppy
            tool.patch_w, tool.patch_h = pw, ph

        self._instruct_engine.submit(
            image=tool.source_patch,
            instruction=tool.instruction,
            guidance_scale=tool.guidance_scale,
            image_guidance_scale=tool.image_guidance_scale,
            steps=tool.steps,
            seed=tool.seed,
        )
        self._pending_instruct_layer = layer
        self._statusbar.text = "Applying instruction..."

    def _on_instruct_new_seed(self):
        layer = self._layer_stack.active_layer
        if not isinstance(layer.tool, InstructTool):
            return
        new_seed = random.randint(0, 2**32 - 1)
        layer.tool.seed = new_seed
        self._instruct_panel.set_seed(new_seed)
        self._on_instruct_apply()

    def _on_instruct_clear_mask(self):
        layer = self._layer_stack.active_layer
        if isinstance(layer.tool, InstructTool):
            self._document.execute(ClearLayerMaskCommand(
                layer=layer,
                label="Clear Instruct Mask",
            ))

    def _on_instruct_clear_patch_rect(self):
        layer = self._layer_stack.active_layer
        if isinstance(layer.tool, InstructTool):
            self._document.execute(ClearManualPatchRectCommand(
                layer=layer,
                label="Clear Instruct Patch Rect",
            ))

    # ------------------------------------------------------------------
    # Segmentation
    # ------------------------------------------------------------------

    def _on_select_background(self):
        layer = self._layer_stack.active_layer
        if not isinstance(layer.tool, DiffusionTool):
            return
        if self._seg_engine.is_busy:
            return
        composite = self._canvas.get_composite_below(layer)
        if composite is None:
            return
        self._seg_engine.submit(composite, invert=True)
        self._statusbar.text = "Segmenting background..."

    # ------------------------------------------------------------------
    # Polling (called every frame from SDL main loop)
    # ------------------------------------------------------------------

    def poll(self):
        self._agent_chat_panel.poll()
        self._poll_segmentation()
        self._poll_lama()
        self._poll_instruct()
        self._poll_diffusion()
        self._poll_grounding()

    def _poll_segmentation(self):
        seg_mask, seg_error = self._seg_engine.poll()
        if seg_mask is not None:
            layer = self._layer_stack.active_layer
            command, status = map_segmentation_result(layer, seg_mask)
            if command is not None:
                self._document.execute(command)
            self._statusbar.text = status
        elif seg_error is not None:
            log.error(f"Segmentation error: {seg_error}")
            self._statusbar.text = f"Segmentation error: {seg_error[:80]}"

    def _poll_lama(self):
        result_image, lama_error = self._lama_engine.poll()
        if result_image is not None:
            layer = self._pending_lama_layer
            command, status = map_lama_result(layer, result_image)
            if command is not None:
                self._document.execute(command)
            self._statusbar.text = status
            self._pending_lama_layer = None
        elif lama_error is not None:
            log.error(f"LaMa error: {lama_error}")
            self._statusbar.text = f"LaMa error: {lama_error[:80]}"
            self._pending_lama_layer = None

    def _poll_instruct(self):
        task_type, result, error, meta = self._instruct_engine.poll()
        if task_type is None:
            return
        if task_type == "load":
            if error:
                log.error(f"InstructPix2Pix load error: {error}")
                self._instruct_panel.on_model_load_error(error)
                self._statusbar.text = f"InstructPix2Pix load error: {error[:80]}"
                self._pending_instruct_layer = None
            else:
                self._instruct_panel.on_model_loaded()
                self._statusbar.text = "InstructPix2Pix model loaded"
                if isinstance(self._pending_instruct_layer.tool, InstructTool):
                    self._on_instruct_apply()
        elif task_type == "inference":
            if error:
                log.error(f"InstructPix2Pix inference error: {error}")
                self._statusbar.text = f"InstructPix2Pix error: {error[:80]}"
                self._pending_instruct_layer = None
                return
            result_image, used_seed = result
            layer = self._pending_instruct_layer
            command, status = map_instruct_result(layer, result_image, used_seed)
            if command is not None:
                self._document.execute(command)
            self._statusbar.text = status
            self._pending_instruct_layer = None

    def _poll_diffusion(self):
        task_type, result, error, meta = self._engine.poll()
        if task_type is None:
            return

        log.debug(
            f"[_poll_diffusion] task_type={task_type}, error={error}, result_type={type(result)}"
        )

        if task_type == "load":
            if error:
                log.error(f"Diffusion model load error: {error}")
                self._diffusion_panel.on_model_load_error(error)
                self._statusbar.text = f"Model load error: {error[:80]}"
                self._pending_request = None
            else:
                self._diffusion_panel.on_model_loaded(result, self._engine.model_info)
                pending = self._pending_request
                if pending is not None and isinstance(pending.tool, DiffusionTool):
                    self._submit_regenerate(pending)
                    return
                self._statusbar.text = "Model loaded"

        elif task_type == "load_ip_adapter":
            if error:
                log.error(f"IP-Adapter load error: {error}")
                self._diffusion_panel.on_ip_adapter_load_error(error)
                self._statusbar.text = f"IP-Adapter error: {error[:80]}"
                self._pending_request = None
            else:
                self._diffusion_panel.on_ip_adapter_loaded()
                pending = self._pending_request
                if pending is not None and isinstance(pending.tool, DiffusionTool):
                    self._submit_regenerate(pending)
                    return
                self._statusbar.text = "IP-Adapter loaded"

        elif task_type == "inference":
            if error:
                log.error(f"Diffusion inference error: {error}")
                self._statusbar.text = f"Diffusion error: {error[:80]}"
                self._pending_request = None
                return

            pending = self._pending_request
            if pending is None:
                self._statusbar.text = "Diffusion result ignored: no pending layer"
                return
            result_image, used_seed = result
            log.debug(
                f"[_poll_diffusion] inference OK, seed={used_seed}, pending={type(pending).__name__}"
            )
            command, status = map_diffusion_result(
                pending, result_image, used_seed)
            if command is not None:
                self._document.execute(command)
            self._statusbar.text = status
            self._pending_request = None

    def _show_grounding_dialog(self) -> None:
        GroundingDialog(self).show()

    def _poll_grounding(self) -> None:
        if self._pending_grounding_result is None:
            return
        results, layer = self._pending_grounding_result
        self._pending_grounding_result = None

        from .commands import DrawRectCommand, FillMaskCommand, SetLayerSelectionCommand

        rect_colors = [
            (255, 80, 80, 255),
            (80, 255, 80, 255),
            (80, 80, 255, 255),
            (255, 255, 80, 255),
            (255, 80, 255, 255),
            (80, 255, 255, 255),
        ]
        fill_colors = [
            (255, 80, 80, 100),
            (80, 255, 80, 100),
            (80, 80, 255, 100),
            (255, 255, 80, 100),
            (255, 80, 255, 100),
            (80, 255, 255, 100),
        ]
        # Combine all detection masks into a single selection (union)
        h, w = layer.height, layer.width
        combined_selection = np.zeros((h, w), dtype=np.float32)
        for i, item in enumerate(results):
            if len(item) == 7:
                label, x0, y0, x1, y1, score, mask = item
            else:
                label, x0, y0, x1, y1, score = item
                mask = None

            rect_color = rect_colors[i % len(rect_colors)]
            cmd = DrawRectCommand(
                layer=layer,
                x=x0, y=y0,
                width=x1 - x0, height=y1 - y0,
                color=rect_color,
                thickness=1,
                label=f"Detect: {label} ({score:.0%})",
            )
            self._document.execute(cmd)

            if mask is not None and mask.any():
                # Visual fill on the layer image
                mask_cmd = FillMaskCommand(
                    layer=layer,
                    mask=mask,
                    color=fill_colors[i % len(fill_colors)],
                    outline_color=rect_colors[i % len(rect_colors)],
                    label=f"Segment: {label}",
                )
                self._document.execute(mask_cmd)
                # Contribute to combined selection
                combined_selection = np.maximum(
                    combined_selection,
                    mask.astype(np.float32)[:h, :w],
                )

        # Set the combined selection on the layer stack
        if combined_selection.any():
            sel_cmd = SetLayerSelectionCommand(
                mask=combined_selection,
                label="Set Selection from Detection",
            )
            self._document.execute(sel_cmd)

    # ------------------------------------------------------------------
    # Public: rendering
    # ------------------------------------------------------------------

    # Background colour painted by the UIRenderer's offscreen clear
    # so transparent UI regions show this through the composite.
    UI_BACKGROUND = (0.12, 0.12, 0.14, 1.0)

    def render(self, vw: int, vh: int):
        self.ui.render(vw, vh, background_color=self.UI_BACKGROUND)

    def render_compose(self, vw: int, vh: int):
        """Render the UI and return the composite TextureHandle.

        Preferred when the host owns a BackendWindow and publishes the
        result via ``win.present(tex)`` — works on both OpenGL and
        Vulkan. ``None`` if the UI is empty.
        """
        return self.ui.render_compose(vw, vh, background_color=self.UI_BACKGROUND)

    @property
    def running(self) -> bool:
        return self._running

    def close(self):
        """Release runtime resources (GPU/engines). Safe to call multiple times."""
        if self._closed:
            return
        self._closed = True
        self._running = False
        if hasattr(self, "_canvas") and self._canvas is not None:
            self._canvas.dispose()
        if hasattr(self, "_agent_chat_panel") and self._agent_chat_panel is not None:
            self._agent_chat_panel.shutdown()
        self._engine.shutdown()
        self._instruct_engine.shutdown()
        self._lama_engine.shutdown()
        self._seg_engine.shutdown()
