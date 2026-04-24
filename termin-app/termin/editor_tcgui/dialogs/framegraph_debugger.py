"""Framegraph Debugger — visualize intermediate FBOs and debug render passes.

UI layer only. State + business logic lives in
:class:`termin.editor_core.framegraph_debugger_model.FramegraphDebuggerModel`.
This file builds tcgui widgets, subscribes to model Signals, and forwards
widget events back into model setters.
"""
from __future__ import annotations

from tcbase import log

from tcgui.widgets.widget import Widget
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.units import px, pct

from termin.editor_core.framegraph_debugger_model import FramegraphDebuggerModel


class CapturePreviewWidget(Widget):
    """Renders captured FBO texture via C++ presenter (shared GL textures)."""

    def __init__(self) -> None:
        super().__init__()
        self._core = None
        self._fbo_surface = None
        self.channel_mode: int = 0
        self.highlight_hdr: bool = False
        self.has_content: bool = False

    def render(self, renderer) -> None:
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           (0.08, 0.08, 0.08, 1.0))
        if not self.has_content or self._core is None:
            return
        capture_tex = self._core.capture_tex
        if not capture_tex:
            return
        tex_w = int(self._core.capture.width)
        tex_h = int(self._core.capture.height)
        if tex_w == 0 or tex_h == 0:
            return
        renderer.draw_texture(
            self.x, self.y, self.width, self.height,
            handle=capture_tex,
            tex_w=tex_w,
            tex_h=tex_h,
        )


