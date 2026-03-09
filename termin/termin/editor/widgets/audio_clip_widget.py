"""AudioClip field widget for inspector panels."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QComboBox,
    QPushButton,
)
from PyQt6.QtCore import pyqtSignal

from termin.editor.widgets.field_widgets import FieldWidget

if TYPE_CHECKING:
    from termin.visualization.core.resources import ResourceManager
    from termin.audio.audio_clip import AudioClipHandle


class AudioClipFieldWidget(FieldWidget):
    """
    Widget for audio_clip fields.

    Displays a combo box with available audio clips and a play button
    for preview playback in the editor.
    """

    value_changed = pyqtSignal()

    def __init__(
        self,
        resources: Optional["ResourceManager"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._resources = resources
        self._preview_channel: int = -1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Combo box for clip selection
        self._combo = QComboBox()
        self._combo.setMinimumWidth(120)
        self._combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self._combo, stretch=1)

        # Play preview button
        self._play_btn = QPushButton("\u25B6")  # ▶ play symbol
        self._play_btn.setFixedWidth(28)
        self._play_btn.setToolTip("Preview audio clip")
        self._play_btn.clicked.connect(self._on_play_clicked)
        layout.addWidget(self._play_btn)

        # Stop button
        self._stop_btn = QPushButton("\u25A0")  # ■ stop symbol
        self._stop_btn.setFixedWidth(28)
        self._stop_btn.setToolTip("Stop preview")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        layout.addWidget(self._stop_btn)

        self._refresh_items()

    def set_resources(self, resources: "ResourceManager") -> None:
        """Set the resource manager and refresh the combo items."""
        self._resources = resources
        self._refresh_items()

    def _refresh_items(self) -> None:
        """Refresh the combo box with available audio clips."""
        self._combo.blockSignals(True)
        current_text = self._combo.currentText()
        self._combo.clear()

        # Add empty option
        self._combo.addItem("(None)", userData=None)

        if self._resources is not None:
            names = self._resources.list_audio_clip_names()
            for name in sorted(names):
                self._combo.addItem(name, userData=name)

        # Restore selection
        idx = self._combo.findText(current_text)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        else:
            self._combo.setCurrentIndex(0)  # (None)

        self._combo.blockSignals(False)

    def _on_selection_changed(self, index: int) -> None:
        """Handle combo selection change."""
        self._stop_preview()
        self.value_changed.emit()

    def _on_play_clicked(self) -> None:
        """Play preview of the selected audio clip."""
        handle = self.get_value()
        if handle is None:
            return

        # Get AudioClip from handle (lazy loads if needed)
        audio_clip = handle.get()
        if audio_clip is None or not audio_clip.is_valid:
            return

        from termin.audio.audio_engine import AudioEngine

        engine = AudioEngine.instance()
        if not engine.is_initialized:
            if not engine.initialize():
                return

        # Stop any previous preview
        self._stop_preview()

        # Play on any available channel
        self._preview_channel = engine.play_chunk(audio_clip.chunk, channel=-1, loops=0)

    def _on_stop_clicked(self) -> None:
        """Stop preview playback."""
        self._stop_preview()

    def _stop_preview(self) -> None:
        """Stop the current preview if playing."""
        if self._preview_channel >= 0:
            from termin.audio.audio_engine import AudioEngine

            engine = AudioEngine.instance()
            if engine.is_initialized:
                engine.stop_channel(self._preview_channel)
            self._preview_channel = -1

    def get_value(self) -> Optional["AudioClipHandle"]:
        """Get the currently selected AudioClipHandle."""
        name = self._combo.currentData()
        if not name or self._resources is None:
            return None
        return self._resources.get_audio_clip(name)

    def set_value(self, value: Any) -> None:
        """Set the widget value from an AudioClipHandle."""
        self._combo.blockSignals(True)

        # Refresh items in case the list changed
        self._refresh_items()

        if value is None:
            self._combo.setCurrentIndex(0)  # (None)
            self._combo.blockSignals(False)
            return

        # Find the name of the clip
        name = None
        if self._resources is not None:
            name = self._resources.find_audio_clip_name(value)

        if name is None:
            self._combo.setCurrentIndex(0)  # (None)
        else:
            idx = self._combo.findText(name)
            self._combo.setCurrentIndex(idx if idx >= 0 else 0)

        self._combo.blockSignals(False)

    def hideEvent(self, event) -> None:
        """Stop preview when widget is hidden."""
        self._stop_preview()
        super().hideEvent(event)
