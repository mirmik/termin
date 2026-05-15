"""Dialog for editing Detour navmesh area names."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from termin.navmesh.settings import NAVMESH_AREA_COUNT, NavigationSettingsManager


class NavMeshAreasDialog(QDialog):
    """Project-level navigation area names editor."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self._manager = NavigationSettingsManager.instance()
        self._on_changed = on_changed
        self._edits: list[QLineEdit] = []

        self.setWindowTitle("NavMesh Areas")
        self.setMinimumSize(420, 500)

        self._init_ui()
        self._load_from_settings()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        content = QWidget()
        form = QFormLayout(content)

        for area_index in range(NAVMESH_AREA_COUNT):
            edit = QLineEdit()
            edit.setPlaceholderText(f"Area {area_index}")
            edit.editingFinished.connect(
                lambda index=area_index, field=edit: self._on_area_changed(index, field.text())
            )
            self._edits.append(edit)
            form.addRow(f"{area_index}:", edit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)

    def _load_from_settings(self) -> None:
        names = self._manager.settings.navmesh_area_names
        for area_index, edit in enumerate(self._edits):
            edit.setText(names[area_index])

    def _on_area_changed(self, index: int, text: str) -> None:
        self._manager.set_navmesh_area_name(index, text)
        self._manager.save()

        if self._on_changed is not None:
            self._on_changed()
