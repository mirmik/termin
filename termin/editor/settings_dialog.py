"""
Диалог настроек редактора.

Позволяет пользователю настроить внешний текстовый редактор и другие параметры.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
)

from termin.editor.settings import EditorSettings


class SettingsDialog(QDialog):
    """
    Диалог настроек редактора.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)

        self._settings = EditorSettings.instance()
        self._init_ui()
        self._load_settings()

    def _init_ui(self) -> None:
        """Создаёт UI диалога."""
        layout = QVBoxLayout(self)

        # --- Группа: Внешние программы ---
        external_group = QGroupBox("External Programs")
        external_layout = QFormLayout(external_group)

        # Текстовый редактор
        editor_layout = QHBoxLayout()
        self._text_editor_edit = QLineEdit()
        self._text_editor_edit.setPlaceholderText("System default")
        editor_layout.addWidget(self._text_editor_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_text_editor)
        editor_layout.addWidget(browse_btn)

        external_layout.addRow("Text Editor:", editor_layout)

        layout.addWidget(external_group)

        # --- Spacer ---
        layout.addStretch()

        # --- Кнопки OK/Cancel ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_settings(self) -> None:
        """Загружает текущие настройки в UI."""
        text_editor = self._settings.get_text_editor()
        if text_editor:
            self._text_editor_edit.setText(text_editor)

    def _save_and_accept(self) -> None:
        """Сохраняет настройки и закрывает диалог."""
        text_editor = self._text_editor_edit.text().strip()
        self._settings.set_text_editor(text_editor if text_editor else None)
        self._settings.sync()
        self.accept()

    def _browse_text_editor(self) -> None:
        """Открывает диалог выбора исполняемого файла текстового редактора."""
        import platform

        if platform.system() == "Windows":
            filter_str = "Executables (*.exe);;All Files (*)"
        else:
            filter_str = "All Files (*)"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Text Editor",
            "",
            filter_str,
        )

        if file_path:
            self._text_editor_edit.setText(file_path)
