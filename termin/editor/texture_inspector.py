"""
TextureInspector — inspector panel for texture files.

Displays texture information: resolution, format, file size, etc.
Allows editing import settings (flip_y) via .spec files.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from termin.visualization.render.texture import Texture


class TextureInspector(QWidget):
    """
    Inspector panel for texture files.

    Shows:
    - File name
    - Resolution (width x height)
    - Channels
    - File size
    - Import settings (flip_y)
    - Preview thumbnail
    """

    # Emitted when texture settings change and texture needs reload
    texture_settings_changed = pyqtSignal(str)  # file_path

    PREVIEW_MAX_SIZE = 200

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._texture: Optional["Texture"] = None
        self._texture_name: str = ""
        self._file_path: str = ""
        self._updating: bool = False

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QLabel("Texture")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Preview
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(100)
        self._preview_label.setStyleSheet("background-color: #2a2a2a; border: 1px solid #555;")
        layout.addWidget(self._preview_label)

        # Form
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)

        # Name
        self._name_label = QLabel("-")
        form.addRow("Name:", self._name_label)

        # Resolution
        self._resolution_label = QLabel("-")
        form.addRow("Resolution:", self._resolution_label)

        # Channels
        self._channels_label = QLabel("-")
        form.addRow("Channels:", self._channels_label)

        # File size
        self._file_size_label = QLabel("-")
        form.addRow("File Size:", self._file_size_label)

        # Path
        self._path_label = QLabel("-")
        self._path_label.setWordWrap(True)
        self._path_label.setStyleSheet("color: #888;")
        form.addRow("Path:", self._path_label)

        # --- Import Settings ---
        settings_header = QLabel("Import Settings")
        settings_header.setStyleSheet("font-weight: bold; margin-top: 8px;")
        form.addRow(settings_header)

        # Flip X checkbox
        self._flip_x_checkbox = QCheckBox()
        self._flip_x_checkbox.setToolTip("Flip texture horizontally (mirror X).")
        self._flip_x_checkbox.stateChanged.connect(self._on_flip_x_changed)
        form.addRow("Flip X:", self._flip_x_checkbox)

        # Flip Y checkbox
        self._flip_y_checkbox = QCheckBox()
        self._flip_y_checkbox.setToolTip(
            "Flip texture vertically for OpenGL.\n"
            "Enable for most textures (OpenGL origin is bottom-left).\n"
            "Disable for textures already in OpenGL orientation."
        )
        self._flip_y_checkbox.stateChanged.connect(self._on_flip_y_changed)
        form.addRow("Flip Y:", self._flip_y_checkbox)

        # Transpose checkbox
        self._transpose_checkbox = QCheckBox()
        self._transpose_checkbox.setToolTip(
            "Transpose texture (swap X and Y axes).\n"
            "Use if texture appears rotated 90 degrees."
        )
        self._transpose_checkbox.stateChanged.connect(self._on_transpose_changed)
        form.addRow("Transpose:", self._transpose_checkbox)

        layout.addLayout(form)
        layout.addStretch()

    def set_texture(self, texture: Optional["Texture"], name: str = "") -> None:
        """Set texture to inspect."""
        self._updating = True
        try:
            self._texture = texture
            self._texture_name = name

            if texture is None:
                self._clear()
                return

            self._name_label.setText(name or "-")

            # Resolution
            if texture._size is not None:
                width, height = texture._size
                self._resolution_label.setText(f"{width} x {height}")
            else:
                self._resolution_label.setText("-")

            # Channels
            if texture._image_data is not None:
                if len(texture._image_data.shape) == 3:
                    channels = texture._image_data.shape[2]
                else:
                    channels = 1
                self._channels_label.setText(str(channels))
            else:
                self._channels_label.setText("-")

            # File size
            if texture.source_path and os.path.exists(texture.source_path):
                size = os.path.getsize(texture.source_path)
                self._file_size_label.setText(self._format_size(size))
                self._path_label.setText(texture.source_path)
                self._file_path = texture.source_path
            else:
                self._file_size_label.setText("-")
                self._path_label.setText("-")
                self._file_path = ""

            # Flip X setting
            self._flip_x_checkbox.setChecked(texture.flip_x)

            # Flip Y setting
            self._flip_y_checkbox.setChecked(texture.flip_y)

            # Transpose setting
            self._transpose_checkbox.setChecked(texture.transpose)

            # Preview
            self._update_preview(texture)
        finally:
            self._updating = False

    def set_texture_by_path(self, file_path: str) -> None:
        """Load and inspect texture from file path."""
        from termin.visualization.render.texture import Texture

        name = os.path.splitext(os.path.basename(file_path))[0]

        try:
            texture = Texture.from_file(file_path)
            self.set_texture(texture, name)
        except Exception as e:
            self._clear()
            self._name_label.setText(name)
            self._path_label.setText(f"Error: {e}")

    def _update_preview(self, texture: "Texture") -> None:
        """Update preview thumbnail."""
        pixmap = texture.get_preview_pixmap(self.PREVIEW_MAX_SIZE)
        if pixmap is not None:
            self._preview_label.setPixmap(pixmap)
        else:
            self._preview_label.clear()

    def _on_flip_x_changed(self, state: int) -> None:
        """Handle flip_x checkbox change."""
        if self._updating or not self._file_path:
            return
        self._save_spec_and_reload()

    def _on_flip_y_changed(self, state: int) -> None:
        """Handle flip_y checkbox change."""
        if self._updating or not self._file_path:
            return
        self._save_spec_and_reload()

    def _on_transpose_changed(self, state: int) -> None:
        """Handle transpose checkbox change."""
        if self._updating or not self._file_path:
            return
        self._save_spec_and_reload()

    def _save_spec_and_reload(self) -> None:
        """Save current settings to spec file and trigger reload."""
        from termin.loaders.texture_spec import TextureSpec

        spec = TextureSpec(
            flip_x=self._flip_x_checkbox.isChecked(),
            flip_y=self._flip_y_checkbox.isChecked(),
            transpose=self._transpose_checkbox.isChecked(),
        )
        spec.save_for_texture(self._file_path)

        # Emit signal to trigger texture reload
        self.texture_settings_changed.emit(self._file_path)

    def _clear(self) -> None:
        """Clear all fields."""
        self._texture = None
        self._texture_name = ""
        self._file_path = ""
        self._name_label.setText("-")
        self._resolution_label.setText("-")
        self._channels_label.setText("-")
        self._file_size_label.setText("-")
        self._path_label.setText("-")
        self._flip_x_checkbox.setChecked(False)
        self._flip_y_checkbox.setChecked(True)
        self._transpose_checkbox.setChecked(False)
        self._preview_label.clear()

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"
