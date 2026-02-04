"""
Scene Manager debug viewer.

Shows all scenes managed by SceneManager, their modes, and entity counts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLabel,
    QTextEdit,
    QSplitter,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush

from termin.editor.scene_manager import SceneMode

if TYPE_CHECKING:
    from termin.editor.scene_manager import SceneManager


class SceneManagerViewer(QWidget):
    """
    Window for viewing SceneManager state.

    Shows:
    - All scenes by name
    - Scene mode (INACTIVE, EDITOR, GAME)
    - Entity count
    - File path
    - Active scene indicator
    """

    def __init__(self, scene_manager: "SceneManager", parent=None):
        super().__init__(parent)
        self._scene_manager = scene_manager
        self._selected_scene_name: str | None = None

        self.setWindowTitle("Scene Manager")
        self.setMinimumSize(600, 400)

        # Make it a standalone window
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        """Create UI."""
        layout = QVBoxLayout(self)

        # Splitter: left - scene list, right - details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Left panel - scene list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        scenes_label = QLabel("Scenes")
        scenes_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(scenes_label)

        self._scenes_tree = QTreeWidget()
        self._scenes_tree.setHeaderLabels(["Name", "Mode", "Entities"])
        self._scenes_tree.setAlternatingRowColors(True)
        self._scenes_tree.itemClicked.connect(self._on_scene_clicked)
        left_layout.addWidget(self._scenes_tree)

        splitter.addWidget(left_widget)

        # Right panel - details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        details_label = QLabel("Scene Details")
        details_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(details_label)

        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setPlaceholderText("Select a scene to view details")
        right_layout.addWidget(self._details_text)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 300])

        # Status bar
        self._status_label = QLabel()
        self._status_label.setFixedHeight(20)
        layout.addWidget(self._status_label)

        # Scene actions toolbar
        actions_layout = QHBoxLayout()

        load_btn = QPushButton("Load...")
        load_btn.setToolTip("Load scene from file")
        load_btn.clicked.connect(self._on_load_scene)
        actions_layout.addWidget(load_btn)

        self._unload_btn = QPushButton("Unload")
        self._unload_btn.setToolTip("Close selected scene")
        self._unload_btn.clicked.connect(self._on_unload_scene)
        self._unload_btn.setEnabled(False)
        actions_layout.addWidget(self._unload_btn)

        actions_layout.addSpacing(20)

        self._inactive_btn = QPushButton("Inactive")
        self._inactive_btn.setToolTip("Set scene mode to INACTIVE")
        self._inactive_btn.clicked.connect(lambda: self._set_mode(SceneMode.INACTIVE))
        self._inactive_btn.setEnabled(False)
        actions_layout.addWidget(self._inactive_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setToolTip("Set scene mode to STOP")
        self._stop_btn.clicked.connect(lambda: self._set_mode(SceneMode.STOP))
        self._stop_btn.setEnabled(False)
        actions_layout.addWidget(self._stop_btn)

        self._play_btn = QPushButton("Play")
        self._play_btn.setToolTip("Set scene mode to PLAY")
        self._play_btn.clicked.connect(lambda: self._set_mode(SceneMode.PLAY))
        self._play_btn.setEnabled(False)
        actions_layout.addWidget(self._play_btn)

        actions_layout.addSpacing(20)

        # Rendering attachment (creates viewports for non-editor displays)
        render_label = QLabel("Render:")
        render_label.setStyleSheet("color: gray;")
        actions_layout.addWidget(render_label)

        self._attach_btn = QPushButton("Attach")
        self._attach_btn.setToolTip("Attach scene to RenderingController (create viewports for non-editor displays)")
        self._attach_btn.clicked.connect(self._on_attach_scene)
        self._attach_btn.setEnabled(False)
        actions_layout.addWidget(self._attach_btn)

        self._detach_btn = QPushButton("Detach")
        self._detach_btn.setToolTip("Detach scene from RenderingController (remove viewports)")
        self._detach_btn.clicked.connect(self._on_detach_scene)
        self._detach_btn.setEnabled(False)
        actions_layout.addWidget(self._detach_btn)

        actions_layout.addSpacing(20)

        # Editor attachment (attaches EditorSceneAttachment to scene)
        editor_label = QLabel("Editor:")
        editor_label.setStyleSheet("color: gray;")
        actions_layout.addWidget(editor_label)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setToolTip("Attach editor to this scene (EditorSceneAttachment)")
        self._edit_btn.clicked.connect(self._on_edit_scene)
        self._edit_btn.setEnabled(False)
        actions_layout.addWidget(self._edit_btn)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        # Bottom buttons
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _on_scene_clicked(self, item: QTreeWidgetItem) -> None:
        """Handle scene item click."""
        # Get slot name from UserRole data
        scene_name = item.data(0, Qt.ItemDataRole.UserRole)
        if scene_name is None:
            scene_name = item.text(0)  # Fallback
        self._selected_scene_name = scene_name
        self._update_details(scene_name)
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        """Update action buttons based on selected scene."""
        has_selection = self._selected_scene_name is not None
        self._unload_btn.setEnabled(has_selection)
        self._inactive_btn.setEnabled(has_selection)
        self._stop_btn.setEnabled(has_selection)
        self._play_btn.setEnabled(has_selection)
        self._attach_btn.setEnabled(has_selection)
        self._detach_btn.setEnabled(has_selection)
        self._edit_btn.setEnabled(has_selection)

    def _on_load_scene(self) -> None:
        """Load a scene from file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Scene",
            "",
            "Scene Files (*.scene);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return

        # Ask for slot name
        slot_name, ok = QInputDialog.getText(
            self,
            "Scene Slot Name",
            "Enter slot name for this scene:",
            text=f"scene_{len(self._scene_manager.get_debug_info())}",
        )
        if not ok or not slot_name:
            return

        try:
            self._scene_manager.load_scene(slot_name, path)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load scene:\n{e}")

    def _on_unload_scene(self) -> None:
        """Unload (close) selected scene."""
        if self._selected_scene_name is None:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Unload",
            f"Close scene '{self._selected_scene_name}'?\n\nUnsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._scene_manager.close_scene(self._selected_scene_name)
            self._selected_scene_name = None
            self._update_action_buttons()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Unload Error", f"Failed to close scene:\n{e}")

    def _set_mode(self, mode: SceneMode) -> None:
        """Set mode for selected scene."""
        if self._selected_scene_name is None:
            return

        try:
            self._scene_manager.set_mode(self._selected_scene_name, mode)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Mode Error", f"Failed to set mode:\n{e}")

    def _on_attach_scene(self) -> None:
        """Attach selected scene to RenderingController."""
        if self._selected_scene_name is None:
            return

        from termin.editor.rendering_controller import RenderingController

        rc = RenderingController.instance()
        if rc is None:
            QMessageBox.warning(self, "No Controller", "RenderingController not available")
            return

        scene = self._scene_manager.get_scene(self._selected_scene_name)
        if scene is None:
            return

        try:
            rc.attach_scene(scene)
            self.refresh()
            QMessageBox.information(self, "Attached", f"Scene '{self._selected_scene_name}' attached")
        except Exception as e:
            QMessageBox.critical(self, "Attach Error", f"Failed to attach scene:\n{e}")

    def _on_detach_scene(self) -> None:
        """Detach selected scene from RenderingController."""
        if self._selected_scene_name is None:
            return

        from termin.editor.rendering_controller import RenderingController

        rc = RenderingController.instance()
        if rc is None:
            QMessageBox.warning(self, "No Controller", "RenderingController not available")
            return

        scene = self._scene_manager.get_scene(self._selected_scene_name)
        if scene is None:
            return

        try:
            rc.detach_scene(scene)
            self.refresh()
            QMessageBox.information(self, "Detached", f"Scene '{self._selected_scene_name}' detached")
        except Exception as e:
            QMessageBox.critical(self, "Detach Error", f"Failed to detach scene:\n{e}")

    def _on_edit_scene(self) -> None:
        """Attach editor to selected scene via EditorSceneAttachment."""
        if self._selected_scene_name is None:
            return

        from termin.editor.editor_window import EditorWindow

        editor = EditorWindow.instance()
        if editor is None:
            QMessageBox.warning(self, "No Editor", "EditorWindow not available")
            return

        attachment = editor._editor_attachment
        if attachment is None:
            QMessageBox.warning(self, "No Attachment", "EditorSceneAttachment not available")
            return

        scene = self._scene_manager.get_scene(self._selected_scene_name)
        if scene is None:
            return

        # Check if already attached to this scene
        if attachment.scene is scene:
            QMessageBox.information(self, "Already Editing", f"Editor is already attached to '{self._selected_scene_name}'")
            return

        try:
            # Attach editor to new scene (transfers camera state)
            attachment.attach(scene, transfer_camera_state=True)
            editor._sync_attachment_refs()

            # Update editor scene name (used by game mode to know which scene to copy)
            editor._editor_scene_name = self._selected_scene_name

            # Set scene mode to STOP (editor mode)
            self._scene_manager.set_mode(self._selected_scene_name, SceneMode.STOP)

            # Update EditorViewportFeatures
            for features in editor._editor_features.values():
                features.set_scene(scene)
                features.set_camera(attachment.camera)
                features.selected_entity_id = 0
                features.hover_entity_id = 0

            # Update scene tree
            if editor.scene_tree_controller is not None:
                editor.scene_tree_controller.set_scene(scene)
                editor.scene_tree_controller.rebuild()

            # Clear selection
            if editor.selection_manager is not None:
                editor.selection_manager.clear()

            # Clear gizmo
            if editor.editor_viewport is not None:
                editor.editor_viewport.set_gizmo_target(None)

            # Update window title
            editor._update_window_title()

            editor._request_viewport_update()
            self.refresh()
            QMessageBox.information(self, "Editing", f"Editor attached to '{self._selected_scene_name}'")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Edit Error", f"Failed to attach editor:\n{e}")

    def _update_details(self, scene_name: str) -> None:
        """Update details panel for selected scene."""
        scene = self._scene_manager.get_scene(scene_name)
        if scene is None:
            self._details_text.setText(f"Scene '{scene_name}' not found")
            return

        mode = self._scene_manager.get_mode(scene_name)
        path = self._scene_manager.get_scene_path(scene_name)

        # Check if this scene is being edited
        is_editing = False
        from termin.editor.editor_window import EditorWindow
        editor = EditorWindow.instance()
        if editor is not None and editor._editor_attachment is not None:
            is_editing = editor._editor_attachment.scene is scene

        lines = [
            f"Name: {scene_name}",
            f"Mode: {mode.name}",
            f"Path: {path or '(unsaved)'}",
            f"Editing: {'YES' if is_editing else 'no'}",
            f"",
            f"=== Entities ===",
        ]

        # List entities
        entity_count = 0
        root_entities = []
        for entity in scene.entities:
            entity_count += 1
            if entity.transform.parent is None:
                root_entities.append(entity)

        lines.append(f"Total: {entity_count}")
        lines.append(f"Root entities: {len(root_entities)}")
        lines.append(f"")

        # List root entities
        for entity in root_entities[:20]:  # Limit to 20
            serializable = "S" if entity.serializable else "-"
            enabled = "E" if entity.enabled else "-"
            lines.append(f"  [{serializable}{enabled}] {entity.name}")

        if len(root_entities) > 20:
            lines.append(f"  ... and {len(root_entities) - 20} more")

        self._details_text.setText("\n".join(lines))

    def _get_debug_info(self) -> dict:
        """Get debug info for all scenes."""
        info = {}
        for name in self._scene_manager.scene_names():
            scene = self._scene_manager.get_scene(name)
            if scene:
                info[name] = {
                    "mode": self._scene_manager.get_mode(name).name,
                    "entity_count": len(list(scene.entities)),
                    "path": self._scene_manager.get_scene_path(name),
                }
        return info

    def refresh(self) -> None:
        """Refresh scene list."""
        self._scenes_tree.clear()

        debug_info = self._get_debug_info()

        # Color brushes for different modes
        mode_colors = {
            "INACTIVE": QBrush(QColor(128, 128, 128)),  # Gray
            "STOP": QBrush(QColor(70, 130, 180)),       # Steel blue
            "PLAY": QBrush(QColor(50, 205, 50)),        # Lime green
        }

        for name, info in sorted(debug_info.items()):
            mode = info["mode"]
            entity_count = info["entity_count"]
            path = info.get("path")

            # Show file name if available, otherwise slot name
            if path:
                import os
                display_name = os.path.splitext(os.path.basename(path))[0]
                display_name = f"{display_name} [{name}]"
            else:
                display_name = f"{name} (unsaved)"

            item = QTreeWidgetItem([
                display_name,
                mode,
                str(entity_count),
            ])
            # Store slot name for click handler
            item.setData(0, Qt.ItemDataRole.UserRole, name)

            # Color by mode
            if mode in mode_colors:
                item.setForeground(1, mode_colors[mode])

            self._scenes_tree.addTopLevelItem(item)

        # Resize columns
        for i in range(3):
            self._scenes_tree.resizeColumnToContents(i)

        # Update details if scene selected
        if self._selected_scene_name:
            self._update_details(self._selected_scene_name)

        # Update status
        total_scenes = len(debug_info)
        total_entities = sum(info["entity_count"] for info in debug_info.values())
        play_scenes = sum(1 for info in debug_info.values() if info["mode"] == "PLAY")

        # Find which scene is being edited
        editing_scene = None
        from termin.editor.editor_window import EditorWindow
        editor = EditorWindow.instance()
        if editor is not None and editor._editor_attachment is not None:
            attached = editor._editor_attachment.scene
            if attached is not None:
                # Find scene name by scene object
                for name, info in debug_info.items():
                    scene = self._scene_manager.get_scene(name)
                    if scene is attached:
                        editing_scene = name
                        break

        editing_str = f" | Editing: {editing_scene}" if editing_scene else ""
        self._status_label.setText(
            f"Scenes: {total_scenes} | "
            f"Total entities: {total_entities} | "
            f"Playing: {play_scenes}"
            f"{editing_str}"
        )

