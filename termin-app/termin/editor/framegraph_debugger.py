from __future__ import annotations

from typing import Optional, Callable, List, Tuple, TYPE_CHECKING

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QWindow

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
        rendering_controller,
        on_request_update: Optional[Callable[[], None]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._window_backend = window_backend
        self._rendering_controller = rendering_controller
        self._on_request_update = on_request_update
        self._resource_name = "debug"

        # C++ core (capture FBO created automatically on first capture)
        from termin._native.editor import FrameGraphDebuggerCore
        self._core = FrameGraphDebuggerCore()

        # UI-agnostic state + pipeline-connect logic lives in the model.
        # This dialog just owns the widgets + Qt-specific SDL debug window
        # rendering; state reads/writes go through self._model.
        from termin.editor_core.framegraph_debugger_model import FramegraphDebuggerModel
        self._model = FramegraphDebuggerModel(
            rendering_controller=rendering_controller,
            core=self._core,
            on_request_update=on_request_update,
        )

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

    # ------------------------------------------------------------------
    # Model-backed properties (delegate state to FramegraphDebuggerModel)
    # ------------------------------------------------------------------

    @property
    def _current_viewport(self):
        return self._model.current_viewport

    @_current_viewport.setter
    def _current_viewport(self, _v):
        # write goes through model.set_viewport_by_index; stray assignments
        # from legacy code paths are benign because model is the source of truth
        pass

    @property
    def _viewports_list(self):
        return self._model.viewports

    @_viewports_list.setter
    def _viewports_list(self, _v):
        pass

    @property
    def _mode(self) -> str:
        return self._model.mode

    @_mode.setter
    def _mode(self, value: str) -> None:
        self._model.set_mode(value)

    @property
    def _selected_pass(self) -> str | None:
        return self._model.selected_pass

    @_selected_pass.setter
    def _selected_pass(self, value: str | None) -> None:
        self._model.set_selected_pass(value)

    @property
    def _selected_symbol(self) -> str | None:
        return self._model.selected_symbol

    @_selected_symbol.setter
    def _selected_symbol(self, value: str | None) -> None:
        self._model.set_selected_symbol(value)

    @property
    def _debug_source_res(self) -> str:
        return self._model.debug_source_res

    @_debug_source_res.setter
    def _debug_source_res(self, value: str) -> None:
        self._model.set_source_resource(value)

    @property
    def _debug_paused(self) -> bool:
        return self._model.debug_paused

    @_debug_paused.setter
    def _debug_paused(self, value: bool) -> None:
        self._model.set_paused(value)

    @property
    def _channel_mode(self) -> int:
        return self._model.channel_mode

    @_channel_mode.setter
    def _channel_mode(self, value: int) -> None:
        self._model.set_channel_mode(value)

    @property
    def _highlight_hdr(self) -> bool:
        return self._model.highlight_hdr

    @_highlight_hdr.setter
    def _highlight_hdr(self, value: bool) -> None:
        self._model.set_highlight_hdr(value)

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

    # ============ Centralized connection management ============

    def _disconnect(self) -> None:
        self._model.disconnect()

    def _connect(self) -> None:
        # Model's _connect is private (driven by _reconnect internally).
        # Call _reconnect to re-establish the pipeline link.
        self._model._reconnect()

    def _reconnect(self) -> None:
        self._model._reconnect()

    # ============ Viewport selection ============

    def _on_viewport_selected(self, index: int) -> None:
        # Pushes viewport into model AND triggers reconnect + list rebuild
        # on the model side; view widgets refresh below.
        self._model.set_viewport_by_index(index)
        self._update_resource_list()
        self._update_passes_list()
        self._sync_initial_resource()

    def _sync_initial_resource(self) -> None:
        if self._resource_combo.count() == 0:
            return
        self._resource_combo.blockSignals(True)
        self._resource_combo.setCurrentIndex(0)
        self._resource_combo.blockSignals(False)
        first_resource = self._resource_combo.currentText()
        if first_resource:
            self._debug_source_res = first_resource
            self._update_fbo_info()
            self._update_writer_pass_label()
            self._update_pipeline_info()

    def _update_viewport_list(self) -> None:
        if self._rendering_controller is None:
            return
        # Model owns the viewports list; pull fresh from rendering controller
        # and rebuild the Qt combo from the resulting snapshot.
        self._model.refresh_viewports()
        viewports = self._model.viewports
        self._viewport_combo.blockSignals(True)
        self._viewport_combo.clear()
        for _viewport, label in viewports:
            self._viewport_combo.addItem(label)
        if viewports:
            self._viewport_combo.setCurrentIndex(0)
        self._viewport_combo.blockSignals(False)

    def _update_render_stats(self) -> None:
        self._render_stats_label.setText(self._model.format_render_stats())

    def _on_refresh_render_stats_clicked(self) -> None:
        self._update_render_stats()

    # ============ Data access helpers ============

    def _get_current_render_state(self):
        if self._current_viewport is None or self._rendering_controller is None:
            return None
        return self._rendering_controller.get_viewport_state(self._current_viewport)

    def _get_current_pipeline(self):
        return self._model.get_current_pipeline()

    def _update_fbo_info(self) -> None:
        self._fbo_info_label.setText(self._model.format_fbo_info())

    def _update_writer_pass_label(self) -> None:
        self._writer_pass_label.setText(self._model.format_writer_pass())

    def _update_pass_serialization(self) -> None:
        self._pass_serialization.setText(self._model.format_pass_json())

    # ============ Present phase ============

    def _present_capture(self) -> None:
        """Present phase: render capture FBO into SDL debug window."""
        from tcbase import log

        if not self._core.capture.has_capture():
            log.debug("[FramegraphDebugger] _present_capture: no capture")
            return

        capture_tex = self._core.capture_tex
        if not capture_tex:
            log.warn("[FramegraphDebugger] _present_capture: capture_tex is invalid")
            return

        log.debug("[FramegraphDebugger] _present_capture: presenting")

        from sdl2 import video as sdl_video
        from termin.visualization.render.manager import RenderingManager

        render_engine = RenderingManager.instance().render_engine
        if render_engine is None:
            log.warn("[FramegraphDebugger] _present_capture: no render engine")
            return
        render_engine.ensure_tgfx2()
        ctx2 = render_engine.tgfx2_ctx
        if ctx2 is None:
            log.warn("[FramegraphDebugger] _present_capture: no ctx2")
            return

        try:
            saved_context = sdl_video.SDL_GL_GetCurrentContext()
            saved_window = sdl_video.SDL_GL_GetCurrentWindow()

            self._sdl_window.make_current()

            dst_w, dst_h = self._sdl_window.framebuffer_size()
            src_w = self._core.capture.width
            src_h = self._core.capture.height

            # Qt-editor framegraph debugger is deprecated (Phase 17 cleanup).
            # Blit the capture texture into the SDL debug window's
            # default framebuffer (GL id = 0). Channel_mode /
            # highlight_hdr are not supported on this fallback path.
            ctx2.blit_to_external_fbo(
                0, capture_tex,
                0, 0, src_w, src_h,
                0, 0, dst_w, dst_h,
            )

            self._sdl_window.swap_buffers()

        except Exception as e:
            from tcbase import log
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
            from tcbase import log
            log.error(f"[FramegraphDebugger] clear failed: {e}")

        finally:
            if saved_window and saved_context:
                sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)

    # ============ Depth buffer ============

    def _update_depth_image(self) -> None:
        """Read depth from capture texture and display as QImage."""
        capture_tex = self._core.capture_tex
        if not capture_tex:
            return

        from termin.visualization.render.manager import RenderingManager
        render_engine = RenderingManager.instance().render_engine
        if render_engine is None:
            return
        render_engine.ensure_tgfx2()
        device = render_engine.tgfx2_device
        if device is None:
            return

        result = self._core.presenter.read_depth_normalized(device, capture_tex)
        if result is None:
            if self._depth_label is not None:
                self._depth_label.setText("No depth data")
                self._depth_label.setStyleSheet("color: #ff6666;")
            return
        data_bytes, w, h = result

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

    # ============ UI event handlers ============

    def _on_mode_changed(self, checked: bool) -> None:
        if self._radio_inside.isChecked():
            self._mode = "inside"
            self._between_panel.hide()
            self._inside_panel.show()
            self._update_passes_list()
            self._update_pass_serialization()
        else:
            self._mode = "between"
            self._between_panel.show()
            self._inside_panel.hide()
        self._reconnect()

    def _on_resource_selected(self, name: str) -> None:
        if not name:
            return
        self._debug_source_res = name
        self._resource_name = name
        self._update_fbo_info()
        self._update_writer_pass_label()
        self._update_pipeline_info()
        self._hdr_stats_label.setText("")
        self._reconnect()

    def _on_hdr_highlight_toggled(self, checked: bool) -> None:
        self._highlight_hdr = checked
        if self._on_request_update is not None:
            self._on_request_update()

    def _on_analyze_hdr_clicked(self) -> None:
        capture_tex = self._core.capture_tex
        if not capture_tex:
            self._hdr_stats_label.setText("No capture available")
            return

        from termin.visualization.render.manager import RenderingManager
        render_engine = RenderingManager.instance().render_engine
        if render_engine is None:
            self._hdr_stats_label.setText("No render engine")
            return
        render_engine.ensure_tgfx2()
        device = render_engine.tgfx2_device
        if device is None:
            self._hdr_stats_label.setText("No tgfx2 device")
            return

        stats = self._core.presenter.compute_hdr_stats(device, capture_tex)

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
        idx = self._pass_combo.currentIndex()
        if idx >= 0:
            self._selected_pass = self._pass_combo.itemData(idx)
        self._selected_symbol = None
        self._update_symbols_list()
        self._update_pass_serialization()
        # Auto-select last symbol if available
        if self._symbol_combo.count() > 0:
            last_index = self._symbol_combo.count() - 1
            self._symbol_combo.blockSignals(True)
            self._symbol_combo.setCurrentIndex(last_index)
            self._symbol_combo.blockSignals(False)
            self._selected_symbol = self._symbol_combo.itemText(last_index)
        if self._selected_symbol:
            self._timing_label.show()
            self._update_timing_label()
        else:
            self._timing_label.hide()
        self._reconnect()

    def _on_symbol_selected(self, name: str) -> None:
        if not name or self._selected_pass is None:
            return
        self._selected_symbol = name
        self._timing_label.show()
        self._update_timing_label()
        self._reconnect()

    def _update_timing_label(self) -> None:
        if self._timing_label is None:
            return
        text = self._model.format_timing()
        if not text:
            self._timing_label.hide()
            return
        self._timing_label.setText(text)
        self._timing_label.show()

    def _on_pause_toggled(self, checked: bool) -> None:
        self._debug_paused = bool(checked)
        self._reconnect()

    def _on_channel_changed(self, index: int) -> None:
        self._channel_mode = index
        if self._on_request_update is not None:
            self._on_request_update()

    def _on_refresh_depth_clicked(self) -> None:
        self._update_depth_image()

    def _build_schedule(self, exclude_debugger: bool = False) -> list:
        return self._model._build_schedule(exclude_debugger)

    def _update_pipeline_info(self) -> None:
        text = self._model.format_pipeline_info()
        if text == "<i>Pipeline пуст</i>":
            self._pipeline_info.setHtml(text)
        else:
            # Model returns HTML (<pre>...<br>...</pre>); pass through.
            self._pipeline_info.setHtml(text)

    def _update_resource_list(self) -> None:
        self._update_pipeline_info()

        names = self._model.get_resources()
        current_items = [self._resource_combo.itemText(i)
                         for i in range(self._resource_combo.count())]
        if current_items == names:
            return

        current = self._resource_combo.currentText()
        self._resource_combo.blockSignals(True)
        self._resource_combo.clear()
        for name in names:
            self._resource_combo.addItem(name)
        if current and current in names:
            self._resource_combo.setCurrentIndex(self._resource_combo.findText(current))
        self._resource_combo.blockSignals(False)

    def _update_passes_list(self) -> None:
        previous_pass = self._selected_pass
        passes_info = self._model.get_passes()
        new_items = [(f"{name} ●" if has_sym else name, name)
                     for name, has_sym in passes_info]

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
        symbols = self._model.get_symbols()

        current_items = [self._symbol_combo.itemText(i)
                         for i in range(self._symbol_combo.count())]
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
        saved_resource = self._debug_source_res
        saved_pass = self._selected_pass
        saved_symbol = self._selected_symbol

        self._disconnect()

        self._update_viewport_list()
        self._update_resource_list()
        self._update_passes_list()

        # Restore selections (without triggering signals)
        if saved_resource:
            index = self._resource_combo.findText(saved_resource)
            if index >= 0:
                self._resource_combo.blockSignals(True)
                self._resource_combo.setCurrentIndex(index)
                self._resource_combo.blockSignals(False)
                self._debug_source_res = saved_resource
                self._resource_name = saved_resource

        if saved_pass:
            for i in range(self._pass_combo.count()):
                if self._pass_combo.itemData(i) == saved_pass:
                    self._pass_combo.blockSignals(True)
                    self._pass_combo.setCurrentIndex(i)
                    self._pass_combo.blockSignals(False)
                    self._selected_pass = saved_pass
                    self._update_symbols_list()
                    break

        if saved_symbol and self._selected_pass:
            index = self._symbol_combo.findText(saved_symbol)
            if index >= 0:
                self._symbol_combo.blockSignals(True)
                self._symbol_combo.setCurrentIndex(index)
                self._symbol_combo.blockSignals(False)
                self._selected_symbol = saved_symbol

        self._reconnect()
        self._update_fbo_info()
        self._update_writer_pass_label()
        self._update_pipeline_info()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_passes_list()
        self._update_pass_serialization()
        self._reconnect()

    def hideEvent(self, event) -> None:
        self._disconnect()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._disconnect()
        if self._sdl_window is not None:
            self._window_backend.remove_window(self._sdl_window)
            self._sdl_window.close()
            self._sdl_window = None
        super().closeEvent(event)
