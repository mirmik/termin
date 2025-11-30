from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QLabel,
    QPushButton,
    QWidget,
)

from termin.editor.undo_stack import UndoStack, UndoCommand


class UndoStackViewer(QDialog):
    """
    Простое отладочное окно, показывающее текущее содержимое undo/redo стека.
    Запускается как отдельное top-level окно поверх главного редактора.
    """

    def __init__(self, undo_stack: UndoStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._undo_stack = undo_stack

        self.setWindowTitle("Undo/Redo Stack")
        self.setMinimumSize(500, 400)
        self.setModal(False)
        # Не используем Qt.WA_WindowTitleHint — в PyQt5 его нет
        # Оставляем только управление удалением по закрытию
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        layout = QVBoxLayout(self)

        header = QLabel("Отладочное окно. Показывает выполненные и отменённые команды undo/redo.")
        header.setWordWrap(True)
        layout.addWidget(header)

        lists_layout = QHBoxLayout()
        layout.addLayout(lists_layout)

        done_container = QWidget(self)
        done_layout = QVBoxLayout(done_container)
        done_label = QLabel("Выполненные команды (Undo)")
        self.done_list = QListWidget()
        done_layout.addWidget(done_label)
        done_layout.addWidget(self.done_list)
        lists_layout.addWidget(done_container)

        undone_container = QWidget(self)
        undone_layout = QVBoxLayout(undone_container)
        undone_label = QLabel("Отменённые команды (Redo)")
        self.undone_list = QListWidget()
        undone_layout.addWidget(undone_label)
        undone_layout.addWidget(self.undone_list)
        lists_layout.addWidget(undone_container)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        refresh_button = QPushButton("Обновить")
        close_button = QPushButton("Закрыть")
        buttons_layout.addWidget(refresh_button)
        buttons_layout.addWidget(close_button)
        layout.addLayout(buttons_layout)

        refresh_button.clicked.connect(self.refresh)
        close_button.clicked.connect(self.close)

        self.refresh()

    def _format_command(self, index: int, cmd: UndoCommand, is_done: bool) -> str:
        kind = "undo" if is_done else "redo"
        text = getattr(cmd, "text", "") or cmd.__class__.__name__
        return f"[{kind} #{index}] {text}"

    def refresh(self) -> None:
        """
        Перечитывает содержимое undo/redo стека и обновляет списки.
        """
        self.done_list.clear()
        self.undone_list.clear()

        done = getattr(self._undo_stack, "_done", [])
        undone = getattr(self._undo_stack, "_undone", [])

        for i, cmd in enumerate(done):
            self.done_list.addItem(self._format_command(i, cmd, True))

        for i, cmd in enumerate(undone):
            self.undone_list.addItem(self._format_command(i, cmd, False))