class _FramegraphDebuggerHandle:
    """Public handle returned by ``show_framegraph_debugger``.

    The editor calls ``update()`` per frame and ``close()`` to tear down.
    All real state lives in ``self.model``; this class is responsible for
    turning model signals into widget updates and widget events into
    model setter calls.
    """

    def __init__(self, model: FramegraphDebuggerModel) -> None:
        self.model = model
        self.window_ui = None
        self.visible: bool = False

        self._updating: bool = False

        self._viewport_combo: ComboBox | None = None
        self._mode_combo: ComboBox | None = None
        self._pass_combo: ComboBox | None = None
        self._symbol_combo: ComboBox | None = None
        self._resource_combo: ComboBox | None = None
        self._channel_combo: ComboBox | None = None
        self._pause_check: Checkbox | None = None
        self._hdr_highlight_check: Checkbox | None = None

        self._timing_label: Label | None = None
        self._fbo_info_label: Label | None = None
        self._render_stats_label: Label | None = None
        self._writer_pass_label: Label | None = None
        self._hdr_stats_label: Label | None = None
        self._status_label: Label | None = None

        self._pipeline_text: TextArea | None = None
        self._pass_json: TextArea | None = None

        self._preview: CapturePreviewWidget | None = None

        self._inside_panel: VStack | None = None
        self._between_panel: VStack | None = None
        self._panel_slot: VStack | None = None

    # ------------------------------------------------------------------
    # Subscribe to model
    # ------------------------------------------------------------------

    def bind_signals(self) -> None:
        self.model.lists_changed.connect(self._on_lists_changed)
        self.model.selection_changed.connect(self._on_selection_changed)
        self.model.info_changed.connect(self._on_info_changed)
        self.model.capture_updated.connect(self._on_capture_updated)
        self.model.preview_params_changed.connect(self._on_preview_params_changed)
        self.model.hdr_stats_changed.connect(self._on_hdr_stats_changed)

    # ------------------------------------------------------------------
    # Model → widget updates
    # ------------------------------------------------------------------

    def _on_lists_changed(self, _model) -> None:
        self._refresh_viewport_combo()
        self._refresh_resource_combo()
        self._refresh_pass_combo()
        self._refresh_symbol_combo()

    def _on_selection_changed(self, _model) -> None:
        # Mode panel swap happens here because it's a structural change
        # to the widget tree: tcgui VStack doesn't re-layout when an
        # existing child toggles visibility, so we swap children.
        if self._panel_slot is not None:
            self._panel_slot.children.clear()
            if self.model.mode == "inside":
                if self._inside_panel is not None:
                    self._panel_slot.add_child(self._inside_panel)
            else:
                if self._between_panel is not None:
                    self._panel_slot.add_child(self._between_panel)
            if self.window_ui is not None:
                self.window_ui.request_layout()

        # Reflect current selection in combos without triggering events.
        self._updating = True
        if self._mode_combo is not None:
            self._mode_combo.selected_index = 0 if self.model.mode == "inside" else 1
        if self._pass_combo is not None and self.model.selected_pass is not None:
            for i in range(self._pass_combo.item_count):
                name = self._pass_name_from_display(self._pass_combo.item_text(i))
                if name == self.model.selected_pass:
                    self._pass_combo.selected_index = i
                    break
        if self._symbol_combo is not None and self.model.selected_symbol is not None:
            for i in range(self._symbol_combo.item_count):
                if self._symbol_combo.item_text(i) == self.model.selected_symbol:
                    self._symbol_combo.selected_index = i
                    break
        if self._resource_combo is not None and self.model.debug_source_res:
            for i in range(self._resource_combo.item_count):
                if self._resource_combo.item_text(i) == self.model.debug_source_res:
                    self._resource_combo.selected_index = i
                    break
        self._updating = False

    def _on_info_changed(self, _model) -> None:
        if self._fbo_info_label is not None:
            self._fbo_info_label.text = self.model.format_fbo_info()
        if self._writer_pass_label is not None:
            self._writer_pass_label.text = self.model.format_writer_pass()
        if self._pipeline_text is not None:
            self._pipeline_text.text = self.model.format_pipeline_info()
        if self._pass_json is not None:
            self._pass_json.text = self.model.format_pass_json()
        if self._timing_label is not None:
            self._timing_label.text = self.model.format_timing()
        if self._render_stats_label is not None:
            self._render_stats_label.text = self.model.format_render_stats()

    def _on_capture_updated(self, _model) -> None:
        if self._preview is not None:
            self._preview.has_content = True

    def _on_preview_params_changed(self, _model) -> None:
        if self._preview is not None:
            self._preview.channel_mode = self.model.channel_mode
            self._preview.highlight_hdr = self.model.highlight_hdr

    def _on_hdr_stats_changed(self, text: str) -> None:
        if self._hdr_stats_label is not None:
            self._hdr_stats_label.text = text

    # ------------------------------------------------------------------
    # Combo refreshers
    # ------------------------------------------------------------------

    def _refresh_viewport_combo(self) -> None:
        if self._viewport_combo is None:
            return
        viewports = self.model.viewports
        self._updating = True
        self._viewport_combo.clear()
        for _, label in viewports:
            self._viewport_combo.add_item(label)
        if viewports:
            current = self.model.current_viewport
            idx = 0
            for i, (vp, _) in enumerate(viewports):
                if vp is current:
                    idx = i
                    break
            self._viewport_combo.selected_index = idx
        self._updating = False

    def _refresh_resource_combo(self) -> None:
        if self._resource_combo is None:
            return
        names = self.model.get_resources()
        self._updating = True
        self._resource_combo.clear()
        for name in names:
            self._resource_combo.add_item(name)
        if names and self.model.debug_source_res in names:
            self._resource_combo.selected_index = names.index(self.model.debug_source_res)
        elif names:
            self._resource_combo.selected_index = 0
        self._updating = False

    def _refresh_pass_combo(self) -> None:
        if self._pass_combo is None:
            return
        passes_info = self.model.get_passes()
        self._updating = True
        self._pass_combo.clear()
        selected_index = -1
        for i, (name, has_sym) in enumerate(passes_info):
            display_name = f"{name} *" if has_sym else name
            self._pass_combo.add_item(display_name)
            if name == self.model.selected_pass:
                selected_index = i
        if selected_index >= 0:
            self._pass_combo.selected_index = selected_index
        self._updating = False

    def _refresh_symbol_combo(self) -> None:
        if self._symbol_combo is None:
            return
        symbols = self.model.get_symbols()
        self._updating = True
        self._symbol_combo.clear()
        selected_index = -1
        for i, sym in enumerate(symbols):
            self._symbol_combo.add_item(sym)
            if sym == self.model.selected_symbol:
                selected_index = i
        if selected_index >= 0:
            self._symbol_combo.selected_index = selected_index
        self._updating = False

    @staticmethod
    def _pass_name_from_display(display_name: str) -> str:
        if display_name.endswith(" *"):
            return display_name[:-2]
        return display_name

    # ------------------------------------------------------------------
    # Per-frame update — editor calls this
    # ------------------------------------------------------------------

    def update(self) -> None:
        if not self.visible:
            return
        self.model.notify_frame_rendered()

    def close(self) -> None:
        self.model.disconnect()
        self.visible = False


