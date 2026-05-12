"""FramegraphDebuggerModel — UI-agnostic state and business logic for the framegraph debugger.

Both Qt (``editor/framegraph_debugger.py``) and tcgui (``editor_tcgui/dialogs/framegraph_debugger.py``)
views subscribe to this model and convert its state snapshots into their own
widget updates. Pipeline connection (``FrameDebugCapturePass`` lifecycle, per-pass
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
from termin.render_framework import FrameDebugCapturePass, PipelineFrameGraphView

from termin.editor_core.signal import Signal

if TYPE_CHECKING:
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.render.framegraph import RenderPipeline


_PIXEL_FORMAT_NAMES = {
    0: "r8",
    1: "rg8",
    2: "rgb8",
    3: "rgba8",
    4: "bgra8",
    5: "r16f",
    6: "rg16f",
    7: "rgba16f",
    8: "r32f",
    9: "rg32f",
    10: "rgba32f",
    11: "depth24",
    12: "depth24_stencil8",
    13: "depth32f",
    14: "undefined",
}


def _format_pixel_format(value: int) -> str:
    name = _PIXEL_FORMAT_NAMES.get(value)
    if name is None:
        log.warn(f"[FrameDebugger] Unknown tgfx PixelFormat value: {value}")
        return f"unknown({value})"
    return name


class FramegraphDebugTarget:
    """A renderable target the framegraph debugger can inspect."""

    source: object
    label: str
    get_pipeline: Callable[[], object | None]

    def __init__(
        self,
        source: object,
        label: str,
        get_pipeline: Callable[[], object | None],
    ) -> None:
        self.source = source
        self.label = label
        self.get_pipeline = get_pipeline


class FramegraphDebuggerModel:
    def __init__(self, rendering_controller, core, on_request_update: Callable[[], None] | None = None):
        self._rendering_controller = rendering_controller
        self._core = core
        self._on_request_update = on_request_update

        self._current_target: FramegraphDebugTarget | None = None
        self._targets_list: list[FramegraphDebugTarget] = []

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
        if self._current_target is None:
            return None
        return self._current_target.source

    @property
    def viewports(self) -> list[tuple[object, str]]:
        return [(target.source, target.label) for target in self._targets_list]

    @property
    def targets(self) -> list[FramegraphDebugTarget]:
        return list(self._targets_list)

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
        if self._current_target is None:
            return None
        return self._current_target.get_pipeline()

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

    def get_capture_resource_info(self, resource_name: str) -> dict | None:
        capture = self._core.capture
        if not capture.has_capture():
            return None
        is_depth = bool(capture.is_depth)
        resource_type = self._resource_type(resource_name)
        if resource_type not in ("color_texture", "depth_texture", "fbo", "external_color"):
            resource_type = "depth_texture" if is_depth else "color_texture"
        samples = 1
        pipeline = self.get_current_pipeline()
        if pipeline is not None and resource_name:
            try:
                source_info = pipeline.get_resource_info(resource_name)
                if isinstance(source_info, dict) and "samples" in source_info:
                    samples = int(source_info["samples"])
            except Exception as e:
                log.warn(f"[FrameDebugger] failed to read resource info for '{resource_name}': {e}")
        return {
            "key": resource_name,
            "width": int(capture.width),
            "height": int(capture.height),
            "resource_type": resource_type,
            "color_format_name": _format_pixel_format(int(capture.format)),
            "has_depth": is_depth,
            "samples": samples,
        }

    def _resource_type(self, resource_name: str) -> str | None:
        if not resource_name:
            return None
        if resource_name.endswith(".depth") or resource_name == "RT_DEPTH":
            return "depth_texture"
        if resource_name.endswith(".color"):
            return "color_texture"

        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return None
        for spec in pipeline.pipeline_specs:
            if spec.resource == resource_name:
                return spec.resource_type
        return None

    # ------------------------------------------------------------------
    # Refresh list contents (from rendering_controller / pipeline state)
    # ------------------------------------------------------------------

    def refresh_viewports(self) -> None:
        current_source = self._current_target.source if self._current_target is not None else None
        if self._rendering_controller is None:
            self._targets_list = []
        else:
            self._targets_list = list(self._rendering_controller.get_framegraph_debug_targets_info())
        self._current_target = None
        if current_source is not None:
            for target in self._targets_list:
                if target.source is current_source:
                    self._current_target = target
                    break
        if self._targets_list and self._current_target is None:
            self._current_target = self._targets_list[0]
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
        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return []
        result: list[tuple[str, bool]] = []
        for p in pipeline.passes:
            if p.pass_name == "FrameDebugger":
                continue
            if p.type_name == "ShadowPass" or p.pass_name == "ShadowPass":
                has_syms = False
            else:
                has_syms = bool(p.get_internal_symbols())
            result.append((p.pass_name, has_syms))
        return result

    def get_symbols(self) -> list[str]:
        pipeline = self.get_current_pipeline()
        if pipeline is None or self._selected_pass is None:
            return []
        for p in pipeline.passes:
            if p.pass_name != self._selected_pass:
                continue
            return list(p.get_internal_symbols())
        return []

    # ------------------------------------------------------------------
    # Info-text formatters (view displays verbatim)
    # ------------------------------------------------------------------

    def format_fbo_info(self) -> str:
        """Info line for the resource actually captured by the debugger."""
        resource_name = self._debug_source_res
        resource = self.get_capture_resource_info(resource_name)
        if resource is None:
            return f"Ресурс '{resource_name}': capture ещё не получен"

        parts = [f"<b>{resource_name}</b>"]
        w = int(resource["width"])
        h = int(resource["height"])
        parts.append(f"Тип: {resource['resource_type']}")
        parts.append(f"Размер: {w}×{h}")
        parts.append(f"fmt={resource['color_format_name']}")
        samples = int(resource.get("samples", 1))
        if samples > 1:
            parts.append(f"MSAA={samples}x")
        else:
            parts.append("MSAA=off")
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
        schedule = self._build_schedule(exclude_debugger=False)
        if not schedule:
            return "<i>Pipeline пуст</i>"

        current_resource = self._debug_source_res
        lines: list[str] = []
        for p in schedule:
            reads_str = ", ".join(sorted(p.reads)) if p.reads else "∅"
            writes_str = ", ".join(sorted(p.writes)) if p.writes else "∅"
            line = f"{p.pass_name}: {{{reads_str}}} → {{{writes_str}}}"
            if p.pass_name == "FrameDebugger":
                line = f"<span style='color: #ffb86c;'>► {line}</span>"
            elif current_resource and current_resource in p.writes:
                line = f"<span style='color: #50fa7b; font-weight: bold;'>● {line}</span>"
            lines.append(line)
        alias_lines = self._format_alias_groups()
        if alias_lines:
            lines.append("")
            lines.append("Aliases:")
            lines.extend(alias_lines)
        return "<pre>" + "<br>".join(lines) + "</pre>"

    def _format_alias_groups(self) -> list[str]:
        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return []

        lines: list[str] = []
        with PipelineFrameGraphView(pipeline) as graph:
            alias_groups = graph.alias_groups()
        for canonical, group in sorted(alias_groups.items()):
            aliases = sorted(group)
            if len(aliases) <= 1:
                continue
            lines.append(f"{canonical}: {', '.join(aliases)}")
        return lines

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
            timings = p.get_internal_symbols_with_timing()
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
        if index < 0 or index >= len(self._targets_list):
            self._current_target = None
        else:
            self._current_target = self._targets_list[index]
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
        if self._frame_debugger_pass is not None:
            self._frame_debugger_pass.set_paused(self._debug_paused)

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

        if self._core.capture.is_depth:
            text = "HDR stats недоступны для depth_texture"
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
                p.set_debug_internal_point("")
                p.clear_debug_capture()
        self._connected_pipeline = None
        self._core.capture.reset_capture()
        self._core.depth_capture.reset_capture()

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
        for target in self._targets_list:
            add(target.get_pipeline())
        return result

    def _connect(self) -> None:
        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return
        self._connected_pipeline = pipeline

        if self._mode == "between":
            if not self._debug_source_res:
                return

            self._frame_debugger_pass = FrameDebugCapturePass(pass_name="FrameDebugger")
            self._frame_debugger_pass.set_source_resource(self._debug_source_res)
            self._frame_debugger_pass.set_source_type(self._resource_type(self._debug_source_res) or "")
            self._frame_debugger_pass.set_paused(self._debug_paused)
            self._frame_debugger_pass.set_capture(self._core.capture)
            self._frame_debugger_pass.set_depth_capture(self._core.depth_capture)
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
        """Ordered pass list resolved by native tc_frame_graph dependency analysis."""
        pipeline = self.get_current_pipeline()
        if pipeline is None:
            return []

        with PipelineFrameGraphView(pipeline) as graph:
            passes = graph.schedule()
        if exclude_debugger:
            passes = [p for p in passes if p.pass_name != "FrameDebugger"]
        return passes
