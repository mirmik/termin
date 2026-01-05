"""ChronoSphere state viewer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Set

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer

if TYPE_CHECKING:
    from termin.chronosquad.core import ChronoSphere


class ChronosphereViewer(QWidget):
    """
    Widget showing current ChronoSphere state.

    Displays:
    - List of timelines with current step/time
    - Objects in each timeline
    - Time multiplier and pause state
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ChronoSphere Viewer")
        self.setMinimumSize(400, 300)

        self._setup_ui()

        # Auto-refresh timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start(500)  # 2 FPS - slower to not interfere with UI

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        self._status_label = QLabel("No ChronoSphere")
        header_layout.addWidget(self._status_label)

        self._auto_refresh_cb = QCheckBox("Auto")
        self._auto_refresh_cb.setChecked(True)
        header_layout.addWidget(self._auto_refresh_cb)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Tree view
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Value"])
        self._tree.setColumnWidth(0, 200)
        layout.addWidget(self._tree)

    def _auto_refresh(self):
        """Called by timer - only refresh if auto is enabled."""
        if self._auto_refresh_cb.isChecked():
            self.refresh()

    def _get_expanded_paths(self) -> Set[str]:
        """Get paths of all expanded items."""
        expanded = set()

        def collect(item: QTreeWidgetItem, path: str):
            item_path = f"{path}/{item.text(0)}"
            if item.isExpanded():
                expanded.add(item_path)
            for i in range(item.childCount()):
                collect(item.child(i), item_path)

        for i in range(self._tree.topLevelItemCount()):
            collect(self._tree.topLevelItem(i), "")

        return expanded

    def _restore_expanded(self, expanded: Set[str]):
        """Restore expanded state from paths."""
        def restore(item: QTreeWidgetItem, path: str):
            item_path = f"{path}/{item.text(0)}"
            if item_path in expanded:
                item.setExpanded(True)
            for i in range(item.childCount()):
                restore(item.child(i), item_path)

        for i in range(self._tree.topLevelItemCount()):
            restore(self._tree.topLevelItem(i), "")

    def refresh(self):
        """Refresh the display."""
        # Save expanded state
        expanded = self._get_expanded_paths()

        self._tree.clear()

        # Always find ChronoSphere from current scene
        cs = self._find_chronosphere()

        if cs is None:
            self._status_label.setText("No ChronoSphere found")
            return

        # Status
        current = cs.current_timeline
        status_parts = [
            f"Timelines: {cs.timelines_count}",
            f"Current: {current.name if current else 'None'}",
        ]
        self._status_label.setText(" | ".join(status_parts))

        # Time control
        time_item = QTreeWidgetItem(["Time Control", ""])
        time_item.addChild(QTreeWidgetItem([
            "Multiplier",
            f"{cs.time_multiplier:.2f} (target: {cs.target_time_multiplier:.2f})"
        ]))
        time_item.addChild(QTreeWidgetItem(["Paused", str(cs.is_paused)]))
        self._tree.addTopLevelItem(time_item)
        time_item.setExpanded(True)

        # Timelines
        for name, timeline in cs.timelines().items():
            tl_item = QTreeWidgetItem([name, ""])

            # Timeline info
            tl_item.addChild(QTreeWidgetItem(["Step", str(timeline.current_step)]))
            tl_item.addChild(QTreeWidgetItem(["Time", f"{timeline.current_time:.2f}s"]))
            tl_item.addChild(QTreeWidgetItem(["Objects", str(len(timeline.objects))]))

            is_current = timeline == current
            if is_current:
                tl_item.setText(0, f"{name} (current)")

            # Objects
            objects_item = QTreeWidgetItem(["Objects", str(len(timeline.objects))])
            for obj in timeline.objects:
                obj_item = QTreeWidgetItem([obj.name, ""])
                pos = obj.local_position
                obj_item.addChild(QTreeWidgetItem([
                    "Position",
                    f"({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f})"
                ]))
                obj_item.addChild(QTreeWidgetItem([
                    "Animatronics",
                    str(len(obj._animatronics))
                ]))
                objects_item.addChild(obj_item)

            tl_item.addChild(objects_item)

            self._tree.addTopLevelItem(tl_item)

            # Expand current timeline by default on first show
            if is_current and not expanded:
                tl_item.setExpanded(True)

        # Restore expanded state
        self._restore_expanded(expanded)

    def _find_chronosphere(self) -> ChronoSphere | None:
        """Find ChronoSphere from current scene."""
        try:
            from termin.editor.editor_window import EditorWindow
            from termin.chronosquad.controllers import ChronosphereController

            editor = EditorWindow.instance()
            if editor is None:
                return None

            scene = editor.world_persistence.scene
            if scene is None:
                return None

            for entity in scene.entities:
                ctrl = entity.get_component(ChronosphereController)
                if ctrl is not None:
                    return ctrl.chronosphere

        except Exception:
            pass

        return None

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
