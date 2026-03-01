"""Framegraph Debugger — visualize intermediate FBOs and debug render passes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from OpenGL.GL import glDisable, glEnable, GL_SCISSOR_TEST

from tcbase import log

from tcgui.widgets.widget import Widget
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.units import px

if TYPE_CHECKING:
    from tgfx import GraphicsBackend


class CapturePreviewWidget(Widget):
    """Renders captured FBO texture via C++ presenter (shared GL textures)."""

    def __init__(self) -> None:
        super().__init__()
        self._core = None
        self._graphics: GraphicsBackend | None = None
        self.channel_mode: int = 0
        self.highlight_hdr: bool = False
        self.has_content: bool = False

    def render(self, renderer) -> None:
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           (0.08, 0.08, 0.08, 1.0))
        if not self.has_content or self._core is None:
            return
        capture_fbo = self._core.capture_fbo
        if capture_fbo is None:
            return

        glDisable(GL_SCISSOR_TEST)
        vp_h = renderer._viewport_h
        dst_x = int(self.x)
        dst_y = int(vp_h - self.y - self.height)
        dst_w, dst_h = int(self.width), int(self.height)
        self._graphics.set_viewport(dst_x, dst_y, dst_w, dst_h)
        self._core.presenter.render(self._graphics, capture_fbo,
                                     dst_w, dst_h,
                                     self.channel_mode, self.highlight_hdr)
        self._graphics.set_viewport(0, 0, renderer._viewport_w, renderer._viewport_h)
        if renderer._clip_stack:
            renderer._graphics.enable_scissor(*renderer._clip_stack[-1])


class _FramegraphDebuggerHandle:
    """Handle returned by show_framegraph_debugger() for external update calls."""

    def __init__(self) -> None:
        self.dialog: Dialog | None = None
        self.visible: bool = False

        # State
        self._core = None
        self._graphics: GraphicsBackend | None = None
        self._rendering_controller = None

        self._current_viewport = None
        self._viewports_list: list[tuple[object, str]] = []

        self._mode: str = "inside"  # "inside" or "between"
        self._selected_pass: str | None = None
        self._selected_symbol: str | None = None
        self._debug_source_res: str = ""
        self._debug_paused: bool = False
        self._channel_mode: int = 0
        self._highlight_hdr: bool = False

        self._frame_debugger_pass = None
        self._connected_pipeline = None

        # Widgets (set during build)
        self._viewport_combo: ComboBox | None = None
        self._mode_combo: ComboBox | None = None
        self._pass_combo: ComboBox | None = None
        self._symbol_combo: ComboBox | None = None
        self._resource_combo: ComboBox | None = None
        self._channel_combo: ComboBox | None = None
        self._pause_check: Checkbox | None = None
        self._timing_label: Label | None = None
        self._pass_json: TextArea | None = None
        self._fbo_info_label: Label | None = None
        self._render_stats_label: Label | None = None
        self._writer_pass_label: Label | None = None
        self._hdr_stats_label: Label | None = None
        self._pipeline_text: TextArea | None = None
        self._status_label: Label | None = None
        self._preview: CapturePreviewWidget | None = None

        self._inside_panel: VStack | None = None
        self._between_panel: VStack | None = None

        self._updating: bool = False

    # ---- Pipeline access ----

    def _get_current_pipeline(self):
        if self._current_viewport is None:
            return None
        managed_by = self._current_viewport.managed_by_scene_pipeline
        if managed_by and self._current_viewport.scene is not None:
            return self._current_viewport.scene.get_pipeline(managed_by)
        return self._current_viewport.pipeline

    def _get_fbos(self) -> dict:
        pipeline = self._get_current_pipeline()
        if pipeline is None:
            return {}
        result = {}
        for key in pipeline.get_fbo_keys():
            fbo = pipeline.get_fbo(key)
            if fbo is not None:
                result[key] = fbo
        return result

    # ---- Connection management ----

    def _disconnect(self) -> None:
        pipeline = self._connected_pipeline or self._get_current_pipeline()

        if pipeline is not None:
            pipeline.remove_passes_by_name("FrameDebugger")

        self._frame_debugger_pass = None

        if pipeline is not None:
            for p in pipeline.passes:
                try:
                    p.set_debug_internal_point("")
                    p.clear_debug_capture()
                except AttributeError:
                    pass

        self._connected_pipeline = None
        self._core.capture.reset_capture()

    def _connect(self) -> None:
        pipeline = self._get_current_pipeline()
        if pipeline is None:
            return

        self._connected_pipeline = pipeline

        if self._mode == "between":
            if not self._debug_source_res:
                return

            from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

            paused_ref = self
            source_ref = self

            def get_source():
                if paused_ref._debug_paused:
                    return None
                return source_ref._debug_source_res

            self._frame_debugger_pass = FrameDebuggerPass(
                get_source_res=get_source,
                pass_name="FrameDebugger",
            )
            self._frame_debugger_pass.set_capture(self._core.capture)
            pipeline.add_pass(self._frame_debugger_pass)
            log.info(f"[FrameDebugger] Connected: between mode, resource='{self._debug_source_res}'")

        elif self._mode == "inside":
            if not self._selected_pass or not self._selected_symbol:
                return

            for p in pipeline.passes:
                if p.pass_name == self._selected_pass:
                    p.set_debug_internal_point(self._selected_symbol)
                    p.set_debug_capture(self._core.capture)
                    log.info(f"[FrameDebugger] Connected: inside mode, pass='{self._selected_pass}', symbol='{self._selected_symbol}'")
                    return

            log.warn(f"[FrameDebugger] Pass '{self._selected_pass}' not found")

    def _reconnect(self) -> None:
        self._disconnect()
        self._connect()

    # ---- Schedule building ----

    def _build_schedule(self, exclude_debugger: bool = False) -> list:
        pipeline = self._get_current_pipeline()
        if pipeline is None:
            return []

        from termin.visualization.render.framegraph.core import FrameGraph
        from termin.visualization.render.framegraph.passes.base import RenderFramePass
        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

        passes = pipeline.passes
        if exclude_debugger:
            passes = [p for p in passes if not isinstance(p, FrameDebuggerPass)]

        for render_pass in passes:
            if isinstance(render_pass, RenderFramePass):
                render_pass.required_resources()

        graph = FrameGraph(passes)
        return graph.build_schedule()

    # ---- List updates ----

    def _update_viewport_list(self) -> None:
        if self._rendering_controller is None:
            return
        self._viewports_list = self._rendering_controller.get_all_viewports_info()
        self._updating = True
        self._viewport_combo.clear()
        for _, label in self._viewports_list:
            self._viewport_combo.add_item(label)
        if self._viewports_list:
            self._viewport_combo.selected_index = 0
            self._current_viewport = self._viewports_list[0][0]
        self._updating = False

    def _update_resource_list(self) -> None:
        self._update_pipeline_info()

        schedule = self._build_schedule(exclude_debugger=True)

        if schedule:
            written: set[str] = set()
            for p in schedule:
                written.update(p.writes)
            written.discard("DISPLAY")

            read_only: list[str] = []
            for p in schedule:
                for r in sorted(p.reads):
                    if r not in written and r != "DISPLAY" and r not in read_only:
                        read_only.append(r)

            seen: set[str] = set()
            write_order: list[str] = []
            for p in schedule:
                for w in sorted(p.writes):
                    if w not in seen and w != "DISPLAY":
                        seen.add(w)
                        write_order.append(w)

            names = read_only + write_order
        else:
            names = sorted(self._get_fbos().keys())

        current_items = [self._resource_combo.item_text(i)
                         for i in range(self._resource_combo.item_count)]
        if current_items == names:
            return

        current = self._resource_combo.selected_text
        self._updating = True
        self._resource_combo.clear()
        for name in names:
            self._resource_combo.add_item(name)
        if current and current in names:
            self._resource_combo.selected_index = names.index(current)
        self._updating = False

    def _update_passes_list(self) -> None:
        previous_pass = self._selected_pass

        passes_info: list[tuple[str, bool]] = []
        pipeline = self._get_current_pipeline()
        if pipeline is not None:
            from termin.visualization.render.framegraph.passes.shadow import ShadowPass
            for p in pipeline.passes:
                if isinstance(p, ShadowPass):
                    has_symbols = False
                else:
                    symbols = p.get_internal_symbols()
                    has_symbols = len(symbols) > 0
                passes_info.append((p.pass_name, has_symbols))

        new_items = [(f"{name} *" if has_sym else name, name)
                     for name, has_sym in passes_info]

        current_items = [(self._pass_combo.item_text(i),
                          self._pass_combo.item_text(i).rstrip(" *"))
                         for i in range(self._pass_combo.item_count)]
        if current_items == new_items:
            return

        self._updating = True
        self._pass_combo.clear()
        selected_index = -1
        for index, (display_name, pass_name) in enumerate(new_items):
            self._pass_combo.add_item(display_name)
            if previous_pass is not None and pass_name == previous_pass:
                selected_index = index

        if previous_pass is not None and selected_index < 0:
            self._pass_combo.selected_index = -1
            self._updating = False
            return

        if previous_pass is None:
            if self._pass_combo.item_count > 0:
                self._pass_combo.selected_index = 0
                self._selected_pass = self._pass_name_from_display(
                    self._pass_combo.item_text(0))
                self._updating = False
                self._update_symbols_list()
            else:
                self._updating = False
            return

        if selected_index >= 0:
            self._pass_combo.selected_index = selected_index
        self._updating = False
        self._update_symbols_list()

    def _pass_name_from_display(self, display_name: str) -> str:
        if display_name.endswith(" *"):
            return display_name[:-2]
        return display_name

    def _update_symbols_list(self) -> None:
        previous_symbol = self._selected_symbol
        symbols: list[str] = []

        if self._selected_pass:
            pipeline = self._get_current_pipeline()
            if pipeline is not None:
                for p in pipeline.passes:
                    if p.pass_name == self._selected_pass:
                        symbols = list(p.get_internal_symbols())
                        break

        current_items = [self._symbol_combo.item_text(i)
                         for i in range(self._symbol_combo.item_count)]
        if current_items == symbols:
            return

        self._updating = True
        self._symbol_combo.clear()
        selected_index = -1
        for index, sym in enumerate(symbols):
            self._symbol_combo.add_item(sym)
            if previous_symbol is not None and sym == previous_symbol:
                selected_index = index

        if previous_symbol is not None and selected_index < 0:
            self._symbol_combo.selected_index = -1
        elif selected_index >= 0:
            self._symbol_combo.selected_index = selected_index
        self._updating = False

    # ---- Info updates ----

    def _update_fbo_info(self) -> None:
        fbos = self._get_fbos()
        resource_name = self._debug_source_res

        resource = fbos.get(resource_name) if fbos else None
        if resource is None:
            self._fbo_info_label.text = f"Resource '{resource_name}': not found"
            return

        from termin.visualization.render.framegraph.resource import (
            SingleFBO,
            ShadowMapArrayResource,
        )
        from termin.graphics import FramebufferHandle

        parts = [resource_name]

        if isinstance(resource, ShadowMapArrayResource):
            parts.append(f"ShadowMapArray ({len(resource)} entries)")
            if len(resource) > 0:
                entry = resource[0]
                fbo = entry.fbo
                if fbo is not None:
                    w, h = fbo.get_size()
                    parts.append(f"{w}x{h}")
        elif isinstance(resource, SingleFBO):
            fbo = resource._fbo
            if fbo is not None:
                w, h = fbo.get_size()
                samples = fbo.get_samples()
                is_msaa = fbo.is_msaa()
                fmt = fbo.get_format()
                parts.append(f"SingleFBO {w}x{h}")
                parts.append(f"fmt={fmt}")
                if is_msaa:
                    parts.append(f"MSAA={samples}x")
                parts.append(f"id={fbo.get_fbo_id()}")
        elif isinstance(resource, FramebufferHandle):
            w, h = resource.get_size()
            samples = resource.get_samples()
            is_msaa = resource.is_msaa()
            fmt = resource.get_format()
            parts.append(f"FBH {w}x{h}")
            parts.append(f"fmt={fmt}")
            if is_msaa:
                parts.append(f"MSAA={samples}x")
            parts.append(f"id={resource.get_fbo_id()}")
        else:
            parts.append(type(resource).__name__)

        self._fbo_info_label.text = " | ".join(parts)

    def _update_writer_pass_label(self) -> None:
        resource_name = self._debug_source_res
        if not resource_name:
            self._writer_pass_label.text = ""
            return

        schedule = self._build_schedule(exclude_debugger=True)
        writer_pass = None
        for p in schedule:
            if resource_name in p.writes:
                writer_pass = p.pass_name
                break

        if writer_pass:
            self._writer_pass_label.text = f"Writer: {writer_pass}"
        else:
            self._writer_pass_label.text = "(read-only)"

    def _update_pass_serialization(self) -> None:
        if self._selected_pass is None:
            self._pass_json.text = ""
            return

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            self._pass_json.text = "<no pipeline>"
            return

        for p in pipeline.passes:
            if p.pass_name == self._selected_pass:
                try:
                    data = p.serialize()
                    self._pass_json.text = json.dumps(data, indent=2, ensure_ascii=False)
                except Exception as e:
                    log.error(f"[FrameDebugger] serialize failed: {e}")
                    self._pass_json.text = f"<error: {e}>"
                return

        self._pass_json.text = f"<pass '{self._selected_pass}' not found>"

    def _update_timing_label(self) -> None:
        if self._selected_pass is None or self._selected_symbol is None:
            self._timing_label.text = ""
            return

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            self._timing_label.text = ""
            return

        for p in pipeline.passes:
            if p.pass_name == self._selected_pass:
                timings = p.get_internal_symbols_with_timing()
                for t in timings:
                    if t.name == self._selected_symbol:
                        gpu_str = f"{t.gpu_time_ms:.3f}ms" if t.gpu_time_ms >= 0 else "pending..."
                        self._timing_label.text = f"CPU: {t.cpu_time_ms:.3f}ms | GPU: {gpu_str}"
                        return
                break

        self._timing_label.text = "Timing: no data"

    def _update_pipeline_info(self) -> None:
        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

        schedule = self._build_schedule()
        if not schedule:
            self._pipeline_text.text = "(pipeline empty)"
            return

        current_resource = self._debug_source_res
        lines = []
        for p in schedule:
            reads_str = ", ".join(sorted(p.reads)) if p.reads else "{}"
            writes_str = ", ".join(sorted(p.writes)) if p.writes else "{}"
            line = f"{p.pass_name}: {{{reads_str}}} -> {{{writes_str}}}"

            if isinstance(p, FrameDebuggerPass):
                line = f">>> {line}"
            elif current_resource and current_resource in p.writes:
                line = f"*** {line}"
            else:
                line = f"    {line}"

            lines.append(line)

        self._pipeline_text.text = "\n".join(lines)

    def _update_render_stats(self) -> None:
        from termin.visualization.render.manager import RenderingManager
        rm = RenderingManager.instance()
        stats = rm.get_render_stats()

        parts = []
        parts.append(f"Scenes: {stats['attached_scenes']}")
        parts.append(f"Pipelines: {stats['scene_pipelines']}")
        parts.append(f"Unmanaged: {stats['unmanaged_viewports']}")

        details = []
        if stats["scene_names"]:
            details.append(f"[{', '.join(stats['scene_names'])}]")
        if stats["pipeline_names"]:
            details.append(f"({', '.join(stats['pipeline_names'])})")

        text = " | ".join(parts)
        if details:
            text += "  " + " ".join(details)
        self._render_stats_label.text = text

    # ---- Present / depth ----

    def _update_preview_state(self) -> None:
        if self._preview is None:
            return
        has_capture = self._core.capture.has_capture()
        self._preview.has_content = has_capture
        self._preview.channel_mode = self._channel_mode
        self._preview.highlight_hdr = self._highlight_hdr

    def _on_refresh_depth(self) -> None:
        capture_fbo = self._core.capture_fbo
        if capture_fbo is None:
            self._status_label.text = "No capture for depth"
            return
        try:
            data_bytes, w, h = self._core.presenter.read_depth_normalized_with_size(
                self._graphics, capture_fbo
            )
            if not data_bytes or w == 0 or h == 0:
                self._status_label.text = "No depth data"
            else:
                self._status_label.text = f"Depth: {w}x{h} read OK"
        except Exception as e:
            log.error(f"[FrameDebugger] depth read failed: {e}")
            self._status_label.text = f"Depth error: {e}"

    # ---- Update (called from editor per frame) ----

    def update(self) -> None:
        if not self.visible:
            return

        self._update_resource_list()
        if self._mode == "inside":
            self._update_passes_list()
            self._update_timing_label()
        self._update_fbo_info()
        self._update_preview_state()

    def close(self) -> None:
        self._disconnect()
        self.visible = False


def show_framegraph_debugger(ui, graphics, rendering_controller) -> _FramegraphDebuggerHandle:
    """Create and show the Framegraph Debugger dialog. Returns handle for updates."""

    from termin._native.editor import FrameGraphDebuggerCore

    handle = _FramegraphDebuggerHandle()
    handle._graphics = graphics
    handle._rendering_controller = rendering_controller
    handle._core = FrameGraphDebuggerCore()

    # ---- Build UI ----
    # Layout matches Qt6 original:
    #   VStack (main)
    #   ├── HStack (top_area)
    #   │   ├── VStack (settings)
    #   │   └── VStack (pipeline schedule)
    #   └── HStack (viewer_area, stretch)
    #       ├── CapturePreviewWidget (stretch)
    #       └── VStack (depth)

    content = VStack()
    content.spacing = 6

    # ============ Top area: settings (left) + pipeline schedule (right) ============

    top_area = HStack()
    top_area.spacing = 8
    top_area.preferred_height = px(320)

    # --- Left: settings ---
    settings = VStack()
    settings.spacing = 4
    settings.stretch = True

    # Viewport selection
    vp_row = HStack()
    vp_row.spacing = 4
    vp_label = Label()
    vp_label.text = "Viewport:"
    vp_row.add_child(vp_label)
    viewport_combo = ComboBox()
    viewport_combo.stretch = True
    handle._viewport_combo = viewport_combo
    vp_row.add_child(viewport_combo)
    settings.add_child(vp_row)

    # Render stats
    stats_row = HStack()
    stats_row.spacing = 4
    render_stats_label = Label()
    render_stats_label.text = ""
    handle._render_stats_label = render_stats_label
    stats_row.add_child(render_stats_label)
    refresh_stats_btn = Button()
    refresh_stats_btn.text = "Refresh"
    refresh_stats_btn.padding = 4
    stats_row.add_child(refresh_stats_btn)
    settings.add_child(stats_row)

    # Mode selection
    mode_row = HStack()
    mode_row.spacing = 4
    mode_label = Label()
    mode_label.text = "Mode:"
    mode_row.add_child(mode_label)
    mode_combo = ComboBox()
    mode_combo.items = ["Passes", "Resources"]
    mode_combo.selected_index = 0
    mode_combo.preferred_width = px(120)
    handle._mode_combo = mode_combo
    mode_row.add_child(mode_combo)
    settings.add_child(mode_row)

    # --- "Resources" panel (initially hidden) ---
    between_panel = VStack()
    between_panel.spacing = 4
    between_panel.visible = False
    handle._between_panel = between_panel

    res_row = HStack()
    res_row.spacing = 4
    r_label = Label()
    r_label.text = "Resource:"
    res_row.add_child(r_label)
    resource_combo = ComboBox()
    resource_combo.stretch = True
    handle._resource_combo = resource_combo
    res_row.add_child(resource_combo)
    between_panel.add_child(res_row)

    writer_pass_label = Label()
    writer_pass_label.text = ""
    handle._writer_pass_label = writer_pass_label
    between_panel.add_child(writer_pass_label)

    hdr_row = HStack()
    hdr_row.spacing = 4
    hdr_highlight_check = Checkbox()
    hdr_highlight_check.text = "Highlight HDR"
    hdr_row.add_child(hdr_highlight_check)
    analyze_btn = Button()
    analyze_btn.text = "Analyze"
    analyze_btn.padding = 4
    hdr_row.add_child(analyze_btn)
    between_panel.add_child(hdr_row)

    hdr_stats_label = Label()
    hdr_stats_label.text = ""
    handle._hdr_stats_label = hdr_stats_label
    between_panel.add_child(hdr_stats_label)

    settings.add_child(between_panel)

    # --- "Passes" panel (shown initially) ---
    inside_panel = VStack()
    inside_panel.spacing = 4
    handle._inside_panel = inside_panel

    pass_row = HStack()
    pass_row.spacing = 4
    p_label = Label()
    p_label.text = "Pass:"
    pass_row.add_child(p_label)
    pass_combo = ComboBox()
    pass_combo.stretch = True
    handle._pass_combo = pass_combo
    pass_row.add_child(pass_combo)
    inside_panel.add_child(pass_row)

    sym_row = HStack()
    sym_row.spacing = 4
    s_label = Label()
    s_label.text = "Symbol:"
    sym_row.add_child(s_label)
    symbol_combo = ComboBox()
    symbol_combo.stretch = True
    handle._symbol_combo = symbol_combo
    sym_row.add_child(symbol_combo)
    inside_panel.add_child(sym_row)

    timing_label = Label()
    timing_label.text = ""
    handle._timing_label = timing_label
    inside_panel.add_child(timing_label)

    pass_json = TextArea()
    pass_json.read_only = True
    pass_json.word_wrap = False
    pass_json.stretch = True
    pass_json.placeholder = "Pass JSON"
    handle._pass_json = pass_json
    inside_panel.add_child(pass_json)

    settings.add_child(inside_panel)

    # FBO info
    fbo_info_label = Label()
    fbo_info_label.text = ""
    handle._fbo_info_label = fbo_info_label
    settings.add_child(fbo_info_label)

    # Pause + channel controls
    controls_row = HStack()
    controls_row.spacing = 8
    pause_check = Checkbox()
    pause_check.text = "Pause"
    handle._pause_check = pause_check
    controls_row.add_child(pause_check)
    ch_label = Label()
    ch_label.text = "Channel:"
    controls_row.add_child(ch_label)
    channel_combo = ComboBox()
    channel_combo.items = ["RGB", "R", "G", "B", "A"]
    channel_combo.selected_index = 0
    channel_combo.preferred_width = px(70)
    handle._channel_combo = channel_combo
    controls_row.add_child(channel_combo)
    settings.add_child(controls_row)

    top_area.add_child(settings)

    # --- Right: pipeline schedule ---
    pipeline_panel = VStack()
    pipeline_panel.spacing = 4
    pipeline_panel.stretch = True

    sched_title = Label()
    sched_title.text = "Pipeline Schedule"
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

    # ============ Bottom area: viewer (left) + depth (right) ============

    viewer_area = HStack()
    viewer_area.spacing = 8
    viewer_area.stretch = True

    # Capture preview (takes most space)
    preview = CapturePreviewWidget()
    preview.stretch = True
    preview._core = handle._core
    preview._graphics = graphics
    handle._preview = preview
    viewer_area.add_child(preview)

    # Depth panel
    depth_panel = VStack()
    depth_panel.spacing = 4
    depth_panel.preferred_width = px(300)

    depth_header = HStack()
    depth_header.spacing = 4
    depth_title = Label()
    depth_title.text = "Depth Buffer"
    depth_header.add_child(depth_title)
    refresh_depth_btn = Button()
    refresh_depth_btn.text = "Refresh"
    refresh_depth_btn.padding = 4
    depth_header.add_child(refresh_depth_btn)
    depth_panel.add_child(depth_header)

    status_label = Label()
    status_label.text = ""
    handle._status_label = status_label
    depth_panel.add_child(status_label)

    viewer_area.add_child(depth_panel)
    content.add_child(viewer_area)

    # ---- Event handlers (closures) ----

    def on_viewport_changed(idx, text):
        if handle._updating:
            return
        if idx < 0 or idx >= len(handle._viewports_list):
            handle._current_viewport = None
        else:
            handle._current_viewport = handle._viewports_list[idx][0]
        handle._update_resource_list()
        handle._update_passes_list()
        _sync_initial_resource()
        handle._reconnect()

    def on_mode_changed(idx, text):
        if handle._updating:
            return
        if idx == 0:
            handle._mode = "inside"
            handle._inside_panel.visible = True
            handle._between_panel.visible = False
            handle._update_passes_list()
            handle._update_pass_serialization()
        else:
            handle._mode = "between"
            handle._inside_panel.visible = False
            handle._between_panel.visible = True
        handle._reconnect()

    def on_pass_changed(idx, text):
        if handle._updating:
            return
        if idx < 0:
            return
        handle._selected_pass = handle._pass_name_from_display(text)
        handle._selected_symbol = None
        handle._update_symbols_list()
        handle._update_pass_serialization()
        # Auto-select last symbol
        if handle._symbol_combo.item_count > 0:
            last = handle._symbol_combo.item_count - 1
            handle._updating = True
            handle._symbol_combo.selected_index = last
            handle._updating = False
            handle._selected_symbol = handle._symbol_combo.item_text(last)
        if handle._selected_symbol:
            handle._update_timing_label()
        else:
            handle._timing_label.text = ""
        handle._reconnect()

    def on_symbol_changed(idx, text):
        if handle._updating:
            return
        if not text or handle._selected_pass is None:
            return
        handle._selected_symbol = text
        handle._update_timing_label()
        handle._reconnect()

    def on_resource_changed(idx, text):
        if handle._updating:
            return
        if not text:
            return
        handle._debug_source_res = text
        handle._update_fbo_info()
        handle._update_writer_pass_label()
        handle._update_pipeline_info()
        handle._hdr_stats_label.text = ""
        handle._reconnect()

    def on_pause_changed(checked):
        handle._debug_paused = checked
        handle._reconnect()

    def on_channel_changed(idx, text):
        if handle._updating:
            return
        handle._channel_mode = idx
        if handle._preview is not None:
            handle._preview.channel_mode = idx

    def on_hdr_highlight_changed(checked):
        handle._highlight_hdr = checked
        if handle._preview is not None:
            handle._preview.highlight_hdr = checked

    def on_analyze_hdr():
        capture_fbo = handle._core.capture_fbo
        if capture_fbo is None:
            handle._hdr_stats_label.text = "No capture available"
            return
        try:
            stats = handle._core.presenter.compute_hdr_stats(
                handle._graphics, capture_fbo)
            lines = []
            lines.append(f"R: {stats.min_r:.3f} - {stats.max_r:.3f} (avg: {stats.avg_r:.3f})")
            lines.append(f"G: {stats.min_g:.3f} - {stats.max_g:.3f} (avg: {stats.avg_g:.3f})")
            lines.append(f"B: {stats.min_b:.3f} - {stats.max_b:.3f} (avg: {stats.avg_b:.3f})")
            lines.append(f"Max: {stats.max_value:.3f}")
            if stats.hdr_percent > 0:
                lines.append(f"HDR pixels: {stats.hdr_pixel_count:,} ({stats.hdr_percent:.2f}%)")
            else:
                lines.append("HDR pixels: 0 (0%)")
            handle._hdr_stats_label.text = "\n".join(lines)
        except Exception as e:
            log.error(f"[FrameDebugger] HDR analyze failed: {e}")
            handle._hdr_stats_label.text = f"Error: {e}"

    def on_refresh_depth():
        handle._on_refresh_depth()

    def on_refresh_stats():
        handle._update_render_stats()

    def _sync_initial_resource():
        if handle._resource_combo.item_count == 0:
            return
        handle._updating = True
        handle._resource_combo.selected_index = 0
        handle._updating = False
        first_resource = handle._resource_combo.selected_text
        if first_resource:
            handle._debug_source_res = first_resource
            handle._update_fbo_info()
            handle._update_writer_pass_label()
            handle._update_pipeline_info()

    # Wire callbacks
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

    # ---- Dialog ----

    dialog = Dialog()
    dialog.title = "Framegraph Debugger"
    dialog.content = content
    dialog.buttons = ["Close"]
    dialog.cancel_button = "Close"
    dialog.preferred_width = px(950)
    dialog.preferred_height = px(700)

    def on_dialog_result(btn):
        handle.close()

    dialog.on_result = on_dialog_result
    handle.dialog = dialog
    handle.visible = True

    dialog.show(ui, windowed=True)

    # Initial population
    handle._update_viewport_list()
    handle._update_resource_list()
    handle._update_passes_list()
    handle._update_render_stats()
    _sync_initial_resource()
    handle._reconnect()

    return handle
