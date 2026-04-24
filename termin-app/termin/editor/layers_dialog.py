"""
Диалог настройки слоёв и флагов.

Позволяет задать имена для слоёв (0-63) и флагов (0-63 бит).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QTabWidget,
    QWidget,
    QScrollArea,
    QLabel,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class LayersDialog(QDialog):
    """
    Диалог настройки слоёв и флагов сцены.
    """

    def __init__(self, scene: "Scene", parent=None):
        super().__init__(parent)
        self._scene = scene
        self.setWindowTitle("Layers & Flags")
        self.setMinimumWidth(400)
        self.setMinimumHeight(500)

        self._layer_edits: list[QLineEdit] = []
        self._flag_edits: list[QLineEdit] = []

        self._init_ui()
        self._load_from_scene()

    def _init_ui(self) -> None:
        """Создаёт UI диалога."""
        layout = QVBoxLayout(self)

        # Tabs for layers and flags
        tabs = QTabWidget()

        # --- Layers tab ---
        layers_tab = self._create_names_tab(
            self._layer_edits,
            "Layer",
            64,
        )
        tabs.addTab(layers_tab, "Layers")

        # --- Flags tab ---
        flags_tab = self._create_names_tab(
            self._flag_edits,
            "Flag",
            64,
        )
        tabs.addTab(flags_tab, "Flags")

        layout.addWidget(tabs)

        # --- Кнопки OK/Cancel ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_names_tab(
        self,
        edits_list: list[QLineEdit],
        prefix: str,
        count: int,
    ) -> QWidget:
        """Создаёт вкладку со списком имён."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        form = QFormLayout(container)
        form.setContentsMargins(10, 10, 10, 10)

        for i in range(count):
            edit = QLineEdit()
            edit.setPlaceholderText(f"{prefix} {i}")
            edits_list.append(edit)
            label = QLabel(f"{i}:")
            label.setFixedWidth(30)
            form.addRow(label, edit)

        scroll.setWidget(container)
        return scroll

    def _load_from_scene(self) -> None:
        """Загружает текущие имена из сцены."""
        layer_names = self._scene.layer_names
        for i, edit in enumerate(self._layer_edits):
            name = layer_names.get(i, "")
            edit.setText(name)

        flag_names = self._scene.flag_names
        for i, edit in enumerate(self._flag_edits):
            name = flag_names.get(i, "")
            edit.setText(name)

    def _save_and_accept(self) -> None:
        """Сохраняет имена в сцену и закрывает диалог."""
        for i, edit in enumerate(self._layer_edits):
            name = edit.text().strip()
            self._scene.set_layer_name(i, name)

        for i, edit in enumerate(self._flag_edits):
            name = edit.text().strip()
            self._scene.set_flag_name(i, name)

        self.accept()
