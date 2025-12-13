"""
TextureInspector — inspector panel for texture files.

Displays texture information: resolution, format, file size, etc.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
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
    - Preview thumbnail
    """

    PREVIEW_MAX_SIZE = 200

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._texture: Optional["Texture"] = None
        self._texture_name: str = ""
        self._file_path: str = ""

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

        layout.addLayout(form)
        layout.addStretch()

    def set_texture(self, texture: Optional["Texture"], name: str = "") -> None:
        """Set texture to inspect."""
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

        # Preview
        self._update_preview(texture)

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
        if texture._image_data is None or texture._size is None:
            self._preview_label.clear()
            return

        width, height = texture._size
        data = texture._image_data

        # Create QImage from numpy data (RGBA, flipped back)
        if len(data.shape) == 3 and data.shape[2] == 4:
            # Flip vertically (texture was flipped for OpenGL)
            data_flipped = data[::-1, :, :].copy()
            qimage = QImage(
                data_flipped.data,
                width,
                height,
                width * 4,
                QImage.Format.Format_RGBA8888,
            )
        else:
            self._preview_label.clear()
            return

        pixmap = QPixmap.fromImage(qimage)

        # Scale to fit preview area
        scaled = pixmap.scaled(
            self.PREVIEW_MAX_SIZE,
            self.PREVIEW_MAX_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

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
        self._preview_label.clear()

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"
