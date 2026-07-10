"""Native Framegraph Debugger projection over the shared debugger model."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Callable
import weakref

from termin.editor_core.framegraph_debugger_model import FramegraphDebuggerModel
from termin.gui_native import (
    DialogAction,
    Document,
    EdgeInsets,
    Rect,
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
    image: object
    root: WidgetRef
    capture: object
    presenter: object
    channel_mode: int = 0
    highlight_hdr: bool = False
    force_depth: bool = False
    target: object | None = None
    target_size: tuple[int, int] = (0, 0)

    def render(self, context: object) -> bool:
        if not self.capture.has_capture() or not self.capture.capture_tex:
            self.root.visible = False
            return False
        width = int(self.capture.width)
        height = int(self.capture.height)
        if width <= 0 or height <= 0:
            self.root.visible = False
            return False
        if self.target is None or self.target_size != (width, height):
            self._destroy_target()
            self.target = context.create_color_attachment(width, height)
            self.target_size = (width, height)
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
        self.image.set_texture(self.target, Size(float(width), float(height)))
        self.root.visible = True
        return True

    def close(self) -> None:
        self.root.visible = False
        self._destroy_target()

    def _destroy_target(self) -> None:
        if self.target is not None:
            self.context.destroy_texture(self.target)
            self.target = None
            self.target_size = (0, 0)


@dataclass
class NativeFramegraphDebugger:
    document: Document
    model: FramegraphDebuggerModel
    dialog: object
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
    main_preview: NativeFramegraphPreviewSurface
    depth_preview: NativeFramegraphPreviewSurface
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    remove_pre_render_callback: Callable[[Callable[[object], None]], None]
    device: object
    pass_indices: list[int] = field(default_factory=list)
    _updating: bool = False
    _active: bool = False
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native framegraph debugger is closed")
        if self.dialog.open:
            return False
        self._bind_signals()
        self._active = True
        self.model.refresh_viewports()
        self._select_initial_values()
        self._refresh_info()
        shown = self.dialog.show(self.viewport())
        if not shown:
            self._deactivate()
            return False
        self.request_render()
        return True

    def update(self) -> bool:
        if not self._active or not self.dialog.open:
            return False
        self.model.notify_frame_rendered()
        return True

    def show_resource(self, resource_name: str) -> bool:
        if not self.dialog.open:
            self.show()
        resources = self.model.get_resources()
        if resource_name not in resources:
            _logger.error(
                "Native framegraph debugger cannot select missing resource '%s'",
                resource_name,
            )
            return False
        self.model.set_mode("between")
        self.model.set_source_resource(resource_name)
        return True

    def render_previews(self, context: object) -> None:
        if not self._active or not self.dialog.open:
            return
        self.main_preview.channel_mode = self.model.channel_mode
        self.main_preview.highlight_hdr = self.model.highlight_hdr
        self.main_preview.render(context)
        self.depth_preview.render(context)

    def refresh_depth(self) -> str:
        capture = self.model.core.depth_capture
        if not capture.has_capture() or not capture.capture_tex:
            text = "No depth capture"
        else:
            try:
                result = self.model.core.presenter.read_depth_normalized(
                    self.device,
                    capture.capture_tex,
                )
                text = "No depth data" if result is None else f"Depth: {result[1]}x{result[2]} read OK"
            except Exception as error:
                _logger.exception("Native framegraph depth read failed")
                text = f"Depth error: {error}"
        self.depth_status.text = text
        self.request_render()
        return text

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        self._deactivate()
        self.remove_pre_render_callback(self.render_previews)
        self.main_preview.close()
        self.depth_preview.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)

    def _select_initial_values(self) -> None:
        passes = self.model.get_passes()
        if self.model.selected_pass_index is None and passes:
            self.model.set_selected_pass_by_index(passes[0].index)
        resources = self.model.get_resources()
        if not self.model.debug_source_res and resources:
            self.model.set_source_resource(resources[0])

    def _bind_signals(self) -> None:
        if self._active:
            return
        self.model.lists_changed.connect(self._refresh_lists)
        self.model.selection_changed.connect(self._refresh_selection)
        self.model.info_changed.connect(self._refresh_info)
        self.model.capture_updated.connect(self._capture_updated)
        self.model.preview_params_changed.connect(self._preview_changed)
        self.model.hdr_stats_changed.connect(self._hdr_stats_changed)

    def _deactivate(self) -> None:
        if not self._active:
            return
        self._active = False
        self.model.disconnect()
        self.model.lists_changed.disconnect(self._refresh_lists)
        self.model.selection_changed.disconnect(self._refresh_selection)
        self.model.info_changed.disconnect(self._refresh_info)
        self.model.capture_updated.disconnect(self._capture_updated)
        self.model.preview_params_changed.disconnect(self._preview_changed)
        self.model.hdr_stats_changed.disconnect(self._hdr_stats_changed)
        self.main_preview.close()
        self.depth_preview.close()

    def _refresh_lists(self, _model=None) -> None:
        self._updating = True
        try:
            self.target_combo.clear()
            targets = self.model.targets
            current_target = self.model.current_viewport
            selected_target = -1
            for index, target in enumerate(targets):
                self.target_combo.add_item(target.label)
                if target.source is current_target:
                    selected_target = index
            self.target_combo.selected_index = selected_target

            self.resource_combo.clear()
            resources = self.model.get_resources()
            for resource in resources:
                self.resource_combo.add_item(resource)
            self.resource_combo.selected_index = (
                resources.index(self.model.debug_source_res)
                if self.model.debug_source_res in resources
                else -1
            )

            self.pass_combo.clear()
            self.pass_indices.clear()
            selected_pass = -1
            for row, item in enumerate(self.model.get_passes()):
                self.pass_combo.add_item(item.display_name)
                self.pass_indices.append(item.index)
                if item.index == self.model.selected_pass_index:
                    selected_pass = row
            self.pass_combo.selected_index = selected_pass

            self.symbol_combo.clear()
            symbols = self.model.get_symbols()
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
            self.mode_combo.selected_index = 0 if self.model.mode == "inside" else 1
            self.channel_combo.selected_index = self.model.channel_mode
            self.pause_check.checked = self.model.debug_paused
            self.hdr_check.checked = self.model.highlight_hdr
            self.inside_panel.visible = self.model.mode == "inside"
            self.between_panel.visible = self.model.mode == "between"
        finally:
            self._updating = False
        self.request_render()

    def _refresh_info(self, _model=None) -> None:
        self.fbo_model.set_html(self.model.format_fbo_info())
        self.pipeline_model.set_html(self.model.format_pipeline_info())
        self.pass_json.text = self.model.format_pass_json()
        self.stats_bar.text = self.model.format_render_stats()
        self.timing_bar.text = self.model.format_timing() or "Timing: no selection"
        self.request_render()

    def _capture_updated(self, _model=None) -> None:
        self.request_render()

    def _preview_changed(self, _model=None) -> None:
        self.request_render()

    def _hdr_stats_changed(self, text: str) -> None:
        self.hdr_model.set_html(text)
        self.request_render()


def build_native_framegraph_debugger(
    document: Document,
    model: FramegraphDebuggerModel,
    *,
    context: object,
    device: object,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
    add_pre_render_callback: Callable[[Callable[[object], None]], None],
    remove_pre_render_callback: Callable[[Callable[[object], None]], None],
) -> NativeFramegraphDebugger:
    root = document.create_vstack("native-framegraph-debugger")
    root.stable_id = "editor.framegraph-debugger"
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
    main_image = document.create_image_widget()
    main_image.set_preserve_aspect(True)
    main_root = _ref(document, main_image)
    main_root.visible = False
    previews.add_stretch_child(main_root)
    depth_panel = document.create_vstack("framegraph-depth-panel")
    depth_panel.set_layout_spacing(4.0)
    depth_image = document.create_image_widget()
    depth_image.set_preserve_aspect(True)
    depth_root = _ref(document, depth_image)
    depth_root.visible = False
    depth_panel.add_stretch_child(depth_root)
    refresh_depth = document.create_button("Refresh Depth")
    depth_panel.add_fixed_child(_ref(document, refresh_depth), 30.0)
    depth_status = document.create_status_bar("No depth capture")
    depth_panel.add_fixed_child(_ref(document, depth_status), 24.0)
    previews.add_fixed_child(depth_panel, 320.0)
    root.add_stretch_child(previews)

    stats_bar = document.create_status_bar("Render stats")
    root.add_fixed_child(_ref(document, stats_bar), 24.0)
    timing_bar = document.create_status_bar("Timing: no selection")
    root.add_fixed_child(_ref(document, timing_bar), 24.0)

    dialog = document.create_dialog("Framegraph Debugger")
    dialog.actions = [DialogAction("close", "Close", is_default=True, is_cancel=True)]
    dialog.set_content(root)
    main_preview = NativeFramegraphPreviewSurface(
        context,
        main_image,
        main_root,
        model.core.capture,
        model.core.presenter,
    )
    depth_preview = NativeFramegraphPreviewSurface(
        context,
        depth_image,
        depth_root,
        model.core.depth_capture,
        model.core.presenter,
        force_depth=True,
    )
    result = NativeFramegraphDebugger(
        document=document,
        model=model,
        dialog=dialog,
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
        main_preview=main_preview,
        depth_preview=depth_preview,
        viewport=viewport,
        request_render=request_render,
        remove_pre_render_callback=remove_pre_render_callback,
        device=device,
    )
    weak_result = weakref.ref(result)

    def current() -> NativeFramegraphDebugger | None:
        return weak_result()

    target_combo.connect_changed(
        lambda index, _text: current().model.set_viewport_by_index(index)
        if current() is not None and not current()._updating
        else None
    )
    mode_combo.connect_changed(
        lambda index, _text: current().model.set_mode("inside" if index == 0 else "between")
        if current() is not None and not current()._updating
        else None
    )

    def pass_changed(index: int, _text: str) -> None:
        owner = current()
        if owner is None or owner._updating or not (0 <= index < len(owner.pass_indices)):
            return
        owner.model.set_selected_pass_by_index(owner.pass_indices[index])

    pass_combo.connect_changed(pass_changed)
    symbol_combo.connect_changed(
        lambda _index, text: current().model.set_selected_symbol(text or None)
        if current() is not None and not current()._updating
        else None
    )
    resource_combo.connect_changed(
        lambda _index, text: current().model.set_source_resource(text)
        if current() is not None and not current()._updating and text
        else None
    )
    channel_combo.connect_changed(
        lambda index, _text: current().model.set_channel_mode(index)
        if current() is not None and not current()._updating
        else None
    )
    pause_check.connect_changed(
        lambda checked: current().model.set_paused(checked)
        if current() is not None and not current()._updating
        else None
    )
    hdr_check.connect_changed(
        lambda checked: current().model.set_highlight_hdr(checked)
        if current() is not None and not current()._updating
        else None
    )
    analyze.connect_clicked(lambda: current().model.analyze_hdr() if current() is not None else None)
    refresh_stats.connect_clicked(
        lambda: current().model.refresh_render_stats() if current() is not None else None
    )
    refresh_depth.connect_clicked(lambda: current().refresh_depth() if current() is not None else None)

    def finished(_dialog_result) -> None:
        owner = current()
        if owner is not None:
            owner._deactivate()
            owner.request_render()

    dialog.connect_finished(finished)
    add_pre_render_callback(result.render_previews)
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
