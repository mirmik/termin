"""
MeshInspector — inspector panel for mesh files.

Displays mesh information: vertex count, triangle count, bounds, etc.
Also allows editing import settings (scale, axis mapping) via .meta files.
Includes 3D preview with orbit camera.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from termin.assets.mesh_asset import MeshAsset
    from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend
    from termin.visualization.platform.backends.base import GraphicsBackend


class MeshInspector(QWidget):
    """
    Inspector panel for mesh files.

    Shows:
    - 3D preview with orbit camera
    - File name
    - Vertex count
    - Triangle count
    - Has normals
    - Has UVs
    - Bounding box
    - File size
    - Import settings (scale, axis mapping)
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_spec_changed: Optional[Callable[[str], None]] = None,
        window_backend: Optional["SDLEmbeddedWindowBackend"] = None,
        graphics: Optional["GraphicsBackend"] = None,
    ):
        super().__init__(parent)

        self._mesh_asset: Optional["MeshAsset"] = None
        self._mesh_name: str = ""
        self._file_path: str = ""
        self._on_spec_changed = on_spec_changed
        self._window_backend = window_backend
        self._graphics = graphics
        self._preview_widget = None
        self._current_mesh3 = None

        # Render timer for preview updates
        self._render_timer: Optional[QTimer] = None

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QLabel("Mesh")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Preview widget (if backend available)
        # TODO: disabled for debugging - causes std::bad_alloc
        # if self._window_backend is not None and self._graphics is not None:
        #     from termin.editor.mesh_preview_widget import MeshPreviewWidget
        #
        #     self._preview_widget = MeshPreviewWidget(
        #         window_backend=self._window_backend,
        #         graphics=self._graphics,
        #         parent=self,
        #     )
        #     self._preview_widget.setMinimumHeight(180)
        #     layout.addWidget(self._preview_widget)
        #
        #     # Start render timer
        #     self._render_timer = QTimer(self)
        #     self._render_timer.timeout.connect(self._on_render_timer)
        #     self._render_timer.start(33)  # ~30 FPS

        # Info Form
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)

        # Name
        self._name_label = QLabel("-")
        form.addRow("Name:", self._name_label)

        # UUID
        self._uuid_label = QLabel("-")
        self._uuid_label.setStyleSheet("color: #888; font-family: monospace; font-size: 10px;")
        self._uuid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("UUID:", self._uuid_label)

        # Vertex count
        self._vertex_count_label = QLabel("-")
        form.addRow("Vertices:", self._vertex_count_label)

        # Triangle count
        self._triangle_count_label = QLabel("-")
        form.addRow("Triangles:", self._triangle_count_label)

        # Has normals
        self._has_normals_label = QLabel("-")
        form.addRow("Normals:", self._has_normals_label)

        # Has UVs
        self._has_uvs_label = QLabel("-")
        form.addRow("UVs:", self._has_uvs_label)

        # Bounds
        self._bounds_label = QLabel("-")
        self._bounds_label.setWordWrap(True)
        form.addRow("Bounds:", self._bounds_label)

        # File size
        self._file_size_label = QLabel("-")
        form.addRow("File Size:", self._file_size_label)

        # Path
        self._path_label = QLabel("-")
        self._path_label.setWordWrap(True)
        self._path_label.setStyleSheet("color: #888;")
        form.addRow("Path:", self._path_label)

        layout.addLayout(form)

        # Import Settings section
        settings_header = QLabel("Import Settings")
        settings_header.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 8px;")
        layout.addWidget(settings_header)

        settings_form = QFormLayout()
        settings_form.setContentsMargins(0, 0, 0, 0)
        settings_form.setSpacing(4)

        # Scale
        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(0.0001, 10000.0)
        self._scale_spin.setDecimals(4)
        self._scale_spin.setSingleStep(0.1)
        self._scale_spin.setValue(1.0)
        settings_form.addRow("Scale:", self._scale_spin)

        # Axis mapping
        axis_options = ["x", "y", "z", "-x", "-y", "-z"]

        self._axis_x_combo = QComboBox()
        self._axis_x_combo.addItems(axis_options)
        self._axis_x_combo.setCurrentText("x")
        settings_form.addRow("Axis X:", self._axis_x_combo)

        self._axis_y_combo = QComboBox()
        self._axis_y_combo.addItems(axis_options)
        self._axis_y_combo.setCurrentText("y")
        settings_form.addRow("Axis Y:", self._axis_y_combo)

        self._axis_z_combo = QComboBox()
        self._axis_z_combo.addItems(axis_options)
        self._axis_z_combo.setCurrentText("z")
        settings_form.addRow("Axis Z:", self._axis_z_combo)

        # UV settings
        self._flip_uv_v_checkbox = QCheckBox()
        self._flip_uv_v_checkbox.setToolTip(
            "Flip V coordinate (v = 1 - v).\n"
            "Use if texture appears upside down on the mesh."
        )
        settings_form.addRow("Flip UV V:", self._flip_uv_v_checkbox)

        layout.addLayout(settings_form)

        # Apply button
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)

        self._apply_btn = QPushButton("Apply && Save")
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        btn_layout.addWidget(self._apply_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addStretch()

    def set_mesh(self, mesh_asset: Optional["MeshAsset"], name: str = "") -> None:
        """Set mesh to inspect."""
        self._mesh_asset = mesh_asset
        self._mesh_name = name

        if mesh_asset is None:
            self._clear()
            return

        self._name_label.setText(name or mesh_asset.name or "-")

        # UUID from MeshAsset
        self._uuid_label.setText(mesh_asset.uuid if mesh_asset else "—")

        mesh3 = mesh_asset.mesh_data
        if mesh3 is None:
            self._clear()
            return

        # Store mesh3 for preview
        self._current_mesh3 = mesh3
        self._update_preview()

        # Vertex count
        vertex_count = mesh3.get_vertex_count()
        self._vertex_count_label.setText(f"{vertex_count:,}")

        # Triangle count
        triangle_count = mesh3.get_face_count()
        self._triangle_count_label.setText(f"{triangle_count:,}")

        # Has normals
        has_normals = mesh3.vertex_normals is not None
        self._has_normals_label.setText("Yes" if has_normals else "No")

        # Has UVs
        has_uvs = mesh3.uvs is not None
        self._has_uvs_label.setText("Yes" if has_uvs else "No")

        # Bounds
        self._update_bounds(mesh3)

        # File size and path
        source_path = mesh_asset.source_path if mesh_asset else None
        if source_path and os.path.exists(source_path):
            size = os.path.getsize(source_path)
            self._file_size_label.setText(self._format_size(size))
            self._path_label.setText(source_path)
            self._file_path = source_path
            # Load spec settings
            self._load_spec_from_file(source_path)
        else:
            self._file_size_label.setText("-")
            self._path_label.setText("-")
            self._file_path = ""
            self._reset_spec_fields()

    def _load_spec_from_file(self, mesh_path: str) -> None:
        """Load spec settings from .meta file."""
        from termin.loaders.mesh_spec import MeshSpec

        spec = MeshSpec.for_mesh_file(mesh_path)
        self._scale_spin.setValue(spec.scale)
        self._axis_x_combo.setCurrentText(spec.axis_x)
        self._axis_y_combo.setCurrentText(spec.axis_y)
        self._axis_z_combo.setCurrentText(spec.axis_z)
        self._flip_uv_v_checkbox.setChecked(spec.flip_uv_v)

    def _reset_spec_fields(self) -> None:
        """Reset spec fields to defaults."""
        self._scale_spin.setValue(1.0)
        self._axis_x_combo.setCurrentText("x")
        self._axis_y_combo.setCurrentText("y")
        self._axis_z_combo.setCurrentText("z")
        self._flip_uv_v_checkbox.setChecked(False)

    def _on_apply_clicked(self) -> None:
        """Save spec and notify for mesh reload."""
        if not self._file_path:
            return

        from termin.loaders.mesh_spec import MeshSpec

        spec = MeshSpec(
            scale=self._scale_spin.value(),
            axis_x=self._axis_x_combo.currentText(),
            axis_y=self._axis_y_combo.currentText(),
            axis_z=self._axis_z_combo.currentText(),
            flip_uv_v=self._flip_uv_v_checkbox.isChecked(),
        )
        spec.save_for_mesh(self._file_path)

        # Notify that spec changed
        if self._on_spec_changed is not None:
            self._on_spec_changed(self._file_path)

    def set_mesh_by_path(self, file_path: str) -> None:
        """Load and inspect mesh from file path."""
        from termin.loaders.mesh_spec import MeshSpec
        from termin.mesh.mesh import Mesh3
        from termin.assets.mesh_asset import MeshAsset

        name = os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1].lower()

        # Load spec
        spec = MeshSpec.for_mesh_file(file_path)

        try:
            if ext == ".stl":
                from termin.loaders.stl_loader import load_stl_file
                scene_data = load_stl_file(file_path, spec=spec)
            elif ext == ".obj":
                from termin.loaders.obj_loader import load_obj_file
                scene_data = load_obj_file(file_path, spec=spec)
            else:
                self._clear()
                self._name_label.setText(name)
                self._path_label.setText(f"Unsupported format: {ext}")
                return

            if not scene_data.meshes:
                self._clear()
                self._name_label.setText(name)
                self._path_label.setText("No meshes found")
                return

            mesh_data = scene_data.meshes[0]
            mesh3 = Mesh3(
                vertices=mesh_data.vertices,
                triangles=mesh_data.indices.reshape(-1, 3),
            )
            if mesh_data.normals is not None:
                mesh3.vertex_normals = mesh_data.normals
            if mesh_data.uvs is not None:
                mesh3.uvs = mesh_data.uvs

            mesh_asset = MeshAsset(mesh_data=mesh3, name=name, source_path=file_path)
            self.set_mesh(mesh_asset, name)

        except Exception as e:
            self._clear()
            self._name_label.setText(name)
            self._path_label.setText(f"Error: {e}")

    def _update_bounds(self, mesh3) -> None:
        """Calculate and display bounding box."""
        import numpy as np

        vertices = mesh3.vertices
        if vertices is None or len(vertices) == 0:
            self._bounds_label.setText("-")
            return

        min_bound = np.min(vertices, axis=0)
        max_bound = np.max(vertices, axis=0)
        size = max_bound - min_bound

        self._bounds_label.setText(
            f"Min: ({min_bound[0]:.2f}, {min_bound[1]:.2f}, {min_bound[2]:.2f})\n"
            f"Max: ({max_bound[0]:.2f}, {max_bound[1]:.2f}, {max_bound[2]:.2f})\n"
            f"Size: ({size[0]:.2f}, {size[1]:.2f}, {size[2]:.2f})"
        )

    def _clear(self) -> None:
        """Clear all fields."""
        self._mesh_asset = None
        self._mesh_name = ""
        self._file_path = ""
        self._current_mesh3 = None
        self._name_label.setText("-")
        self._uuid_label.setText("-")
        self._vertex_count_label.setText("-")
        self._triangle_count_label.setText("-")
        self._has_normals_label.setText("-")
        self._has_uvs_label.setText("-")
        self._bounds_label.setText("-")
        self._file_size_label.setText("-")
        self._path_label.setText("-")

        # Clear preview
        if self._preview_widget is not None:
            self._preview_widget.set_mesh(None)

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"

    def _on_render_timer(self) -> None:
        """Render preview on timer tick."""
        if self._preview_widget is not None and self.isVisible():
            self._preview_widget.render()

    def _update_preview(self) -> None:
        """Update preview with current mesh."""
        if self._preview_widget is not None and self._current_mesh3 is not None:
            self._preview_widget.set_mesh(self._current_mesh3)

    def hideEvent(self, event) -> None:
        """Stop render timer when hidden."""
        if self._render_timer is not None:
            self._render_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        """Start render timer when shown."""
        if self._render_timer is not None:
            self._render_timer.start(33)
        super().showEvent(event)

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._render_timer is not None:
            self._render_timer.stop()
            self._render_timer = None
        if self._preview_widget is not None:
            self._preview_widget.cleanup()
            self._preview_widget = None
