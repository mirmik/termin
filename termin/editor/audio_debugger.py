"""Audio debugger dialog for visualizing audio levels."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6 import QtWidgets, QtCore, QtGui

if TYPE_CHECKING:
    pass


class LevelMeter(QtWidgets.QWidget):
    """
    Simple horizontal level meter widget.

    Displays a colored bar representing audio level (0.0 to 1.0).
    """

    def __init__(self, label: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._label = label
        self._level: float = 0.0
        self._peak: float = 0.0
        self._peak_hold_frames: int = 0

        self.setMinimumHeight(24)
        self.setMinimumWidth(200)

    def set_level(self, level: float) -> None:
        """Set current level (0.0 to 1.0)."""
        self._level = max(0.0, min(1.0, level))

        # Peak hold
        if self._level > self._peak:
            self._peak = self._level
            self._peak_hold_frames = 30  # Hold for ~0.5s at 60fps
        elif self._peak_hold_frames > 0:
            self._peak_hold_frames -= 1
        else:
            self._peak *= 0.95  # Decay

        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        margin = 2

        # Background
        painter.fillRect(rect, QtGui.QColor(40, 40, 40))

        # Calculate bar width
        bar_rect = rect.adjusted(margin, margin, -margin, -margin)
        level_width = int(bar_rect.width() * self._level)
        peak_x = int(bar_rect.width() * self._peak)

        # Level bar with gradient (green -> yellow -> red)
        if level_width > 0:
            gradient = QtGui.QLinearGradient(bar_rect.left(), 0, bar_rect.right(), 0)
            gradient.setColorAt(0.0, QtGui.QColor(0, 200, 0))      # Green
            gradient.setColorAt(0.6, QtGui.QColor(200, 200, 0))    # Yellow
            gradient.setColorAt(0.85, QtGui.QColor(200, 100, 0))   # Orange
            gradient.setColorAt(1.0, QtGui.QColor(200, 0, 0))      # Red

            level_rect = QtCore.QRect(
                bar_rect.left(),
                bar_rect.top(),
                level_width,
                bar_rect.height()
            )
            painter.fillRect(level_rect, gradient)

        # Peak indicator
        if self._peak > 0.01:
            peak_color = QtGui.QColor(255, 255, 255, 200)
            painter.setPen(QtGui.QPen(peak_color, 2))
            peak_x_pos = bar_rect.left() + peak_x
            painter.drawLine(peak_x_pos, bar_rect.top(), peak_x_pos, bar_rect.bottom())

        # Label
        if self._label:
            painter.setPen(QtGui.QColor(200, 200, 200))
            painter.drawText(
                rect.adjusted(6, 0, 0, 0),
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
                self._label
            )

        # Level text
        level_text = f"{self._level * 100:.0f}%"
        painter.setPen(QtGui.QColor(255, 255, 255))
        painter.drawText(
            rect.adjusted(0, 0, -6, 0),
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
            level_text
        )

        painter.end()


class ChannelInfoWidget(QtWidgets.QWidget):
    """Widget displaying info about an active audio channel."""

    def __init__(self, channel: int, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._channel = channel

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        # Channel number
        self._channel_label = QtWidgets.QLabel(f"Ch {channel}")
        self._channel_label.setFixedWidth(40)
        layout.addWidget(self._channel_label)

        # Status
        self._status_label = QtWidgets.QLabel("Playing")
        self._status_label.setFixedWidth(60)
        layout.addWidget(self._status_label)

        # Volume
        self._volume_label = QtWidgets.QLabel("100%")
        self._volume_label.setFixedWidth(40)
        layout.addWidget(self._volume_label)

        # Position info (angle/distance for 3D)
        self._position_label = QtWidgets.QLabel("")
        layout.addWidget(self._position_label, 1)

    def update_info(self, playing: bool, paused: bool, volume: float, angle: int = 0, distance: int = 0) -> None:
        """Update channel info display."""
        if paused:
            self._status_label.setText("Paused")
            self._status_label.setStyleSheet("color: orange;")
        elif playing:
            self._status_label.setText("Playing")
            self._status_label.setStyleSheet("color: lightgreen;")
        else:
            self._status_label.setText("Stopped")
            self._status_label.setStyleSheet("color: gray;")

        self._volume_label.setText(f"{volume * 100:.0f}%")

        if distance > 0:
            self._position_label.setText(f"Angle: {angle}\u00b0, Dist: {distance}")
        else:
            self._position_label.setText("2D")


class AudioDebugDialog(QtWidgets.QDialog):
    """
    Debug dialog for audio system.

    Shows:
    - Master volume level
    - Left/Right channel output levels
    - List of active channels with their status
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build_ui()

        # Update timer
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_levels)
        self._timer.setInterval(33)  # ~30 fps

    def _build_ui(self) -> None:
        self.setWindowTitle("Audio Debugger")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setModal(False)
        self.setMinimumSize(350, 300)

        layout = QtWidgets.QVBoxLayout(self)

        # Engine status
        status_group = QtWidgets.QGroupBox("Audio Engine")
        status_layout = QtWidgets.QFormLayout(status_group)

        self._engine_status = QtWidgets.QLabel("Not initialized")
        status_layout.addRow("Status:", self._engine_status)

        self._master_volume_label = QtWidgets.QLabel("100%")
        status_layout.addRow("Master Volume:", self._master_volume_label)

        self._channels_label = QtWidgets.QLabel("0 / 32")
        status_layout.addRow("Active Channels:", self._channels_label)

        layout.addWidget(status_group)

        # Output levels
        levels_group = QtWidgets.QGroupBox("Output Levels")
        levels_layout = QtWidgets.QVBoxLayout(levels_group)

        self._left_meter = LevelMeter("L")
        self._right_meter = LevelMeter("R")

        levels_layout.addWidget(self._left_meter)
        levels_layout.addWidget(self._right_meter)

        layout.addWidget(levels_group)

        # Active channels list
        channels_group = QtWidgets.QGroupBox("Active Channels")
        channels_layout = QtWidgets.QVBoxLayout(channels_group)

        self._channels_scroll = QtWidgets.QScrollArea()
        self._channels_scroll.setWidgetResizable(True)
        self._channels_scroll.setMinimumHeight(100)

        self._channels_container = QtWidgets.QWidget()
        self._channels_container_layout = QtWidgets.QVBoxLayout(self._channels_container)
        self._channels_container_layout.setContentsMargins(0, 0, 0, 0)
        self._channels_container_layout.setSpacing(2)
        self._channels_container_layout.addStretch()

        self._channels_scroll.setWidget(self._channels_container)
        channels_layout.addWidget(self._channels_scroll)

        layout.addWidget(channels_group)

        # Channel widgets cache
        self._channel_widgets: dict[int, ChannelInfoWidget] = {}

    def _update_levels(self) -> None:
        """Update all audio level displays."""
        from termin.audio.audio_engine import AudioEngine

        engine = AudioEngine.instance()

        # Engine status
        if engine.is_initialized:
            self._engine_status.setText("Initialized")
            self._engine_status.setStyleSheet("color: lightgreen;")
        else:
            self._engine_status.setText("Not initialized")
            self._engine_status.setStyleSheet("color: orange;")
            self._left_meter.set_level(0)
            self._right_meter.set_level(0)
            return

        # Master volume
        master_vol = engine.get_master_volume()
        self._master_volume_label.setText(f"{master_vol * 100:.0f}%")

        # Count active channels and calculate approximate levels
        active_count = 0
        left_level = 0.0
        right_level = 0.0

        for ch in range(engine.num_channels):
            if engine.is_channel_playing(ch):
                active_count += 1
                vol = engine.get_channel_volume(ch)

                # Approximate stereo levels based on volume
                # (SDL_mixer doesn't expose actual audio levels, so this is simulated)
                left_level = max(left_level, vol * master_vol)
                right_level = max(right_level, vol * master_vol)

                # Update channel widget
                self._ensure_channel_widget(ch)
                widget = self._channel_widgets.get(ch)
                if widget:
                    paused = engine.is_channel_paused(ch)
                    widget.update_info(True, paused, vol)
                    widget.show()
            else:
                # Hide inactive channel widget
                widget = self._channel_widgets.get(ch)
                if widget:
                    widget.hide()

        # Update levels
        self._left_meter.set_level(left_level)
        self._right_meter.set_level(right_level)

        # Update channel count
        self._channels_label.setText(f"{active_count} / {engine.num_channels}")

    def _ensure_channel_widget(self, channel: int) -> None:
        """Ensure widget exists for channel."""
        if channel not in self._channel_widgets:
            widget = ChannelInfoWidget(channel)
            self._channel_widgets[channel] = widget
            # Insert before stretch
            self._channels_container_layout.insertWidget(
                self._channels_container_layout.count() - 1,
                widget
            )

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Start update timer when shown."""
        super().showEvent(event)
        self._timer.start()
        self._update_levels()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        """Stop update timer when hidden."""
        self._timer.stop()
        super().hideEvent(event)
