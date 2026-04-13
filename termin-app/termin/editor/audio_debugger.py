"""Audio debugger dialog for audio system inspection."""

from __future__ import annotations

from typing import Optional

from PyQt6 import QtWidgets, QtCore, QtGui


class ChannelInfoWidget(QtWidgets.QWidget):
    """Widget displaying info about an active audio channel."""

    def __init__(self, channel: int, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._channel = channel

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(12)

        # Channel number
        self._channel_label = QtWidgets.QLabel(f"Ch {channel}")
        self._channel_label.setFixedWidth(35)
        layout.addWidget(self._channel_label)

        # Status
        self._status_label = QtWidgets.QLabel("Playing")
        self._status_label.setFixedWidth(50)
        layout.addWidget(self._status_label)

        # Volume
        self._volume_label = QtWidgets.QLabel("Vol: 100%")
        self._volume_label.setFixedWidth(70)
        layout.addWidget(self._volume_label)

        # Angle
        self._angle_label = QtWidgets.QLabel("Angle: 0\u00b0")
        self._angle_label.setFixedWidth(75)
        layout.addWidget(self._angle_label)

        # Distance
        self._distance_label = QtWidgets.QLabel("Dist: 0")
        self._distance_label.setFixedWidth(60)
        layout.addWidget(self._distance_label)

        layout.addStretch()

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

        self._volume_label.setText(f"Vol: {volume * 100:.0f}%")
        self._angle_label.setText(f"Angle: {angle}\u00b0")
        self._distance_label.setText(f"Dist: {distance}")


class AudioDebugDialog(QtWidgets.QDialog):
    """
    Debug dialog for audio system.

    Shows:
    - Audio engine status
    - Master volume
    - Active channels with volume, angle, distance
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build_ui()

        # Update timer
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_channels)
        self._timer.setInterval(100)  # 10 fps is enough for debug info

    def _build_ui(self) -> None:
        self.setWindowTitle("Audio Debugger")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setModal(False)
        self.setMinimumSize(400, 250)

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

        # Active channels list
        channels_group = QtWidgets.QGroupBox("Active Channels")
        channels_layout = QtWidgets.QVBoxLayout(channels_group)

        self._channels_scroll = QtWidgets.QScrollArea()
        self._channels_scroll.setWidgetResizable(True)
        self._channels_scroll.setMinimumHeight(120)

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

    def _update_channels(self) -> None:
        """Update all channel displays."""
        from termin.audio.audio_engine import AudioEngine

        engine = AudioEngine.instance()

        # Engine status
        if engine.is_initialized:
            self._engine_status.setText("Initialized")
            self._engine_status.setStyleSheet("color: lightgreen;")
        else:
            self._engine_status.setText("Not initialized")
            self._engine_status.setStyleSheet("color: orange;")
            return

        # Master volume
        master_vol = engine.get_master_volume()
        self._master_volume_label.setText(f"{master_vol * 100:.0f}%")

        # Count active channels
        active_count = 0

        for ch in range(engine.num_channels):
            if engine.is_channel_playing(ch):
                active_count += 1
                vol = engine.get_channel_volume(ch)
                angle, distance = engine.get_channel_position(ch)

                # Update channel widget
                self._ensure_channel_widget(ch)
                widget = self._channel_widgets.get(ch)
                if widget:
                    paused = engine.is_channel_paused(ch)
                    widget.update_info(True, paused, vol, angle, distance)
                    widget.show()
            else:
                # Hide inactive channel widget
                widget = self._channel_widgets.get(ch)
                if widget:
                    widget.hide()

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
        self._update_channels()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        """Stop update timer when hidden."""
        self._timer.stop()
        super().hideEvent(event)
