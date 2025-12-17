"""
GLBInspector - inspector panel for GLB files.

Displays GLB information: meshes, textures, animations, skeleton.
Allows editing import settings including normalize scale via .spec files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from termin.loaders.glb_loader import GLBSceneData


class GLBInspector(QWidget):
    """
    Inspector panel for GLB files.

    Shows:
    - File name and path
    - Mesh count and details
    - Texture count
    - Animation count and names
    - Skeleton info (bone count)
    - Root node scale
    - Normalize Scale option
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_spec_changed: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)

        self._scene_data: Optional["GLBSceneData"] = None
        self._file_path: str = ""
        self._on_spec_changed = on_spec_changed

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QLabel("GLB File")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Info Form
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)

        # Name
        self._name_label = QLabel("-")
        form.addRow("Name:", self._name_label)

        # File size
        self._file_size_label = QLabel("-")
        form.addRow("File Size:", self._file_size_label)

        # Path
        self._path_label = QLabel("-")
        self._path_label.setWordWrap(True)
        self._path_label.setStyleSheet("color: #888;")
        form.addRow("Path:", self._path_label)

        layout.addLayout(form)

        # Content section
        content_header = QLabel("Content")
        content_header.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 8px;")
        layout.addWidget(content_header)

        content_form = QFormLayout()
        content_form.setContentsMargins(0, 0, 0, 0)
        content_form.setSpacing(4)

        # Mesh count
        self._mesh_count_label = QLabel("-")
        content_form.addRow("Meshes:", self._mesh_count_label)

        # Skinned meshes
        self._skinned_mesh_label = QLabel("-")
        content_form.addRow("Skinned:", self._skinned_mesh_label)

        # Total vertices
        self._vertex_count_label = QLabel("-")
        content_form.addRow("Total Vertices:", self._vertex_count_label)

        # Total triangles
        self._triangle_count_label = QLabel("-")
        content_form.addRow("Total Triangles:", self._triangle_count_label)

        # Texture count
        self._texture_count_label = QLabel("-")
        content_form.addRow("Textures:", self._texture_count_label)

        # Animation count
        self._animation_count_label = QLabel("-")
        content_form.addRow("Animations:", self._animation_count_label)

        # Animation names
        self._animation_names_label = QLabel("-")
        self._animation_names_label.setWordWrap(True)
        self._animation_names_label.setStyleSheet("color: #888; font-size: 11px;")
        content_form.addRow("", self._animation_names_label)

        layout.addLayout(content_form)

        # Skeleton section
        skeleton_header = QLabel("Skeleton")
        skeleton_header.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 8px;")
        layout.addWidget(skeleton_header)

        skeleton_form = QFormLayout()
        skeleton_form.setContentsMargins(0, 0, 0, 0)
        skeleton_form.setSpacing(4)

        # Has skeleton
        self._has_skeleton_label = QLabel("-")
        skeleton_form.addRow("Has Skeleton:", self._has_skeleton_label)

        # Bone count
        self._bone_count_label = QLabel("-")
        skeleton_form.addRow("Bones:", self._bone_count_label)

        # Root scale
        self._root_scale_label = QLabel("-")
        skeleton_form.addRow("Root Scale:", self._root_scale_label)

        layout.addLayout(skeleton_form)

        # Import Settings section
        settings_header = QLabel("Import Settings")
        settings_header.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 8px;")
        layout.addWidget(settings_header)

        settings_form = QFormLayout()
        settings_form.setContentsMargins(0, 0, 0, 0)
        settings_form.setSpacing(4)

        # Convert to Z-Up checkbox
        self._convert_z_up_checkbox = QCheckBox()
        self._convert_z_up_checkbox.setChecked(True)  # Default enabled
        self._convert_z_up_checkbox.setToolTip(
            "Convert from glTF Y-up to engine Z-up coordinate system.\n"
            "glTF uses Y-up, -Z forward.\n"
            "Engine uses Z-up, Y forward.\n"
            "Disable only for models already in Z-up format."
        )
        settings_form.addRow("Convert to Z-Up:", self._convert_z_up_checkbox)

        # Normalize Scale checkbox
        self._normalize_scale_checkbox = QCheckBox()
        self._normalize_scale_checkbox.setToolTip(
            "If root node has scale != 1.0, normalize it by:\n"
            "1. Scaling all vertex positions\n"
            "2. Scaling animation translations\n"
            "3. Setting root scale to 1.0"
        )
        settings_form.addRow("Normalize Scale:", self._normalize_scale_checkbox)

        # Blender Z-Up Fix checkbox
        self._blender_z_up_fix_checkbox = QCheckBox()
        self._blender_z_up_fix_checkbox.setToolTip(
            "Compensate for Blender's -90°X rotation on Armature.\n"
            "Enable if character appears rotated after export from Blender.\n"
            "Rotates Armature by +90°X and root by -90°X."
        )
        settings_form.addRow("Blender Z-Up Fix:", self._blender_z_up_fix_checkbox)

        layout.addLayout(settings_form)

        # Apply button
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)

        self._apply_btn = QPushButton("Apply && Reimport")
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        btn_layout.addWidget(self._apply_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addStretch()

    def set_glb_by_path(self, file_path: str) -> None:
        """Load and inspect GLB from file path."""
        from termin.loaders.glb_loader import load_glb_file

        self._file_path = file_path
        name = os.path.splitext(os.path.basename(file_path))[0]

        self._name_label.setText(name)
        self._path_label.setText(file_path)

        # File size
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            self._file_size_label.setText(self._format_size(size))
        else:
            self._file_size_label.setText("-")

        try:
            scene_data = load_glb_file(file_path)
            self._scene_data = scene_data
            self._update_content_info(scene_data)
            self._load_spec_from_file(file_path)
        except Exception as e:
            self._clear_content()
            self._path_label.setText(f"Error: {e}")

    def _update_content_info(self, scene_data: "GLBSceneData") -> None:
        """Update UI with GLB content information."""
        # Mesh count
        mesh_count = len(scene_data.meshes)
        self._mesh_count_label.setText(str(mesh_count))

        # Skinned mesh count
        skinned_count = sum(1 for m in scene_data.meshes if m.is_skinned)
        self._skinned_mesh_label.setText(str(skinned_count) if skinned_count > 0 else "No")

        # Total vertices and triangles
        total_verts = sum(len(m.vertices) for m in scene_data.meshes)
        total_tris = sum(len(m.indices) // 3 for m in scene_data.meshes)
        self._vertex_count_label.setText(f"{total_verts:,}")
        self._triangle_count_label.setText(f"{total_tris:,}")

        # Texture count
        tex_count = len(scene_data.textures)
        self._texture_count_label.setText(str(tex_count) if tex_count > 0 else "None")

        # Animation count and names
        anim_count = len(scene_data.animations)
        self._animation_count_label.setText(str(anim_count) if anim_count > 0 else "None")
        if anim_count > 0:
            names = [a.name for a in scene_data.animations[:5]]  # Show first 5
            if anim_count > 5:
                names.append(f"... +{anim_count - 5} more")
            self._animation_names_label.setText(", ".join(names))
        else:
            self._animation_names_label.setText("")

        # Skeleton info
        if scene_data.skins:
            self._has_skeleton_label.setText("Yes")
            bone_count = sum(s.joint_count for s in scene_data.skins)
            self._bone_count_label.setText(str(bone_count))
        else:
            self._has_skeleton_label.setText("No")
            self._bone_count_label.setText("-")

        # Root scale
        root_scale = self._get_root_scale(scene_data)
        if root_scale is not None:
            if np.allclose(root_scale, [1, 1, 1]):
                self._root_scale_label.setText("1.0 (uniform)")
            else:
                self._root_scale_label.setText(
                    f"({root_scale[0]:.3f}, {root_scale[1]:.3f}, {root_scale[2]:.3f})"
                )
        else:
            self._root_scale_label.setText("-")

    def _get_root_scale(self, scene_data: "GLBSceneData") -> Optional[np.ndarray]:
        """Get root node scale if available."""
        if not scene_data.root_nodes or not scene_data.nodes:
            return None
        root_idx = scene_data.root_nodes[0]
        if root_idx < len(scene_data.nodes):
            return scene_data.nodes[root_idx].scale
        return None

    def _load_spec_from_file(self, glb_path: str) -> None:
        """Load spec settings from .glb.spec file."""
        from termin.editor.project_file_watcher import FilePreLoader

        spec_data = FilePreLoader.read_spec_file(glb_path)
        if spec_data:
            # Convert to Z-Up defaults to True
            convert_z_up = spec_data.get("convert_to_z_up", True)
            self._convert_z_up_checkbox.setChecked(convert_z_up)
            normalize = spec_data.get("normalize_scale", False)
            self._normalize_scale_checkbox.setChecked(normalize)
            blender_fix = spec_data.get("blender_z_up_fix", False)
            self._blender_z_up_fix_checkbox.setChecked(blender_fix)
        else:
            self._convert_z_up_checkbox.setChecked(True)  # Default enabled
            self._normalize_scale_checkbox.setChecked(False)
            self._blender_z_up_fix_checkbox.setChecked(False)

    def _on_apply_clicked(self) -> None:
        """Save spec and notify for GLB reimport."""
        if not self._file_path:
            return

        from termin.editor.project_file_watcher import FilePreLoader

        # Read existing spec to preserve UUID
        existing = FilePreLoader.read_spec_file(self._file_path) or {}

        # Update with new settings
        spec_data = {
            **existing,
            "convert_to_z_up": self._convert_z_up_checkbox.isChecked(),
            "normalize_scale": self._normalize_scale_checkbox.isChecked(),
            "blender_z_up_fix": self._blender_z_up_fix_checkbox.isChecked(),
        }

        # Save spec
        FilePreLoader.write_spec_file(self._file_path, spec_data)

        # Notify that spec changed
        if self._on_spec_changed is not None:
            self._on_spec_changed(self._file_path)

    def _clear_content(self) -> None:
        """Clear content fields."""
        self._scene_data = None
        self._mesh_count_label.setText("-")
        self._skinned_mesh_label.setText("-")
        self._vertex_count_label.setText("-")
        self._triangle_count_label.setText("-")
        self._texture_count_label.setText("-")
        self._animation_count_label.setText("-")
        self._animation_names_label.setText("")
        self._has_skeleton_label.setText("-")
        self._bone_count_label.setText("-")
        self._root_scale_label.setText("-")

    def _clear(self) -> None:
        """Clear all fields."""
        self._file_path = ""
        self._name_label.setText("-")
        self._file_size_label.setText("-")
        self._path_label.setText("-")
        self._clear_content()
        self._convert_z_up_checkbox.setChecked(True)  # Default enabled
        self._normalize_scale_checkbox.setChecked(False)
        self._blender_z_up_fix_checkbox.setChecked(False)

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"
