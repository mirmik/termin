"""FramegraphDebuggerModel — UI-agnostic state and business logic for the framegraph debugger.

Both Qt (``editor/framegraph_debugger.py``) and tcgui (``editor_tcgui/dialogs/framegraph_debugger.py``)
views subscribe to this model and convert its state snapshots into their own
widget updates. Pipeline connection (``FrameDebuggerPass`` lifecycle, per-pass
``set_debug_internal_point``) is owned here; views never touch the pipeline
directly.

Signals:

- ``lists_changed``      fires after viewport/resource/pass/symbols lists rebuild
- ``selection_changed``  fires when mode / selected pass / symbol / resource changes
- ``info_changed``       fires when any derived info text changed (fbo_info, writer, pipeline, pass_json, timing, render_stats)
- ``capture_updated``    fires when a new capture is ready to display (per-frame)
- ``preview_params_changed`` fires when channel_mode / highlight_hdr toggled
- ``hdr_stats_changed``  fires after ``analyze_hdr()`` with the formatted text

Views re-read model state via properties on signal emit.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from tcbase import log

from termin.editor_core.signal import Signal

if TYPE_CHECKING:
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.render.framegraph import RenderPipeline


class FramegraphDebuggerModel:
    def __init__(self, rendering_controller, core, on_request_update: Callable[[], None] | None = None):
        self._rendering_controller = rendering_controller
        self._core = core
        self._on_request_update = on_request_update

        self._current_viewport = None
        self._viewports_list: list[tuple[object, str]] = []

        self._mode: str = "inside"
        self._selected_pass: str | None = None
        self._selected_symbol: str | None = None
        self._debug_source_res: str = ""
        self._debug_paused: bool = False
        self._channel_mode: int = 0
        self._highlight_hdr: bool = False

        self._frame_debugger_pass = None
        self._connected_pipeline = None

        self.lists_changed = Signal()
        self.selection_changed = Signal()
        self.info_changed = Signal()
        self.capture_updated = Signal()
        self.preview_params_changed = Signal()
        self.hdr_stats_changed = Signal()

    # ------------------------------------------------------------------
    # Public read-only state (views pull these after signal emit)
    # ------------------------------------------------------------------

    @property
    def core(self):
        return self._core

    @property
    def current_viewport(self):
        return self._current_viewport

    @property
    def viewports(self) -> list[tuple[object, str]]:
        return list(self._viewports_list)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def selected_pass(self) -> str | None:
        return self._selected_pass

    @property
    def selected_symbol(self) -> str | None:
        return self._selected_symbol

    @property
    def debug_source_res(self) -> str:
        return self._debug_source_res

    @property
    def debug_paused(self) -> bool:
        return self._debug_paused

    @property
    def channel_mode(self) -> int:
        return self._channel_mode

    @property
    def highlight_hdr(self) -> bool:
        return self._highlight_hdr

    # ------------------------------------------------------------------
    # Pipeline access
    # ------------------------------------------------------------------

    def get_current_pipeline(self) -> "RenderPipeline | None":
        if self._current_viewport is None:
            return None
        managed_by = self._current_viewport.managed_by_scene_pipeline
        if managed_by and self._current_viewport.scene is not None:
            from termin.visualization.core.scene import scene_render_mount
            return scene_render_mount(self._current_viewport.scene).get_pipeline(managed_by)
        return self._current_viewport.pipeline

    def get_fbos(self) -> dict:
        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return {}
        result = {}
        for key in pipeline.get_fbo_keys():
            fbo = pipeline.get_fbo(key)
            if fbo is not None:
                result[key] = fbo
        return result

    # ------------------------------------------------------------------
    # Refresh list contents (from rendering_controller / pipeline state)
    # ------------------------------------------------------------------

    def refresh_viewports(self) -> None:
        if self._rendering_controller is None:
            self._viewports_list = []
        else:
            self._viewports_list = list(self._rendering_controller.get_all_viewports_info())
        if self._viewports_list and self._current_viewport is None:
            self._current_viewport = self._viewports_list[0][0]
        self.lists_changed.emit(self)

    def get_resources(self) -> list[str]:
        """FBO resource names available in the current pipeline, ordered so
        read-only resources come first, followed by written resources in
        schedule order. ``DISPLAY`` is excluded."""
        schedule = self._build_schedule(exclude_debugger=True)
        if not schedule:
            return sorted(self.get_fbos().keys())

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
        return read_only + write_order

    def get_passes(self) -> list[tuple[str, bool]]:
        """List of (pass_name, has_internal_symbols) from current pipeline,
        with the debugger pass filtered out. ShadowPass is treated as having
        no symbols (matches Qt behaviour)."""
        from termin.visualization.render.framegraph.passes.shadow import ShadowPass

        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return []
        result: list[tuple[str, bool]] = []
        for p in pipeline.passes:
            if p.pass_name == "FrameDebugger":
                continue
            if isinstance(p, ShadowPass):
                has_syms = False
            else:
                try:
                    has_syms = bool(p.get_internal_symbols())
                except AttributeError:
                    has_syms = False
            result.append((p.pass_name, has_syms))
        return result

    def get_symbols(self) -> list[str]:
        pipeline = self.get_current_pipeline()
        if pipeline is None or self._selected_pass is None:
            return []
        for p in pipeline.passes:
            if p.pass_name != self._selected_pass:
                continue
            try:
                return list(p.get_internal_symbols())
            except AttributeError:
                return []
        return []

    # ------------------------------------------------------------------
    # Info-text formatters (view displays verbatim)
    # ------------------------------------------------------------------

    def format_fbo_info(self) -> str:
        """Info line for the currently-selected source resource.

        ``RenderPipeline.get_fbo(key)`` returns a dict (see
        render_pipeline_bindings.cpp); ``ShadowMapArrayResource`` is a
        separate dataclass-like type — check its type first.
        """
        from termin.visualization.render.framegraph.resource import ShadowMapArrayResource

        fbos = self.get_fbos()
        resource_name = self._debug_source_res
        resource = fbos.get(resource_name) if fbos else None
        if resource is None:
            return f"Ресурс '{resource_name}': не найден"

        parts = [f"<b>{resource_name}</b>"]
        if isinstance(resource, ShadowMapArrayResource):
            parts.append(f"Тип: ShadowMapArray ({len(resource)} entries)")
            if len(resource) > 0:
                fbo = resource[0].fbo
                if fbo is not None:
                    w, h = fbo.get_size()
                    parts.append(f"Размер: {w}×{h}")
        elif isinstance(resource, dict):
            w = int(resource.get("width", 0))
            h = int(resource.get("height", 0))
            parts.append(f"Размер: {w}×{h}")
            parts.append(f"fmt={resource.get('color_format', 0)}")
            if resource.get("has_depth", False):
                parts.append(f"depth_fmt={resource.get('depth_format', 0)}")
            samples = int(resource.get("samples", 1))
            if samples > 1:
                parts.append(f"MSAA={samples}x")
            handle = resource.get("color_native_handle", 0)
            if handle:
                parts.append(f"id={handle}")
        else:
            parts.append(f"Тип: {type(resource).__name__}")
        return " | ".join(parts)

    def format_writer_pass(self) -> str:
        resource_name = self._debug_source_res
        if not resource_name:
            return ""
        schedule = self._build_schedule(exclude_debugger=True)
        for p in schedule:
            if resource_name in p.writes:
                return f"← {p.pass_name}"
        return "(read-only)"

    def format_pipeline_info(self) -> str:
        """HTML pipeline schedule with FrameDebugger highlighted in orange
        and the writer of the current debug-source resource in green."""
        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

        schedule = self._build_schedule(exclude_debugger=False)
        if not schedule:
            return "<i>Pipeline пуст</i>"

        current_resource = self._debug_source_res
        lines: list[str] = []
        for p in schedule:
            reads_str = ", ".join(sorted(p.reads)) if p.reads else "∅"
            writes_str = ", ".join(sorted(p.writes)) if p.writes else "∅"
            line = f"{p.pass_name}: {{{reads_str}}} → {{{writes_str}}}"
            if isinstance(p, FrameDebuggerPass):
                line = f"<span style='color: #ffb86c;'>► {line}</span>"
            elif current_resource and current_resource in p.writes:
                line = f"<span style='color: #50fa7b; font-weight: bold;'>● {line}</span>"
            lines.append(line)
        return "<pre>" + "<br>".join(lines) + "</pre>"

    def format_pass_json(self) -> str:
        if self._selected_pass is None:
            return ""
        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return "<no pipeline>"
        for p in pipeline.passes:
            if p.pass_name == self._selected_pass:
                try:
                    return json.dumps(p.serialize(), indent=2, ensure_ascii=False)
                except Exception as e:
                    return f"<error: {e}>"
        return f"<pass '{self._selected_pass}' not found>"

    def format_timing(self) -> str:
        if self._selected_pass is None or self._selected_symbol is None:
            return ""
        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return ""
        for p in pipeline.passes:
            if p.pass_name != self._selected_pass:
                continue
            try:
                timings = p.get_internal_symbols_with_timing()
            except AttributeError:
                return ""
            for t in timings:
                if t.name == self._selected_symbol:
                    gpu_str = f"{t.gpu_time_ms:.3f}ms" if t.gpu_time_ms >= 0 else "pending..."
                    return f"CPU: {t.cpu_time_ms:.3f}ms | GPU: {gpu_str}"
            return "Timing: no data"
        return ""

    def format_render_stats(self) -> str:
        from termin.visualization.render.manager import RenderingManager
        stats = RenderingManager.instance().get_render_stats()
        parts = [
            f"Scenes: {stats['attached_scenes']}",
            f"Pipelines: {stats['scene_pipelines']}",
            f"Unmanaged: {stats['unmanaged_viewports']}",
        ]
        details: list[str] = []
        if stats["scene_names"]:
            details.append(f"[{', '.join(stats['scene_names'])}]")
        if stats["pipeline_names"]:
            details.append(f"({', '.join(stats['pipeline_names'])})")
        text = " | ".join(parts)
        if details:
            text += "  " + " ".join(details)
        return text

    # ------------------------------------------------------------------
    # Mutations (view calls these; they emit signals)
    # ------------------------------------------------------------------

    def set_viewport_by_index(self, index: int) -> None:
        if index < 0 or index >= len(self._viewports_list):
            self._current_viewport = None
        else:
            self._current_viewport = self._viewports_list[index][0]
        self.lists_changed.emit(self)
        self._reconnect()
        self.info_changed.emit(self)

    def set_mode(self, mode: str) -> None:
        if mode not in ("inside", "between") or mode == self._mode:
            return
        self._mode = mode
        self.selection_changed.emit(self)
        self._reconnect()
        self.info_changed.emit(self)

    def set_selected_pass(self, pass_name: str | None) -> None:
        if pass_name == self._selected_pass:
            return
        self._selected_pass = pass_name
        # Auto-select last symbol in the new pass if any
        symbols = self.get_symbols()
        self._selected_symbol = symbols[-1] if symbols else None
        self.lists_changed.emit(self)
        self.selection_changed.emit(self)
        self._reconnect()
        self.info_changed.emit(self)

    def set_selected_symbol(self, symbol: str | None) -> None:
        if symbol == self._selected_symbol:
            return
        self._selected_symbol = symbol
        self.selection_changed.emit(self)
        self._reconnect()
        self.info_changed.emit(self)

    def set_source_resource(self, name: str) -> None:
        if name == self._debug_source_res:
            return
        self._debug_source_res = name
        self.selection_changed.emit(self)
        self._reconnect()
        self.info_changed.emit(self)

    def set_paused(self, paused: bool) -> None:
        self._debug_paused = bool(paused)

    def set_channel_mode(self, mode: int) -> None:
        self._channel_mode = int(mode)
        self.preview_params_changed.emit(self)
        if self._on_request_update is not None:
            self._on_request_update()

    def set_highlight_hdr(self, enabled: bool) -> None:
        self._highlight_hdr = bool(enabled)
        self.preview_params_changed.emit(self)
        if self._on_request_update is not None:
            self._on_request_update()

    def refresh_render_stats(self) -> None:
        self.info_changed.emit(self)

    def analyze_hdr(self) -> str:
        capture_tex = self._core.capture_tex
        if not capture_tex:
            text = "No capture available"
            self.hdr_stats_changed.emit(text)
            return text

        from termin.visualization.render.manager import RenderingManager
        render_engine = RenderingManager.instance().render_engine
        if render_engine is None:
            text = "No render engine"
            self.hdr_stats_changed.emit(text)
            return text
        render_engine.ensure_tgfx2()
        device = render_engine.tgfx2_device
        if device is None:
            text = "No tgfx2 device"
            self.hdr_stats_changed.emit(text)
            return text

        stats = self._core.presenter.compute_hdr_stats(device, capture_tex)
        lines = [
            f"<b>R:</b> {stats.min_r:.3f} - {stats.max_r:.3f} (avg: {stats.avg_r:.3f})",
            f"<b>G:</b> {stats.min_g:.3f} - {stats.max_g:.3f} (avg: {stats.avg_g:.3f})",
            f"<b>B:</b> {stats.min_b:.3f} - {stats.max_b:.3f} (avg: {stats.avg_b:.3f})",
            f"<b>Max:</b> {stats.max_value:.3f}",
        ]
        if stats.hdr_percent > 0:
            lines.append(
                f"<span style='color: #ff69b4;'><b>HDR pixels:</b> "
                f"{stats.hdr_pixel_count:,} ({stats.hdr_percent:.2f}%)</span>"
            )
        else:
            lines.append("<b>HDR pixels:</b> 0 (0%)")
        text = "<br>".join(lines)
        self.hdr_stats_changed.emit(text)
        return text

    # ------------------------------------------------------------------
    # Per-frame update — called by view's timer
    # ------------------------------------------------------------------

    def notify_frame_rendered(self) -> None:
        """Called once per editor frame; views refresh preview / timing."""
        if self._core.capture.has_capture():
            self.capture_updated.emit(self)
        self.info_changed.emit(self)

    # ------------------------------------------------------------------
    # Pipeline connect / disconnect
    # ------------------------------------------------------------------

    def _reconnect(self) -> None:
        self._disconnect()
        self._connect()
        if self._on_request_update is not None:
            self._on_request_update()

    def disconnect(self) -> None:
        """Public: called by view when the debugger closes."""
        self._disconnect()

    def _disconnect(self) -> None:
        for pipeline in self._known_pipelines():
            pipeline.remove_passes_by_name("FrameDebugger")
        self._frame_debugger_pass = None
        for pipeline in self._known_pipelines():
            for p in pipeline.passes:
                try:
                    p.set_debug_internal_point("")
                    p.clear_debug_capture()
                except AttributeError:
                    pass
        self._connected_pipeline = None
        self._core.capture.reset_capture()

    def _known_pipelines(self) -> list:
        result = []

        def add(pipeline) -> None:
            if pipeline is None:
                return
            for existing in result:
                if existing is pipeline:
                    return
            result.append(pipeline)

        add(self._connected_pipeline)
        add(self.get_current_pipeline())
        for viewport, _label in self._viewports_list:
            managed_by = viewport.managed_by_scene_pipeline
            if managed_by and viewport.scene is not None:
                from termin.visualization.core.scene import scene_render_mount
                add(scene_render_mount(viewport.scene).get_pipeline(managed_by))
            else:
                add(viewport.pipeline)
        return result

    def _connect(self) -> None:
        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return
        self._connected_pipeline = pipeline

        if self._mode == "between":
            if not self._debug_source_res:
                return
            from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

            def get_source():
                if self._debug_paused:
                    return None
                return self._debug_source_res

            self._frame_debugger_pass = FrameDebuggerPass(
                get_source_res=get_source,
                pass_name="FrameDebugger",
            )
            self._frame_debugger_pass.set_capture(self._core.capture)
            pipeline.add_pass(self._frame_debugger_pass)
            log.info(
                f"[FrameDebugger] Connected: between mode, "
                f"resource='{self._debug_source_res}'"
            )
            return

        if self._mode == "inside":
            if not self._selected_pass or not self._selected_symbol:
                return
            for p in pipeline.passes:
                if p.pass_name == self._selected_pass:
                    p.set_debug_internal_point(self._selected_symbol)
                    p.set_debug_capture(self._core.capture)
                    log.info(
                        f"[FrameDebugger] Connected: inside mode, "
                        f"pass='{self._selected_pass}', "
                        f"symbol='{self._selected_symbol}'"
                    )
                    return
            log.warn(f"[FrameDebugger] Pass '{self._selected_pass}' not found")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_schedule(self, exclude_debugger: bool = False) -> list:
        """Ordered pass list resolved by FrameGraph dependency analysis
        (mirrors Qt ``FramegraphDebugDialog._build_schedule``). Every pass
        is asked for its required_resources before the graph is built."""
        from termin.visualization.render.framegraph.core import FrameGraph
        from termin.visualization.render.framegraph.passes.base import RenderFramePass
        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return []

        passes = pipeline.passes
        if exclude_debugger:
            passes = [p for p in passes if not isinstance(p, FrameDebuggerPass)]

        for render_pass in passes:
            if isinstance(render_pass, RenderFramePass):
                render_pass.required_resources()

        graph = FrameGraph(passes)
        return graph.build_schedule()