def show_framegraph_debugger(
    ui, rendering_controller, fbo_surface,
    on_request_update=None,
) -> _FramegraphDebuggerHandle | None:
    """Create and show the Framegraph Debugger in a dedicated tcgui window."""

    if ui.create_window is None:
        log.error("[FrameDebugger] ui.create_window is not available — cannot open")
        return None

    from termin._native.editor import FrameGraphDebuggerCore

    core = FrameGraphDebuggerCore()
    model = FramegraphDebuggerModel(
        rendering_controller=rendering_controller,
        core=core,
        on_request_update=on_request_update,
    )
    handle = _FramegraphDebuggerHandle(model)

    # ---- Build UI ----

    content = VStack()
    content.preferred_width = pct(100)
    content.preferred_height = pct(100)
    content.padding = 6
    content.spacing = 6

    # Top area: settings (left) + pipeline schedule (right)
    top_area = HStack()
    top_area.spacing = 8
    top_area.preferred_height = px(320)

    settings = VStack()
    settings.spacing = 4
    settings.stretch = True

    # Viewport row
    vp_row = HStack()
    vp_row.spacing = 4
    vp_label = Label(); vp_label.text = "Viewport:"
    vp_row.add_child(vp_label)
    viewport_combo = ComboBox()
    viewport_combo.stretch = True
    handle._viewport_combo = viewport_combo
    vp_row.add_child(viewport_combo)
    settings.add_child(vp_row)

    # Render stats
    stats_row = HStack()
    stats_row.spacing = 4
    render_stats_label = Label(); render_stats_label.text = ""
    handle._render_stats_label = render_stats_label
    stats_row.add_child(render_stats_label)
    refresh_stats_btn = Button()
    refresh_stats_btn.text = "Refresh"; refresh_stats_btn.padding = 4
    stats_row.add_child(refresh_stats_btn)
    settings.add_child(stats_row)

    # Mode selection
    mode_row = HStack()
    mode_row.spacing = 4
    mode_label = Label(); mode_label.text = "Mode:"
    mode_row.add_child(mode_label)
    mode_combo = ComboBox()
    mode_combo.items = ["Passes", "Resources"]
    mode_combo.selected_index = 0
    mode_combo.preferred_width = px(120)
    handle._mode_combo = mode_combo
    mode_row.add_child(mode_combo)
    settings.add_child(mode_row)

    # Mode-dependent slot
    panel_slot = VStack()
    panel_slot.spacing = 4
    handle._panel_slot = panel_slot
    settings.add_child(panel_slot)

    # "Resources" panel
    between_panel = VStack()
    between_panel.spacing = 4
    handle._between_panel = between_panel

    res_row = HStack()
    res_row.spacing = 4
    r_label = Label(); r_label.text = "Resource:"
    res_row.add_child(r_label)
    resource_combo = ComboBox()
    resource_combo.stretch = True
    handle._resource_combo = resource_combo
    res_row.add_child(resource_combo)
    between_panel.add_child(res_row)

    writer_pass_label = Label(); writer_pass_label.text = ""
    handle._writer_pass_label = writer_pass_label
    between_panel.add_child(writer_pass_label)

    hdr_row = HStack()
    hdr_row.spacing = 4
    hdr_highlight_check = Checkbox()
    hdr_highlight_check.text = "Highlight HDR"
    handle._hdr_highlight_check = hdr_highlight_check
    hdr_row.add_child(hdr_highlight_check)
    analyze_btn = Button()
    analyze_btn.text = "Analyze"; analyze_btn.padding = 4
    hdr_row.add_child(analyze_btn)
    between_panel.add_child(hdr_row)

    hdr_stats_label = Label(); hdr_stats_label.text = ""
    handle._hdr_stats_label = hdr_stats_label
    between_panel.add_child(hdr_stats_label)

    # "Passes" panel
    inside_panel = VStack()
    inside_panel.spacing = 4
    handle._inside_panel = inside_panel

    pass_row = HStack()
    pass_row.spacing = 4
    p_label = Label(); p_label.text = "Pass:"
    pass_row.add_child(p_label)
    pass_combo = ComboBox()
    pass_combo.stretch = True
    handle._pass_combo = pass_combo
    pass_row.add_child(pass_combo)
    inside_panel.add_child(pass_row)

    sym_row = HStack()
    sym_row.spacing = 4
    s_label = Label(); s_label.text = "Symbol:"
    sym_row.add_child(s_label)
    symbol_combo = ComboBox()
    symbol_combo.stretch = True
    handle._symbol_combo = symbol_combo
    sym_row.add_child(symbol_combo)
    inside_panel.add_child(sym_row)

    timing_label = Label(); timing_label.text = ""
    handle._timing_label = timing_label
    inside_panel.add_child(timing_label)

    pass_json = TextArea()
    pass_json.read_only = True
    pass_json.word_wrap = False
    pass_json.stretch = True
    pass_json.placeholder = "Pass JSON"
    handle._pass_json = pass_json
    inside_panel.add_child(pass_json)

    # Default: Passes panel
    panel_slot.add_child(inside_panel)

    # FBO info
    fbo_info_label = Label(); fbo_info_label.text = ""
    handle._fbo_info_label = fbo_info_label
    settings.add_child(fbo_info_label)

    # Pause + channel
    controls_row = HStack()
    controls_row.spacing = 8
    pause_check = Checkbox()
    pause_check.text = "Pause"
    handle._pause_check = pause_check
    controls_row.add_child(pause_check)
    ch_label = Label(); ch_label.text = "Channel:"
    controls_row.add_child(ch_label)
    channel_combo = ComboBox()
    channel_combo.items = ["RGB", "R", "G", "B", "A"]
    channel_combo.selected_index = 0
    channel_combo.preferred_width = px(70)
    handle._channel_combo = channel_combo
    controls_row.add_child(channel_combo)
    settings.add_child(controls_row)

    top_area.add_child(settings)

    # Pipeline schedule
    pipeline_panel = VStack()
    pipeline_panel.spacing = 4
    pipeline_panel.stretch = True
    sched_title = Label(); sched_title.text = "Pipeline Schedule"
    pipeline_panel.add_child(sched_title)
    pipeline_text = TextArea()
    pipeline_text.read_only = True
    pipeline_text.word_wrap = False
    pipeline_text.stretch = True
    pipeline_text.placeholder = "No pipeline"
    handle._pipeline_text = pipeline_text
    pipeline_panel.add_child(pipeline_text)

    top_area.add_child(pipeline_panel)
    content.add_child(top_area)

    # Viewer: preview + depth panel
    viewer_area = HStack()
    viewer_area.spacing = 8
    viewer_area.stretch = True

    preview = CapturePreviewWidget()
    preview.stretch = True
    preview._core = core
    preview._fbo_surface = fbo_surface
    handle._preview = preview
    viewer_area.add_child(preview)

    depth_panel = VStack()
    depth_panel.spacing = 4
    depth_panel.preferred_width = px(300)
    depth_header = HStack()
    depth_header.spacing = 4
    depth_title = Label(); depth_title.text = "Depth Buffer"
    depth_header.add_child(depth_title)
    refresh_depth_btn = Button()
    refresh_depth_btn.text = "Refresh"; refresh_depth_btn.padding = 4
    depth_header.add_child(refresh_depth_btn)
    depth_panel.add_child(depth_header)
    status_label = Label(); status_label.text = ""
    handle._status_label = status_label
    depth_panel.add_child(status_label)
    viewer_area.add_child(depth_panel)
    content.add_child(viewer_area)

    # Footer
    footer = HStack()
    footer.spacing = 6
    footer.preferred_height = px(32)
    footer_spacer = Label(); footer_spacer.text = ""; footer_spacer.stretch = True
    footer.add_child(footer_spacer)
    close_btn = Button()
    close_btn.text = "Close"
    close_btn.preferred_width = px(90)
    close_btn.padding = 4
    footer.add_child(close_btn)
    content.add_child(footer)

    # ---- Event handlers ----

    def on_viewport_changed(idx, _text):
        if handle._updating:
            return
        model.set_viewport_by_index(idx)

    def on_mode_changed(idx, _text):
        if handle._updating:
            return
        model.set_mode("inside" if idx == 0 else "between")

    def on_pass_changed(idx, text):
        if handle._updating or idx < 0:
            return
        model.set_selected_pass(handle._pass_name_from_display(text))

    def on_symbol_changed(idx, text):
        if handle._updating or not text:
            return
        model.set_selected_symbol(text)

    def on_resource_changed(idx, text):
        if handle._updating or not text:
            return
        model.set_source_resource(text)

    def on_pause_changed(checked):
        model.set_paused(bool(checked))

    def on_channel_changed(idx, _text):
        if handle._updating:
            return
        model.set_channel_mode(idx)

    def on_hdr_highlight_changed(checked):
        model.set_highlight_hdr(bool(checked))

    def on_analyze_hdr():
        model.analyze_hdr()

    def on_refresh_depth():
        capture_tex = core.capture_tex
        if not capture_tex:
            status_label.text = "No capture for depth"
            return
        from termin.visualization.render.manager import RenderingManager
        render_engine = RenderingManager.instance().render_engine
        if render_engine is None:
            status_label.text = "No render engine"
            return
        render_engine.ensure_tgfx2()
        device = render_engine.tgfx2_device
        if device is None:
            status_label.text = "No tgfx2 device"
            return
        try:
            result = core.presenter.read_depth_normalized(device, capture_tex)
            if result is None:
                status_label.text = "No depth data"
            else:
                _, w, h = result
                status_label.text = f"Depth: {w}x{h} read OK"
        except Exception as e:
            log.error(f"[FrameDebugger] depth read failed: {e}")
            status_label.text = f"Depth error: {e}"

    def on_refresh_stats():
        model.refresh_render_stats()

    # Wire widget events
    viewport_combo.on_changed = on_viewport_changed
    mode_combo.on_changed = on_mode_changed
    pass_combo.on_changed = on_pass_changed
    symbol_combo.on_changed = on_symbol_changed
    resource_combo.on_changed = on_resource_changed
    pause_check.on_changed = on_pause_changed
    channel_combo.on_changed = on_channel_changed
    hdr_highlight_check.on_changed = on_hdr_highlight_changed
    analyze_btn.on_click = on_analyze_hdr
    refresh_depth_btn.on_click = on_refresh_depth
    refresh_stats_btn.on_click = on_refresh_stats

    # ---- Create dedicated window ----

    window_ui = ui.create_window("Framegraph Debugger", 950, 700)
    if window_ui is None:
        log.error("[FrameDebugger] create_window returned None")
        return None

    handle.window_ui = window_ui
    handle.visible = True
    window_ui.root = content

    native_close = window_ui.close_window

    def _on_close():
        handle.close()
        if native_close is not None:
            native_close()

    window_ui.close_window = _on_close
    window_ui.on_empty = _on_close
    close_btn.on_click = _on_close

    # Subscribe handle to model and do initial population.
    handle.bind_signals()
    model.refresh_viewports()
    # ``refresh_viewports`` fires lists_changed but not info_changed, so
    # pull initial info text now.
    handle._on_info_changed(model)
    # Auto-select the first resource so schedule/writer info populate.
    if resource_combo.item_count > 0:
        model.set_source_resource(resource_combo.item_text(0))

    return handle
