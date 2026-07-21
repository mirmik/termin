"""Native UI projection over the C++ FrameGraphDebugger."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Callable
import weakref

from termin.engine import FrameGraphDebuggerMode
from termin.editor_native.ui_host import NativeUiWindow, NativeUiWindowManager
from termin.gui_native import (
    Document,
    EdgeInsets,
    Point,
    RichTextModel,
    Size,
    WidgetRef,
)


_logger = logging.getLogger(__name__)


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


def _labeled_row(document: Document, label: str, control, *, label_width: float = 82.0) -> WidgetRef:
    row = document.create_hstack(f"framegraph-{label.lower().replace(' ', '-')}-row")
    row.set_layout_spacing(4.0)
    caption = document.create_label(label)
    row.add_fixed_child(_ref(document, caption), label_width)
    row.add_stretch_child(_ref(document, control))
    return row


@dataclass
class NativeFramegraphPreviewSurface:
    """Render a debugger capture through its presenter into a sampled UI texture."""

    context: object
    canvas: object
    root: WidgetRef
    capture: object
    presenter: object
    channel_mode: int = 0
    highlight_hdr: bool = False
    force_depth: bool = False
    target: object | None = None
    target_size: tuple[int, int] = (0, 0)
    cursor_pixel: tuple[int, int] | None = None
    _canvas_has_texture: bool = False

    def __post_init__(self) -> None:
        # Keep the preview in its parent layout even before the first scene
        # frame has supplied a capture.  BoxLayout excludes invisible children,
        # which used to collapse the main preview and move the depth panel.
        self.root.visible = True

    def render(self, context: object) -> bool:
        if not self.capture.has_capture() or not self.capture.capture_tex:
            if self._canvas_has_texture:
                self.canvas.clear_texture()
                self._canvas_has_texture = False
            self.cursor_pixel = None
            return False
        width = int(self.capture.width)
        height = int(self.capture.height)
        if width <= 0 or height <= 0:
            if self._canvas_has_texture:
                self.canvas.clear_texture()
                self._canvas_has_texture = False
            self.cursor_pixel = None
            return False
        target_recreated = False
        if self.target is None or self.target_size != (width, height):
            self._destroy_target()
            self.target = context.create_color_attachment(width, height)
            self.target_size = (width, height)
            target_recreated = True
        depth = self.force_depth or bool(self.capture.is_depth)
        self.presenter.render(
            context,
            self.capture.capture_tex,
            self.target,
            0,
            0,
            width,
            height,
            5 if depth else self.channel_mode,
            False if depth else self.highlight_hdr,
        )
        if target_recreated or not self._canvas_has_texture:
            self.canvas.set_texture(self.target, Size(float(width), float(height)))
            self._canvas_has_texture = True
        return True

    def fit(self) -> None:
        self.canvas.fit_in_view()

    def actual_size(self) -> None:
        bounds = self.canvas.widget.bounds
        anchor = Point(
            bounds.x + bounds.width * 0.5,
            bounds.y + bounds.height * 0.5,
        )
        self.canvas.set_zoom(1.0, anchor)

    def update_cursor(self, image_point: Point) -> None:
        width, height = self.target_size
        if 0.0 <= image_point.x < width and 0.0 <= image_point.y < height:
            self.cursor_pixel = (int(image_point.x), int(image_point.y))
        else:
            self.cursor_pixel = None

    def status_text(self) -> str:
        width, height = self.target_size
        source = f"{width}x{height}" if width > 0 and height > 0 else "—"
        zoom = f"{self.canvas.zoom * 100.0:.0f}%"
        mode = f"Fit ({zoom})" if self.canvas.fit_mode else zoom
        pixel = (
            f"{self.cursor_pixel[0]}, {self.cursor_pixel[1]}"
            if self.cursor_pixel is not None
            else "—"
        )
        return f"Source: {source} | Zoom: {mode} | Pixel: {pixel}"

    def close(self) -> None:
        if self._canvas_has_texture:
            self.canvas.clear_texture()
            self._canvas_has_texture = False
        self._destroy_target()

    def _destroy_target(self) -> None:
        if self.target is not None:
            self.context.destroy_texture(self.target)
            self.target = None
            self.target_size = (0, 0)


@dataclass
class NativeFramegraphDebugger:
    document: Document
    model: object
    window_manager: NativeUiWindowManager
    root: WidgetRef
    target_combo: object
    mode_combo: object
    pass_combo: object
    symbol_combo: object
    resource_combo: object
    channel_combo: object
    pause_check: object
    hdr_check: object
    inside_panel: WidgetRef
    between_panel: WidgetRef
    pass_json: object
    pipeline_model: RichTextModel
    fbo_model: RichTextModel
    hdr_model: RichTextModel
    stats_bar: object
    timing_bar: object
    depth_status: object
    depth_read_status: object
    main_status: object
    main_fit_button: object
    main_actual_button: object
    depth_fit_button: object
    depth_actual_button: object
    main_preview: NativeFramegraphPreviewSurface
    depth_preview: NativeFramegraphPreviewSurface
    request_scene_render: Callable[[], None]
    device: object
    window: NativeUiWindow | None = None
    pass_indices: list[int] = field(default_factory=list)
    _updating: bool = False
    _active: bool = False
    _closed: bool = False
    _main_preview_ready: bool = False
    _depth_preview_ready: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native framegraph debugger is closed")
        if self.window is not None and not self.window.closed:
            return False
        self._bind_signals()
        self._active = True
        self.model.refresh()
        self._select_initial_values()
        self.model.connect()
        self._refresh_lists()
        self._refresh_selection()
        self._refresh_info()
        try:
            window = self.window_manager.create_window(
                "Framegraph Debugger",
                1180,
                760,
                document=self.document,
                on_close=self._on_window_closed,
            )
        except Exception:
            self._deactivate()
            raise
        self.window = window
        self.main_preview.context = window.host.context
        self.depth_preview.context = window.host.context
        window.host.add_pre_render_callback(self.render_previews)
        self.request_render()
        return True

    def update(self) -> bool:
        if not self._active or self.window is None or self.window.closed:
            return False
        self.model.finish_frame()
        self.model.refresh()
        self._refresh_lists()
        self._refresh_selection()
        self._refresh_info()
        self._capture_updated()
        return True

    def show_resource(self, resource_name: str) -> bool:
        if self.window is None or self.window.closed:
            self.show()
        resources = self.model.resources()
        if resource_name not in resources:
            _logger.error(
                "Native framegraph debugger cannot select missing resource '%s'",
                resource_name,
            )
            return False
        self.model.mode = FrameGraphDebuggerMode.BetweenPasses
        self.model.selected_resource = resource_name
        return True

    def render_previews(self, context: object) -> None:
        if not self._active or self.window is None or self.window.closed:
            return
        self.main_preview.channel_mode = self.model.channel_mode
        self.main_preview.highlight_hdr = self.model.highlight_hdr
        main_ready = self.main_preview.render(context)
        depth_ready = self.depth_preview.render(context)
        main_status = self.main_preview.status_text()
        if self.main_status.text != main_status:
            self.main_status.text = main_status
        depth_status = self.depth_preview.status_text()
        if self.depth_status.text != depth_status:
            self.depth_status.text = depth_status
        # Pre-render runs after layout.  A newly registered capture changes the
        # canvas source transform, so request one follow-up UI frame.
        if (
            main_ready != self._main_preview_ready
            or depth_ready != self._depth_preview_ready
        ):
            self._main_preview_ready = main_ready
            self._depth_preview_ready = depth_ready
            self.request_render()

    def refresh_depth(self) -> str:
        capture = self.model.depth_capture
        if not capture.has_capture() or not capture.capture_tex:
            text = "No depth capture"
        else:
            try:
                result = self.model.presenter.read_depth_normalized(
                    self.device,
                    capture.capture_tex,
                )
                text = "No depth data" if result is None else f"Depth: {result[1]}x{result[2]} read OK"
            except Exception as error:
                _logger.exception("Native framegraph depth read failed")
                text = f"Depth error: {error}"
        self.depth_read_status.text = text
        self.request_render()
        return text

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.dismiss()
        if self._active:
            self._deactivate()
        self.main_preview.close()
        self.depth_preview.close()
        if self.document.is_alive(self.root.handle):
            self.document.destroy_widget_recursive(self.root.handle)
        self.document.close()

    def dismiss(self) -> None:
        if self.window is not None and not self.window.closed:
            self.window.close()

    def request_render(self) -> None:
        self.request_scene_render()
        if self.window is not None and not self.window.closed:
            self.window.request_render_update()

    def _on_window_closed(self) -> None:
        window = self.window
        if window is not None:
            window.host.remove_pre_render_callback(self.render_previews)
        self.window = None
        self._deactivate()

    def _select_initial_values(self) -> None:
        targets = self.model.targets
        if self.model.selected_target_index is None and targets:
            if not self.model.select_target_at(0):
                _logger.error(
                    "Native framegraph debugger failed to select initial target '%s'",
                    targets[0].label,
                )
        passes = self.model.passes()
        if self.model.selected_pass_index is None and passes:
            self.model.selected_pass_index = passes[0].index
        resources = self.model.resources()
        if not self.model.selected_resource and resources:
            self.model.selected_resource = resources[0]

    def _bind_signals(self) -> None:
        pass

    def _deactivate(self) -> None:
        if not self._active:
            return
        self._active = False
        self.model.disconnect()
        self.main_preview.close()
        self.depth_preview.close()

    def _refresh_lists(self, _model=None) -> None:
        self._updating = True
        try:
            self.target_combo.clear()
            targets = self.model.targets
            for target in targets:
                self.target_combo.add_item(target.label)
            selected_target = self.model.selected_target_index
            self.target_combo.selected_index = (
                selected_target if selected_target is not None else -1
            )

            self.resource_combo.clear()
            resources = self.model.resources()
            for resource in resources:
                self.resource_combo.add_item(resource)
            self.resource_combo.selected_index = (
                resources.index(self.model.selected_resource)
                if self.model.selected_resource in resources
                else -1
            )

            self.pass_combo.clear()
            self.pass_indices.clear()
            selected_pass = -1
            for row, item in enumerate(self.model.passes()):
                self.pass_combo.add_item(item.display_name)
                self.pass_indices.append(item.index)
                if item.index == self.model.selected_pass_index:
                    selected_pass = row
            self.pass_combo.selected_index = selected_pass

            self.symbol_combo.clear()
            symbols = self.model.symbols()
            for symbol in symbols:
                self.symbol_combo.add_item(symbol)
            self.symbol_combo.selected_index = (
                symbols.index(self.model.selected_symbol)
                if self.model.selected_symbol in symbols
                else -1
            )
        finally:
            self._updating = False
        self.request_render()

    def _refresh_selection(self, _model=None) -> None:
        self._updating = True
        try:
            self.mode_combo.selected_index = (
                0 if self.model.mode == FrameGraphDebuggerMode.InsidePass else 1
            )
            self.channel_combo.selected_index = self.model.channel_mode
            self.pause_check.checked = self.model.paused
            self.hdr_check.checked = self.model.highlight_hdr
            self.inside_panel.visible = self.model.mode == FrameGraphDebuggerMode.InsidePass
            self.between_panel.visible = self.model.mode == FrameGraphDebuggerMode.BetweenPasses
        finally:
            self._updating = False
        self.request_render()

    def _refresh_info(self, _model=None) -> None:
        self.fbo_model.set_html(self.model.format_capture_info())
        self.pipeline_model.set_html(self.model.format_pipeline_info())
        self.pass_json.text = self.model.format_pass_json()
        self.stats_bar.text = self.model.format_render_stats()
        self.timing_bar.text = self.model.format_timing() or "Timing: no selection"
        self.request_render()

    def _capture_updated(self, _model=None) -> None:
        self.request_render()

    def _preview_changed(self, _model=None) -> None:
        self.request_render()

    def _refresh_preview_statuses(self) -> None:
        self.main_status.text = self.main_preview.status_text()
        self.depth_status.text = self.depth_preview.status_text()
        if self.window is not None and not self.window.closed:
            self.window.request_render_update()

    def _hdr_stats_changed(self, text: str) -> None:
        self.hdr_model.set_html(text)
        self.request_render()


def build_native_framegraph_debugger(
    window_manager: NativeUiWindowManager,
    model: object,
    *,
    request_render: Callable[[], None],
) -> NativeFramegraphDebugger:
    document = Document()
    root = document.create_vstack("native-framegraph-debugger")
    root.stable_id = "editor.framegraph-debugger"
    if not document.add_root(root.handle):
        raise RuntimeError("failed to add native framegraph debugger root")
    root.preferred_size = Size(1180.0, 760.0)
    root.set_layout_padding(EdgeInsets(5.0, 5.0, 5.0, 5.0))
    root.set_layout_spacing(5.0)

    top = document.create_hstack("framegraph-top")
    top.set_layout_spacing(8.0)
    settings = document.create_vstack("framegraph-settings")
    settings.set_layout_spacing(4.0)

    target_combo = document.create_combo_box()
    settings.add_fixed_child(_labeled_row(document, "Target:", target_combo), 30.0)
    mode_combo = document.create_combo_box()
    mode_combo.add_item("Passes")
    mode_combo.add_item("Resources")
    settings.add_fixed_child(_labeled_row(document, "Mode:", mode_combo), 30.0)

    inside = document.create_vstack("framegraph-inside-panel")
    inside.set_layout_spacing(4.0)
    pass_combo = document.create_combo_box()
    inside.add_fixed_child(_labeled_row(document, "Pass:", pass_combo), 30.0)
    symbol_combo = document.create_combo_box()
    inside.add_fixed_child(_labeled_row(document, "Symbol:", symbol_combo), 30.0)
    pass_json = document.create_text_area()
    inside.add_stretch_child(_ref(document, pass_json))
    settings.add_stretch_child(inside)

    between = document.create_vstack("framegraph-between-panel")
    between.set_layout_spacing(4.0)
    resource_combo = document.create_combo_box()
    between.add_fixed_child(_labeled_row(document, "Resource:", resource_combo), 30.0)
    hdr_check = document.create_checkbox(False)
    analyze = document.create_button("Analyze HDR")
    hdr_row = document.create_hstack("framegraph-hdr-row")
    hdr_row.set_layout_spacing(4.0)
    hdr_row.add_stretch_child(_ref(document, hdr_check))
    hdr_row.add_fixed_child(_ref(document, analyze), 110.0)
    between.add_fixed_child(hdr_row, 30.0)
    hdr_model = RichTextModel()
    hdr_view = document.create_rich_text_view(hdr_model)
    between.add_stretch_child(_ref(document, hdr_view))
    between.visible = False
    settings.add_stretch_child(between)

    controls = document.create_hstack("framegraph-controls")
    controls.set_layout_spacing(4.0)
    pause_check = document.create_checkbox(False)
    controls.add_fixed_child(_ref(document, pause_check), 90.0)
    channel_combo = document.create_combo_box()
    for channel in ("RGBA", "R", "G", "B", "A"):
        channel_combo.add_item(channel)
    controls.add_stretch_child(_ref(document, channel_combo))
    refresh_stats = document.create_button("Refresh Stats")
    controls.add_fixed_child(_ref(document, refresh_stats), 110.0)
    settings.add_fixed_child(controls, 30.0)
    top.add_fixed_child(settings, 520.0)

    pipeline_model = RichTextModel()
    pipeline_view = document.create_rich_text_view(pipeline_model)
    pipeline_view.word_wrap = False
    pipeline_view.placeholder = "No pipeline"
    top.add_stretch_child(_ref(document, pipeline_view))
    root.add_fixed_child(top, 320.0)

    fbo_model = RichTextModel()
    fbo_view = document.create_rich_text_view(fbo_model)
    root.add_fixed_child(_ref(document, fbo_view), 42.0)

    previews = document.create_hstack("framegraph-previews")
    previews.set_layout_spacing(8.0)
    main_panel = document.create_vstack("framegraph-main-preview-panel")
    main_panel.set_layout_spacing(4.0)
    main_canvas = document.create_canvas()
    main_root = _ref(document, main_canvas)
    main_panel.add_stretch_child(main_root)
    main_view_controls = document.create_hstack("framegraph-main-view-controls")
    main_view_controls.set_layout_spacing(4.0)
    main_fit_button = document.create_button("Fit")
    main_actual_button = document.create_button("1:1")
    main_view_controls.add_fixed_child(_ref(document, main_fit_button), 64.0)
    main_view_controls.add_fixed_child(_ref(document, main_actual_button), 64.0)
    main_panel.add_fixed_child(_ref(document, main_view_controls), 30.0)
    main_status = document.create_status_bar("Source: — | Zoom: Fit (100%) | Pixel: —")
    main_panel.add_fixed_child(_ref(document, main_status), 24.0)
    previews.add_stretch_child(_ref(document, main_panel))
    depth_panel = document.create_vstack("framegraph-depth-panel")
    depth_panel.set_layout_spacing(4.0)
    depth_canvas = document.create_canvas()
    depth_root = _ref(document, depth_canvas)
    depth_panel.add_stretch_child(depth_root)
    depth_view_controls = document.create_hstack("framegraph-depth-view-controls")
    depth_view_controls.set_layout_spacing(4.0)
    depth_fit_button = document.create_button("Fit")
    depth_actual_button = document.create_button("1:1")
    depth_view_controls.add_fixed_child(_ref(document, depth_fit_button), 64.0)
    depth_view_controls.add_fixed_child(_ref(document, depth_actual_button), 64.0)
    refresh_depth = document.create_button("Refresh Depth")
    depth_view_controls.add_stretch_child(_ref(document, refresh_depth))
    depth_panel.add_fixed_child(_ref(document, depth_view_controls), 30.0)
    depth_status = document.create_status_bar("Source: — | Zoom: Fit (100%) | Pixel: —")
    depth_panel.add_fixed_child(_ref(document, depth_status), 24.0)
    depth_read_status = document.create_status_bar("No depth capture")
    depth_panel.add_fixed_child(_ref(document, depth_read_status), 24.0)
    previews.add_fixed_child(depth_panel, 320.0)
    root.add_stretch_child(previews)

    stats_bar = document.create_status_bar("Render stats")
    root.add_fixed_child(_ref(document, stats_bar), 24.0)
    timing_bar = document.create_status_bar("Timing: no selection")
    root.add_fixed_child(_ref(document, timing_bar), 24.0)

    context = window_manager.main_host.context
    main_preview = NativeFramegraphPreviewSurface(
        context,
        main_canvas,
        main_root,
        model.capture,
        model.presenter,
    )
    depth_preview = NativeFramegraphPreviewSurface(
        context,
        depth_canvas,
        depth_root,
        model.depth_capture,
        model.presenter,
        force_depth=True,
    )
    result = NativeFramegraphDebugger(
        document=document,
        model=model,
        window_manager=window_manager,
        root=root,
        target_combo=target_combo,
        mode_combo=mode_combo,
        pass_combo=pass_combo,
        symbol_combo=symbol_combo,
        resource_combo=resource_combo,
        channel_combo=channel_combo,
        pause_check=pause_check,
        hdr_check=hdr_check,
        inside_panel=inside,
        between_panel=between,
        pass_json=pass_json,
        pipeline_model=pipeline_model,
        fbo_model=fbo_model,
        hdr_model=hdr_model,
        stats_bar=stats_bar,
        timing_bar=timing_bar,
        depth_status=depth_status,
        depth_read_status=depth_read_status,
        main_status=main_status,
        main_fit_button=main_fit_button,
        main_actual_button=main_actual_button,
        depth_fit_button=depth_fit_button,
        depth_actual_button=depth_actual_button,
        main_preview=main_preview,
        depth_preview=depth_preview,
        request_scene_render=request_render,
        device=window_manager.main_host.device,
    )
    weak_result = weakref.ref(result)

    def current() -> NativeFramegraphDebugger | None:
        return weak_result()

    target_combo.connect_changed(
        lambda index, _text: current().model.select_target_at(index)
        if current() is not None and not current()._updating
        else None
    )

    def mode_changed(index: int, _text: str) -> None:
        owner = current()
        if owner is None or owner._updating:
            return
        owner.model.mode = (
            FrameGraphDebuggerMode.InsidePass
            if index == 0 else FrameGraphDebuggerMode.BetweenPasses
        )

    mode_combo.connect_changed(mode_changed)

    def pass_changed(index: int, _text: str) -> None:
        owner = current()
        if owner is None or owner._updating or not (0 <= index < len(owner.pass_indices)):
            return
        owner.model.selected_pass_index = owner.pass_indices[index]

    pass_combo.connect_changed(pass_changed)
    def symbol_changed(_index: int, text: str) -> None:
        owner = current()
        if owner is not None and not owner._updating:
            owner.model.selected_symbol = text or ""

    symbol_combo.connect_changed(symbol_changed)

    def resource_changed(_index: int, text: str) -> None:
        owner = current()
        if owner is not None and not owner._updating and text:
            owner.model.selected_resource = text

    resource_combo.connect_changed(resource_changed)

    def channel_changed(index: int, _text: str) -> None:
        owner = current()
        if owner is not None and not owner._updating:
            owner.model.channel_mode = index

    channel_combo.connect_changed(channel_changed)
    pause_check.connect_changed(
        lambda checked: current().model.set_paused(checked)
        if current() is not None and not current()._updating
        else None
    )
    def hdr_changed(checked: bool) -> None:
        owner = current()
        if owner is not None and not owner._updating:
            owner.model.highlight_hdr = checked

    hdr_check.connect_changed(hdr_changed)
    analyze.connect_clicked(
        lambda: current()._hdr_stats_changed(current().model.analyze_hdr())
        if current() is not None else None
    )
    refresh_stats.connect_clicked(
        lambda: current()._refresh_info() if current() is not None else None
    )
    refresh_depth.connect_clicked(lambda: current().refresh_depth() if current() is not None else None)

    def update_preview_status(preview_name: str, image_point=None) -> None:
        owner = current()
        if owner is None:
            return
        surface = owner.main_preview if preview_name == "main" else owner.depth_preview
        if image_point is not None:
            surface.update_cursor(image_point)
        owner._refresh_preview_statuses()

    main_canvas.connect_zoom_changed(
        lambda _zoom: update_preview_status("main")
    )
    depth_canvas.connect_zoom_changed(
        lambda _zoom: update_preview_status("depth")
    )
    main_canvas.connect_pointer_input(
        lambda image_point, _event: update_preview_status("main", image_point)
    )
    depth_canvas.connect_pointer_input(
        lambda image_point, _event: update_preview_status("depth", image_point)
    )

    def fit_preview(preview_name: str) -> None:
        owner = current()
        if owner is None:
            return
        surface = owner.main_preview if preview_name == "main" else owner.depth_preview
        surface.fit()
        update_preview_status(preview_name)

    def show_actual_size(preview_name: str) -> None:
        owner = current()
        if owner is None:
            return
        surface = owner.main_preview if preview_name == "main" else owner.depth_preview
        surface.actual_size()
        update_preview_status(preview_name)

    main_fit_button.connect_clicked(lambda: fit_preview("main"))
    main_actual_button.connect_clicked(lambda: show_actual_size("main"))
    depth_fit_button.connect_clicked(lambda: fit_preview("depth"))
    depth_actual_button.connect_clicked(lambda: show_actual_size("depth"))

    return result


def connect_framegraph_debugger_command(menu_bar, command_id: int, debugger) -> None:
    weak_debugger = weakref.ref(debugger)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        if activated_id != command_id:
            return
        owner = weak_debugger()
        if owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeFramegraphDebugger",
    "NativeFramegraphPreviewSurface",
    "build_native_framegraph_debugger",
    "connect_framegraph_debugger_command",
]
