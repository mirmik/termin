from __future__ import annotations

from typing import Optional, Callable, List, Tuple, TYPE_CHECKING

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QWindow

from termin.visualization.platform.backends.base import GraphicsBackend

if TYPE_CHECKING:
    from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend


class FramegraphDebugDialog(QtWidgets.QDialog):
    """
    Framegraph debugger window with two connection modes:

    1. "Between passes" — select intermediate resource (FBO) between passes.
       Uses FrameDebuggerPass to capture selected resource into offscreen FBO.

    2. "Inside pass" — select pass and its internal symbol.
       E.g., for ColorPass you can select a mesh and see state after rendering it.

    Architecture:
    - FrameGraphDebuggerCore (C++) handles capture and presentation
    - Capture phase: blit src FBO -> capture FBO (during render, same GL context)
    - Present phase: render capture FBO -> SDL window (after render, SDL context)
    """

    def __init__(
        self,
        window_backend: "SDLEmbeddedWindowBackend",
        graphics: GraphicsBackend,
        rendering_controller,
        on_request_update: Optional[Callable[[], None]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._window_backend = window_backend
        self._graphics = graphics
        self._rendering_controller = rendering_controller
        self._on_request_update = on_request_update
        self._resource_name = "debug"

        # C++ core (capture FBO created automatically on first capture)
        from termin._native.editor import FrameGraphDebuggerCore
        self._core = FrameGraphDebuggerCore()

        # Current selected viewport
        self._current_viewport = None
        self._viewports_list: List[Tuple[object, str]] = []

        # Current mode: "inside" (Frame passes) or "between" (Resources)
        self._mode = "inside"
        # Current selected pass (for "inside" mode)
        self._selected_pass: str | None = None
        # Current selected internal symbol (for "inside" mode)
        self._selected_symbol: str | None = None

        # Debug source resource name (for "between passes" mode)
        self._debug_source_res: str = ""
        # Paused state
        self._debug_paused: bool = False

        # FrameDebuggerPass for "between passes" mode (created dynamically)
        self._frame_debugger_pass = None

        # Channel mode and HDR
        self._channel_mode: int = 0  # 0=RGB, 1=R, 2=G, 3=B, 4=A
        self._highlight_hdr: bool = False

        # Depth label
        self._depth_label: QtWidgets.QLabel | None = None

        # SDL window for debug display
        self._sdl_window = window_backend.create_embedded_window(
            width=400, height=300, title="Framegraph Debug"
        )

        self._build_ui()

        # Timer for updating timing info (GPU results may arrive with delay)
        self._timing_timer = QtCore.QTimer(self)
        self._timing_timer.timeout.connect(self._update_timing_label)
        self._timing_timer.start(100)

    def _build_ui(self) -> None:
        self.setWindowTitle("Framegraph Debugger")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setModal(False)
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        layout = QtWidgets.QVBoxLayout(self)

        # ============ Top panel: settings left, pipeline right ============
        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # --- Left: settings ---
        settings_widget = QtWidgets.QWidget()
        settings_layout = QtWidgets.QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        # Viewport selection
        viewport_row = QtWidgets.QHBoxLayout()
        viewport_label = QtWidgets.QLabel("Viewport:")
        self._viewport_combo = QtWidgets.QComboBox()
        self._viewport_combo.currentIndexChanged.connect(self._on_viewport_selected)
        viewport_row.addWidget(viewport_label)
        viewport_row.addWidget(self._viewport_combo, 1)
        settings_layout.addLayout(viewport_row)

        # Render stats status line
        render_stats_row = QtWidgets.QHBoxLayout()
        self._render_stats_label = QtWidgets.QLabel()
        self._render_stats_label.setStyleSheet(
            "QLabel { background-color: #1a1a2e; padding: 3px 6px; border-radius: 3px; "
            "font-family: monospace; font-size: 10px; color: #b8b8b8; }"
        )
        render_stats_row.addWidget(self._render_stats_label, 1)
        self._refresh_stats_btn = QtWidgets.QPushButton("↻")
        self._refresh_stats_btn.setFixedWidth(24)
        self._refresh_stats_btn.setToolTip("Refresh render stats")
        self._refresh_stats_btn.clicked.connect(self._on_refresh_render_stats_clicked)
        render_stats_row.addWidget(self._refresh_stats_btn)
        settings_layout.addLayout(render_stats_row)

        # Mode selection group
        mode_group = QtWidgets.QGroupBox("Режим")
        mode_layout = QtWidgets.QHBoxLayout(mode_group)
        self._radio_inside = QtWidgets.QRadioButton("Фреймпассы")
        self._radio_between = QtWidgets.QRadioButton("Ресурсы")
        self._radio_inside.setChecked(True)
        self._radio_inside.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self._radio_inside)
        mode_layout.addWidget(self._radio_between)
        settings_layout.addWidget(mode_group)

        # "Resources" panel
        self._between_panel = QtWidgets.QWidget()
        between_layout = QtWidgets.QVBoxLayout(self._between_panel)
        between_layout.setContentsMargins(0, 0, 0, 0)

        resource_row = QtWidgets.QHBoxLayout()
        self._resource_label = QtWidgets.QLabel("Ресурс:")
        self._resource_combo = QtWidgets.QComboBox()
        self._resource_combo.currentTextChanged.connect(self._on_resource_selected)
        resource_row.addWidget(self._resource_label)
        resource_row.addWidget(self._resource_combo, 1)
        between_layout.addLayout(resource_row)

        # Pass that writes selected resource
        self._writer_pass_label = QtWidgets.QLabel()
        self._writer_pass_label.setStyleSheet(
            "QLabel { color: #8be9fd; font-weight: bold; }"
        )
        between_layout.addWidget(self._writer_pass_label)

        # HDR Analysis controls
        hdr_row = QtWidgets.QHBoxLayout()
        self._hdr_highlight_check = QtWidgets.QCheckBox("Highlight HDR")
        self._hdr_highlight_check.toggled.connect(self._on_hdr_highlight_toggled)
        hdr_row.addWidget(self._hdr_highlight_check)
        self._hdr_analyze_btn = QtWidgets.QPushButton("Analyze")
        self._hdr_analyze_btn.setFixedWidth(60)
        self._hdr_analyze_btn.clicked.connect(self._on_analyze_hdr_clicked)
        hdr_row.addWidget(self._hdr_analyze_btn)
        hdr_row.addStretch()
        between_layout.addLayout(hdr_row)

        # HDR statistics label
        self._hdr_stats_label = QtWidgets.QLabel()
        self._hdr_stats_label.setStyleSheet(
            "QLabel { background-color: #1a1a2e; padding: 4px; border-radius: 3px; "
            "font-family: monospace; font-size: 10px; }"
        )
        self._hdr_stats_label.setWordWrap(True)
        between_layout.addWidget(self._hdr_stats_label)

        settings_layout.addWidget(self._between_panel)
        self._between_panel.hide()

        # "Frame passes" panel
        self._inside_panel = QtWidgets.QWidget()
        inside_layout = QtWidgets.QVBoxLayout(self._inside_panel)
        inside_layout.setContentsMargins(0, 0, 0, 0)

        pass_row = QtWidgets.QHBoxLayout()
        self._pass_label = QtWidgets.QLabel("Пасс:")
        self._pass_combo = QtWidgets.QComboBox()
        self._pass_combo.currentTextChanged.connect(self._on_pass_selected)
        pass_row.addWidget(self._pass_label)
        pass_row.addWidget(self._pass_combo, 1)
        inside_layout.addLayout(pass_row)

        symbol_row = QtWidgets.QHBoxLayout()
        self._symbol_label = QtWidgets.QLabel("Символ:")
        self._symbol_combo = QtWidgets.QComboBox()
        self._symbol_combo.currentTextChanged.connect(self._on_symbol_selected)
        symbol_row.addWidget(self._symbol_label)
        symbol_row.addWidget(self._symbol_combo, 1)
        inside_layout.addLayout(symbol_row)

        # Timing info label
        self._timing_label = QtWidgets.QLabel()
        self._timing_label.setStyleSheet(
            "QLabel { background-color: #2a3a2a; padding: 4px; border-radius: 3px; "
            "font-family: monospace; font-size: 11px; }"
        )
        self._timing_label.hide()
        inside_layout.addWidget(self._timing_label)

        # Pass serialization view
        self._pass_serialization = QtWidgets.QTextEdit()
        self._pass_serialization.setReadOnly(True)
        self._pass_serialization.setMaximumHeight(150)
        self._pass_serialization.setStyleSheet(
            "QTextEdit { font-family: monospace; font-size: 10px; "
            "background-color: #1e1e1e; color: #d4d4d4; }"
        )
        inside_layout.addWidget(self._pass_serialization)

        settings_layout.addWidget(self._inside_panel)

        # FBO info
        self._fbo_info_label = QtWidgets.QLabel()
        self._fbo_info_label.setStyleSheet(
            "QLabel { background-color: #2a2a2a; padding: 4px; border-radius: 3px; }"
        )
        self._fbo_info_label.setWordWrap(True)
        settings_layout.addWidget(self._fbo_info_label)

        # Pause and channel selection
        controls_row = QtWidgets.QHBoxLayout()
        self._pause_check = QtWidgets.QCheckBox("Пауза")
        self._pause_check.toggled.connect(self._on_pause_toggled)
        controls_row.addWidget(self._pause_check)
        controls_row.addStretch()
        channel_label = QtWidgets.QLabel("Канал:")
        self._channel_combo = QtWidgets.QComboBox()
        self._channel_combo.addItems(["RGB", "R", "G", "B", "A"])
        self._channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        controls_row.addWidget(channel_label)
        controls_row.addWidget(self._channel_combo)
        settings_layout.addLayout(controls_row)

        settings_layout.addStretch()

        # --- Right: pipeline schedule ---
        pipeline_widget = QtWidgets.QWidget()
        pipeline_layout = QtWidgets.QVBoxLayout(pipeline_widget)
        pipeline_layout.setContentsMargins(0, 0, 0, 0)

        pipeline_title = QtWidgets.QLabel("Pipeline Schedule")
        pipeline_title.setStyleSheet("font-weight: bold;")
        pipeline_layout.addWidget(pipeline_title)

        self._pipeline_info = QtWidgets.QTextEdit()
        self._pipeline_info.setReadOnly(True)
        self._pipeline_info.setStyleSheet(
            "QTextEdit { font-family: monospace; font-size: 11px; "
            "background-color: #1e1e1e; color: #d4d4d4; }"
        )
        pipeline_layout.addWidget(self._pipeline_info)

        top_splitter.addWidget(settings_widget)
        top_splitter.addWidget(pipeline_widget)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)

        layout.addWidget(top_splitter)

        # ============ Viewer ============
        # Embed SDL window into Qt
        native_handle = self._sdl_window.native_handle
        self._qwindow = QWindow.fromWinId(native_handle)
        self._gl_container = QtWidgets.QWidget.createWindowContainer(self._qwindow, self)
        self._gl_container.setMinimumSize(200, 150)

        # Depth buffer with label
        depth_container = QtWidgets.QWidget()
        depth_layout = QtWidgets.QVBoxLayout(depth_container)
        depth_layout.setContentsMargins(0, 0, 0, 0)

        depth_header = QtWidgets.QHBoxLayout()
        depth_title = QtWidgets.QLabel("Depth Buffer")
        depth_header.addWidget(depth_title)
        depth_header.addStretch()
        self._refresh_depth_btn = QtWidgets.QPushButton("Refresh")
        self._refresh_depth_btn.setFixedWidth(60)
        self._refresh_depth_btn.clicked.connect(self._on_refresh_depth_clicked)
        depth_header.addWidget(self._refresh_depth_btn)
        depth_layout.addLayout(depth_header)

        self._depth_label = QtWidgets.QLabel()
        self._depth_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._depth_label.setMinimumSize(100, 100)
        self._depth_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        depth_layout.addWidget(self._depth_label, 1)

        viewer_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        viewer_splitter.addWidget(self._gl_container)
        viewer_splitter.addWidget(depth_container)
        viewer_splitter.setStretchFactor(0, 3)
        viewer_splitter.setStretchFactor(1, 2)

        layout.addWidget(viewer_splitter, 1)

        # Init
        self._update_viewport_list()
        self._update_resource_list()
        self._update_passes_list()
        self._sync_pause_state()
        self._update_render_stats()
        self._sync_initial_resource()

    # ============ Viewport selection ============

    def _on_viewport_selected(self, index: int) -> None:
        self._detach_frame_debugger_pass()

        if index < 0 or index >= len(self._viewports_list):
            self._current_viewport = None
            return
        self._current_viewport = self._viewports_list[index][0]

        self._update_resource_list()
        self._update_passes_list()
        self._sync_initial_resource()

        if self._mode == "between":
            self._attach_frame_debugger_pass()

    def _sync_initial_resource(self) -> None:
        if self._resource_combo.count() == 0:
            return
        self._resource_combo.setCurrentIndex(0)
        first_resource = self._resource_combo.currentText()
        if first_resource:
            self._debug_source_res = first_resource
            self._update_fbo_info()
            self._update_writer_pass_label()
            self._update_pipeline_info()

    def _update_viewport_list(self) -> None:
        if self._rendering_controller is None:
            return
        self._viewports_list = self._rendering_controller.get_all_viewports_info()
        self._viewport_combo.blockSignals(True)
        self._viewport_combo.clear()
        for viewport, label in self._viewports_list:
            self._viewport_combo.addItem(label)
        if self._viewports_list:
            self._viewport_combo.setCurrentIndex(0)
            self._current_viewport = self._viewports_list[0][0]
        self._viewport_combo.blockSignals(False)

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
        self._render_stats_label.setText(text)

    def _on_refresh_render_stats_clicked(self) -> None:
        self._update_render_stats()

    # ============ Data access helpers ============

    def _get_current_render_state(self):
        if self._current_viewport is None or self._rendering_controller is None:
            return None
        return self._rendering_controller.get_viewport_state(self._current_viewport)

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

    def _get_current_pipeline(self):
        if self._current_viewport is None:
            return None
        managed_by = self._current_viewport.managed_by_scene_pipeline
        if managed_by and self._current_viewport.scene is not None:
            return self._current_viewport.scene.get_pipeline(managed_by)
        return self._current_viewport.pipeline

    def _update_fbo_info(self) -> None:
        fbos = self._get_fbos()
        resource_name = self._resource_name if self._mode == "between" else self._debug_source_res
        resource = fbos.get(resource_name) if fbos else None

        if resource is None:
            self._fbo_info_label.setText(f"Ресурс '{resource_name}': не найден")
            return

        info_parts = [f"<b>{resource_name}</b>"]

        from termin.visualization.render.framegraph.resource import (
            SingleFBO,
            ShadowMapArrayResource,
        )
        from termin.graphics import FramebufferHandle

        if isinstance(resource, ShadowMapArrayResource):
            info_parts.append(f"Тип: ShadowMapArray ({len(resource)} entries)")
            if len(resource) > 0:
                entry = resource[0]
                fbo = entry.fbo
                if fbo is not None:
                    w, h = fbo.get_size()
                    info_parts.append(f"Размер: {w}×{h}")
        elif isinstance(resource, SingleFBO):
            info_parts.append("Тип: SingleFBO")
            fbo = resource._fbo
            if fbo is not None:
                w, h = fbo.get_size()
                samples = fbo.get_samples()
                is_msaa = fbo.is_msaa()
                fmt = fbo.get_format()
                info_parts.append(f"Размер: {w}×{h}")
                info_parts.append(f"Формат: {fmt}")
                if is_msaa:
                    info_parts.append(f"<span style='color: #ffaa00;'>MSAA: {samples}x</span>")
                else:
                    info_parts.append("MSAA: нет")
                info_parts.append(f"FBO ID: {fbo.get_fbo_id()}")
                gl_fmt = fbo.get_actual_gl_format()
                gl_w = fbo.get_actual_gl_width()
                gl_h = fbo.get_actual_gl_height()
                gl_s = fbo.get_actual_gl_samples()
                info_parts.append(f"<span style='color: #88ff88;'>GL: {gl_fmt} {gl_w}×{gl_h} s={gl_s}</span>")
                req_filter = fbo.get_filter()
                gl_filter = fbo.get_actual_gl_filter()
                info_parts.append(f"<span style='color: #88aaff;'>Filter: {req_filter} → {gl_filter}</span>")
        elif isinstance(resource, FramebufferHandle):
            info_parts.append("Тип: FramebufferHandle")
            w, h = resource.get_size()
            samples = resource.get_samples()
            is_msaa = resource.is_msaa()
            fmt = resource.get_format()
            info_parts.append(f"Размер: {w}×{h}")
            info_parts.append(f"Формат: {fmt}")
            if is_msaa:
                info_parts.append(f"<span style='color: #ffaa00;'>MSAA: {samples}x</span>")
            else:
                info_parts.append("MSAA: нет")
            info_parts.append(f"FBO ID: {resource.get_fbo_id()}")
            gl_fmt = resource.get_actual_gl_format()
            gl_w = resource.get_actual_gl_width()
            gl_h = resource.get_actual_gl_height()
            gl_s = resource.get_actual_gl_samples()
            info_parts.append(f"<span style='color: #88ff88;'>GL: {gl_fmt} {gl_w}×{gl_h} s={gl_s}</span>")
            req_filter = resource.get_filter()
            gl_filter = resource.get_actual_gl_filter()
            info_parts.append(f"<span style='color: #88aaff;'>Filter: {req_filter} → {gl_filter}</span>")
        else:
            info_parts.append(f"Тип: {type(resource).__name__}")

        self._fbo_info_label.setText(" | ".join(info_parts))

    def _update_writer_pass_label(self) -> None:
        resource_name = self._debug_source_res
        if not resource_name:
            self._writer_pass_label.setText("")
            return

        schedule = self._build_schedule(exclude_debugger=True)
        writer_pass = None
        for p in schedule:
            if resource_name in p.writes:
                writer_pass = p.pass_name
                break

        if writer_pass:
            self._writer_pass_label.setText(f"← {writer_pass}")
        else:
            self._writer_pass_label.setText("(read-only)")

    def _update_pass_serialization(self) -> None:
        import json

        if self._selected_pass is None:
            self._pass_serialization.clear()
            return

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            self._pass_serialization.setText("<no pipeline>")
            return

        for p in pipeline.passes:
            if p.pass_name == self._selected_pass:
                try:
                    data = p.serialize()
                    text = json.dumps(data, indent=2, ensure_ascii=False)
                    self._pass_serialization.setText(text)
                except Exception as e:
                    self._pass_serialization.setText(f"<error: {e}>")
                return

        self._pass_serialization.setText(f"<pass '{self._selected_pass}' not found>")

    # ============ Present phase ============

    def _present_capture(self) -> None:
        """Present phase: render capture FBO into SDL debug window."""
        if not self._core.capture.has_capture():
            return

        capture_fbo = self._core.capture_fbo
        if capture_fbo is None:
            return

        from sdl2 import video as sdl_video

        try:
            saved_context = sdl_video.SDL_GL_GetCurrentContext()
            saved_window = sdl_video.SDL_GL_GetCurrentWindow()

            self._sdl_window.make_current()

            dst_w, dst_h = self._sdl_window.framebuffer_size()
            self._graphics.bind_framebuffer(None)
            self._graphics.set_viewport(0, 0, dst_w, dst_h)

            self._core.presenter.render(
                self._graphics, capture_fbo,
                dst_w, dst_h,
                self._channel_mode, self._highlight_hdr
            )

            self._sdl_window.swap_buffers()

        except Exception as e:
            from termin._native import log
            log.error(f"[FramegraphDebugger] present failed: {e}")

        finally:
            if saved_window and saved_context:
                sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)

        self._core.capture.reset_capture()

    def _clear_debug_window(self) -> None:
        """Clear debug window to background color."""
        from sdl2 import video as sdl_video

        try:
            saved_context = sdl_video.SDL_GL_GetCurrentContext()
            saved_window = sdl_video.SDL_GL_GetCurrentWindow()

            self._sdl_window.make_current()

            from OpenGL import GL as gl
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            w, h = self._sdl_window.framebuffer_size()
            gl.glViewport(0, 0, w, h)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(0.1, 0.1, 0.1, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

            self._sdl_window.swap_buffers()

        except Exception as e:
            from termin._native import log
            log.error(f"[FramegraphDebugger] clear failed: {e}")

        finally:
            if saved_window and saved_context:
                sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)

    # ============ Depth buffer ============

    def _update_depth_image(self) -> None:
        """Read depth from capture FBO and display as QImage."""
        capture_fbo = self._core.capture_fbo
        if capture_fbo is None:
            return

        data_bytes, w, h = self._core.presenter.read_depth_normalized_with_size(
            self._graphics, capture_fbo
        )

        if not data_bytes or w == 0 or h == 0:
            if self._depth_label is not None:
                self._depth_label.setText("No depth data")
                self._depth_label.setStyleSheet("color: #ff6666;")
            return

        qimage = QtGui.QImage(
            data_bytes, w, h, w,
            QtGui.QImage.Format.Format_Grayscale8,
        )
        qimage = qimage.copy()

        if self._depth_label is not None:
            self._depth_label.setStyleSheet("")
            self._depth_label.setText("")
            pixmap = QtGui.QPixmap.fromImage(qimage)
            target_size = self._depth_label.size()
            if target_size.width() > 0 and target_size.height() > 0:
                pixmap = pixmap.scaled(
                    target_size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            self._depth_label.setPixmap(pixmap)

    # ============ Mode switching ============

    def _on_mode_changed(self, checked: bool) -> None:
        if self._radio_inside.isChecked():
            self._mode = "inside"
            self._between_panel.hide()
            self._inside_panel.show()
            self._clear_internal_symbol()
            self._detach_frame_debugger_pass()
            self._update_passes_list()
            self._update_pass_serialization()
            self._clear_debug_window()
        else:
            self._mode = "between"
            self._between_panel.show()
            self._inside_panel.hide()
            self._clear_internal_symbol()
            self._attach_frame_debugger_pass()

    def _attach_frame_debugger_pass(self) -> None:
        from termin._native import log

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            log.warn("[FrameDebugger] _attach: no pipeline")
            return

        self._detach_frame_debugger_pass()

        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

        def get_source():
            if self._debug_paused:
                return None
            return self._debug_source_res

        self._frame_debugger_pass = FrameDebuggerPass(
            get_source_res=get_source,
            pass_name="FrameDebugger",
        )

        # Pass FrameGraphCapture for blit during render
        self._frame_debugger_pass.set_capture(self._core.capture)

        pipeline.add_pass(self._frame_debugger_pass)
        log.info(f"[FrameDebugger] Attached FrameDebuggerPass, pipeline has {len(pipeline.passes)} passes")

        if self._on_request_update is not None:
            self._on_request_update()

    def _detach_frame_debugger_pass(self) -> None:
        pipeline = self._get_current_pipeline()
        if pipeline is not None:
            removed = pipeline.remove_passes_by_name("FrameDebugger")
            if removed > 0:
                from termin._native import log
                log.info(f"[FrameDebugger] Removed {removed} FrameDebuggerPass(es), pipeline has {len(pipeline.passes)} passes")

        self._frame_debugger_pass = None

        if self._on_request_update is not None:
            self._on_request_update()

    def _on_resource_selected(self, name: str) -> None:
        if not name:
            return
        self._debug_source_res = name
        self._resource_name = name
        self._update_fbo_info()
        self._update_writer_pass_label()
        self._update_pipeline_info()
        self._hdr_stats_label.setText("")

    def _on_hdr_highlight_toggled(self, checked: bool) -> None:
        self._highlight_hdr = checked

    def _on_analyze_hdr_clicked(self) -> None:
        capture_fbo = self._core.capture_fbo
        if capture_fbo is None:
            self._hdr_stats_label.setText("No capture available")
            return

        stats = self._core.presenter.compute_hdr_stats(self._graphics, capture_fbo)

        lines = []
        lines.append(f"<b>R:</b> {stats.min_r:.3f} - {stats.max_r:.3f} (avg: {stats.avg_r:.3f})")
        lines.append(f"<b>G:</b> {stats.min_g:.3f} - {stats.max_g:.3f} (avg: {stats.avg_g:.3f})")
        lines.append(f"<b>B:</b> {stats.min_b:.3f} - {stats.max_b:.3f} (avg: {stats.avg_b:.3f})")
        lines.append(f"<b>Max:</b> {stats.max_value:.3f}")

        if stats.hdr_percent > 0:
            hdr_color = "#ff69b4"
            lines.append(f"<span style='color: {hdr_color};'><b>HDR pixels:</b> {stats.hdr_pixel_count:,} ({stats.hdr_percent:.2f}%)</span>")
        else:
            lines.append(f"<b>HDR pixels:</b> 0 (0%)")

        self._hdr_stats_label.setText("<br>".join(lines))

    def _on_pass_selected(self, name: str) -> None:
        if not name:
            return
        self._clear_internal_symbol()
        idx = self._pass_combo.currentIndex()
        if idx >= 0:
            self._selected_pass = self._pass_combo.itemData(idx)
        self._selected_symbol = None
        self._update_symbols_list()
        self._update_pass_serialization()
        if self._symbol_combo.count() > 0:
            last_index = self._symbol_combo.count() - 1
            self._symbol_combo.setCurrentIndex(last_index)
            last_symbol = self._symbol_combo.itemText(last_index)
            self._on_symbol_selected(last_symbol)

    def _on_symbol_selected(self, name: str) -> None:
        if not name:
            return
        if self._selected_pass is None:
            return

        self._selected_symbol = name
        self._detach_frame_debugger_pass()
        self._set_pass_internal_symbol(self._selected_pass, name)
        self._timing_label.show()
        self._update_timing_label()

    def _update_timing_label(self) -> None:
        if self._timing_label is None:
            return

        if self._selected_pass is None or self._selected_symbol is None:
            self._timing_label.hide()
            return

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            self._timing_label.hide()
            return

        for p in pipeline.passes:
            if p.pass_name == self._selected_pass:
                timings = p.get_internal_symbols_with_timing()
                for t in timings:
                    if t.name == self._selected_symbol:
                        gpu_str = f"{t.gpu_time_ms:.3f}ms" if t.gpu_time_ms >= 0 else "pending..."
                        self._timing_label.setText(
                            f"CPU: {t.cpu_time_ms:.3f}ms | GPU: {gpu_str}"
                        )
                        self._timing_label.show()
                        return
                break

        self._timing_label.setText("Timing: no data")
        self._timing_label.show()

    def _on_pause_toggled(self, checked: bool) -> None:
        self._debug_paused = bool(checked)
        if self._on_request_update is not None:
            self._on_request_update()

    def _on_channel_changed(self, index: int) -> None:
        self._channel_mode = index

    def _on_refresh_depth_clicked(self) -> None:
        self._update_depth_image()

    def _clear_internal_symbol(self) -> None:
        from termin._native import log

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            return

        cleared_count = 0
        for p in pipeline.passes:
            try:
                p.set_debug_internal_point("")
                p.clear_debug_capture()
                cleared_count += 1
            except AttributeError:
                log.warn(f"[FrameDebugger] Pass '{p.pass_name}' does not support debug symbols")

        log.info(f"[FrameDebugger] _clear_internal_symbol: cleared {cleared_count} passes")

    def _set_pass_internal_symbol(self, pass_name: str, symbol: str | None) -> None:
        from termin._native import log

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            log.warn(f"[FrameDebugger] _set_pass_internal_symbol: no pipeline")
            return

        for p in pipeline.passes:
            if p.pass_name == pass_name:
                pass_type = type(p).__name__
                if symbol is None or symbol == "":
                    p.set_debug_internal_point("")
                    p.clear_debug_capture()
                    log.info(f"[FrameDebugger] Cleared debug symbol for pass '{pass_name}' ({pass_type})")
                else:
                    p.set_debug_internal_point(symbol)
                    # Set FrameGraphCapture on tc_pass so the pass can blit during render
                    p.set_debug_capture(self._core.capture)
                    # Set target so capture knows which pass is allowed to capture
                    log.info(f"[FrameDebugger] Set debug symbol '{symbol}' for pass '{pass_name}' ({pass_type})")

                if self._on_request_update is not None:
                    self._on_request_update()
                return

        log.warn(f"[FrameDebugger] Pass '{pass_name}' not found in pipeline")

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

    def _update_pipeline_info(self) -> None:
        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

        schedule = self._build_schedule()
        if not schedule:
            self._pipeline_info.setHtml("<i>Pipeline пуст</i>")
            return

        current_resource = self._debug_source_res

        lines = []
        for p in schedule:
            reads_str = ", ".join(sorted(p.reads)) if p.reads else "∅"
            writes_str = ", ".join(sorted(p.writes)) if p.writes else "∅"
            line = f"{p.pass_name}: {{{reads_str}}} → {{{writes_str}}}"

            if isinstance(p, FrameDebuggerPass):
                line = f"<span style='color: #ffb86c;'>► {line}</span>"
            elif current_resource and current_resource in p.writes:
                line = f"<span style='color: #50fa7b; font-weight: bold;'>● {line}</span>"

            lines.append(line)

        self._pipeline_info.setHtml("<pre>" + "<br>".join(lines) + "</pre>")

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

        current_items = [self._resource_combo.itemText(i) for i in range(self._resource_combo.count())]
        if current_items == names:
            return

        current = self._resource_combo.currentText()
        self._resource_combo.blockSignals(True)
        self._resource_combo.clear()
        for name in names:
            self._resource_combo.addItem(name)
        if current and current in names:
            index = self._resource_combo.findText(current)
            if index >= 0:
                self._resource_combo.setCurrentIndex(index)
        self._resource_combo.blockSignals(False)

    def _update_passes_list(self) -> None:
        previous_pass = self._selected_pass

        passes_info: List[Tuple[str, bool]] = []

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

        new_items = [(f"{name} ●" if has_sym else name, name) for name, has_sym in passes_info]

        current_items = [(self._pass_combo.itemText(i), self._pass_combo.itemData(i))
                         for i in range(self._pass_combo.count())]
        if current_items == new_items:
            return

        self._pass_combo.blockSignals(True)
        self._pass_combo.clear()

        selected_index = -1

        for index, (display_name, pass_name) in enumerate(new_items):
            self._pass_combo.addItem(display_name, pass_name)
            if previous_pass is not None and pass_name == previous_pass:
                selected_index = index

        self._pass_combo.blockSignals(False)

        if previous_pass is not None and selected_index < 0:
            self._pass_combo.blockSignals(True)
            self._pass_combo.setCurrentIndex(-1)
            self._pass_combo.blockSignals(False)
            return

        if previous_pass is None:
            if self._pass_combo.count() > 0:
                self._pass_combo.blockSignals(True)
                self._pass_combo.setCurrentIndex(0)
                self._selected_pass = self._pass_combo.itemData(0)
                self._pass_combo.blockSignals(False)
                self._update_symbols_list()
            return

        if selected_index >= 0:
            self._pass_combo.blockSignals(True)
            self._pass_combo.setCurrentIndex(selected_index)
            self._pass_combo.blockSignals(False)
            self._update_symbols_list()

    def _update_symbols_list(self) -> None:
        previous_symbol = self._selected_symbol

        symbols: List[str] = []

        if self._selected_pass:
            pipeline = self._get_current_pipeline()
            if pipeline is not None:
                for p in pipeline.passes:
                    if p.pass_name == self._selected_pass:
                        symbols = list(p.get_internal_symbols())
                        break

        current_items = [self._symbol_combo.itemText(i) for i in range(self._symbol_combo.count())]
        if current_items == symbols:
            return

        self._symbol_combo.blockSignals(True)
        self._symbol_combo.clear()

        selected_index = -1

        for index, sym in enumerate(symbols):
            self._symbol_combo.addItem(sym)
            if previous_symbol is not None and sym == previous_symbol:
                selected_index = index

        if previous_symbol is not None and selected_index < 0:
            self._symbol_combo.setCurrentIndex(-1)
        elif selected_index >= 0:
            self._symbol_combo.setCurrentIndex(selected_index)

        self._symbol_combo.setEnabled(len(symbols) > 0)
        self._symbol_combo.blockSignals(False)

    def _sync_pause_state(self) -> None:
        self._pause_check.blockSignals(True)
        self._pause_check.setChecked(self._debug_paused)
        self._pause_check.blockSignals(False)

    def set_initial_resource(self, resource_name: str) -> None:
        self._debug_source_res = resource_name
        self._resource_name = resource_name

        index = self._resource_combo.findText(resource_name)
        if index >= 0:
            self._resource_combo.blockSignals(True)
            self._resource_combo.setCurrentIndex(index)
            self._resource_combo.blockSignals(False)

    def debugger_request_update(self) -> None:
        """
        Called by editor after render update.
        Updates lists and presents captured texture to debug window.
        """
        if not self.isVisible():
            return

        self._update_resource_list()
        if self._mode == "inside":
            self._update_passes_list()
        self._sync_pause_state()
        self._update_fbo_info()

        # Present phase: render capture FBO into SDL debug window
        self._present_capture()

        # If inside mode with no symbol selected — show blank
        if self._mode == "inside" and not self._selected_symbol:
            self._clear_debug_window()

    def refresh_for_new_scene(self) -> None:
        saved_mode = self._mode
        saved_resource = self._debug_source_res
        saved_pass = self._selected_pass
        saved_symbol = self._selected_symbol

        self._detach_frame_debugger_pass()
        self._clear_internal_symbol()

        self._update_viewport_list()
        self._update_resource_list()
        self._update_passes_list()

        if saved_resource:
            index = self._resource_combo.findText(saved_resource)
            if index >= 0:
                self._resource_combo.setCurrentIndex(index)
                self._debug_source_res = saved_resource
                self._resource_name = saved_resource

        if saved_pass:
            for i in range(self._pass_combo.count()):
                if self._pass_combo.itemData(i) == saved_pass:
                    self._pass_combo.setCurrentIndex(i)
                    self._selected_pass = saved_pass
                    self._update_symbols_list()
                    break

        if saved_symbol and self._selected_pass:
            index = self._symbol_combo.findText(saved_symbol)
            if index >= 0:
                self._symbol_combo.setCurrentIndex(index)
                self._selected_symbol = saved_symbol
                if saved_mode == "inside":
                    self._set_pass_internal_symbol(self._selected_pass, saved_symbol)

        if saved_mode == "between":
            self._attach_frame_debugger_pass()

        self._update_fbo_info()
        self._update_writer_pass_label()
        self._update_pipeline_info()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._mode == "between":
            self._attach_frame_debugger_pass()
        else:
            self._update_passes_list()
            self._update_pass_serialization()

    def hideEvent(self, event) -> None:
        self._detach_frame_debugger_pass()
        self._clear_internal_symbol()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._detach_frame_debugger_pass()
        self._clear_internal_symbol()
        if self._sdl_window is not None:
            self._window_backend.remove_window(self._sdl_window)
            self._sdl_window.close()
            self._sdl_window = None
        super().closeEvent(event)
