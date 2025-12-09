"""
ProjectBrowser — файловый менеджер проекта в стиле Unity.

Показывает дерево директорий слева и содержимое выбранной директории справа.
Позволяет просматривать и выбирать ассеты проекта (материалы, меши, текстуры и т.д.).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import (
    QTreeView,
    QListView,
    QAbstractItemView,
    QMenu,
    QInputDialog,
    QMessageBox,
)
from PyQt6.QtGui import QFileSystemModel, QAction
from PyQt6.QtCore import Qt, QModelIndex, QDir

from termin.editor.settings import EditorSettings


class ProjectBrowser:
    """
    Контроллер файлового браузера проекта.

    Управляет двумя виджетами:
    - dir_tree: QTreeView с деревом директорий
    - file_list: QListView с содержимым выбранной директории

    Атрибуты:
        root_path: Корневая директория проекта
        on_file_selected: Callback при выборе файла
        on_file_double_clicked: Callback при двойном клике на файл
    """

    # Расширения файлов, которые показываем
    SUPPORTED_EXTENSIONS = {
        ".shader",    # Шейдеры/материалы
        ".json",      # Сцены, конфиги
        ".png", ".jpg", ".jpeg", ".tga", ".bmp",  # Текстуры
        ".obj", ".fbx", ".gltf", ".glb",  # Модели
        ".py",        # Скрипты
    }

    def __init__(
        self,
        dir_tree: QTreeView,
        file_list: QListView,
        root_path: str | Path | None = None,
        on_file_selected: Callable[[Path], None] | None = None,
        on_file_double_clicked: Callable[[Path], None] | None = None,
    ):
        self._dir_tree = dir_tree
        self._file_list = file_list
        self._on_file_selected = on_file_selected
        self._on_file_double_clicked = on_file_double_clicked

        # Модели файловой системы
        self._dir_model = QFileSystemModel()
        self._file_model = QFileSystemModel()

        # Настройка модели директорий (только папки)
        self._dir_model.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)
        self._dir_model.setReadOnly(True)

        # Настройка модели файлов (файлы и папки)
        self._file_model.setFilter(
            QDir.Filter.Files | QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot
        )
        self._file_model.setReadOnly(True)

        # Применяем модели к виджетам
        self._dir_tree.setModel(self._dir_model)
        self._file_list.setModel(self._file_model)

        # Настройка дерева директорий
        self._dir_tree.setHeaderHidden(True)
        # Скрываем все колонки кроме имени
        for i in range(1, self._dir_model.columnCount()):
            self._dir_tree.hideColumn(i)

        # Настройка списка файлов
        self._file_list.setViewMode(QListView.ViewMode.ListMode)
        self._file_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Подключаем сигналы
        self._dir_tree.selectionModel().currentChanged.connect(self._on_dir_selected)
        self._file_list.doubleClicked.connect(self._on_file_double_click)
        self._file_list.clicked.connect(self._on_file_click)
        self._file_list.customContextMenuRequested.connect(self._show_file_context_menu)

        # Устанавливаем корневую директорию
        if root_path is not None:
            self.set_root_path(root_path)

    def set_root_path(self, path: str | Path) -> None:
        """Установить корневую директорию проекта."""
        path = Path(path).resolve()
        if not path.exists():
            return

        self._root_path = path
        path_str = str(path)

        # Устанавливаем корень для обеих моделей
        self._dir_model.setRootPath(path_str)
        self._file_model.setRootPath(path_str)

        # Устанавливаем корневой индекс для дерева
        root_index = self._dir_model.index(path_str)
        self._dir_tree.setRootIndex(root_index)

        # Устанавливаем корневой индекс для списка файлов
        file_root_index = self._file_model.index(path_str)
        self._file_list.setRootIndex(file_root_index)

    @property
    def root_path(self) -> Path | None:
        """Текущая корневая директория."""
        return getattr(self, "_root_path", None)

    @property
    def current_directory(self) -> Path | None:
        """Текущая выбранная директория."""
        index = self._dir_tree.currentIndex()
        if not index.isValid():
            return self._root_path
        return Path(self._dir_model.filePath(index))

    @property
    def selected_file(self) -> Path | None:
        """Текущий выбранный файл."""
        index = self._file_list.currentIndex()
        if not index.isValid():
            return None
        return Path(self._file_model.filePath(index))

    def _on_dir_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        """Обработчик выбора директории в дереве."""
        if not current.isValid():
            return

        dir_path = self._dir_model.filePath(current)

        # Обновляем список файлов для выбранной директории
        file_index = self._file_model.index(dir_path)
        self._file_list.setRootIndex(file_index)

    def _on_file_click(self, index: QModelIndex) -> None:
        """Обработчик клика на файл."""
        if not index.isValid():
            return

        file_path = Path(self._file_model.filePath(index))

        # Если это директория — игнорируем одиночный клик
        if file_path.is_dir():
            return

        if self._on_file_selected is not None:
            self._on_file_selected(file_path)

    def _on_file_double_click(self, index: QModelIndex) -> None:
        """Обработчик двойного клика на файл/папку."""
        if not index.isValid():
            return

        file_path = Path(self._file_model.filePath(index))

        if file_path.is_dir():
            # Двойной клик на папку — переходим в неё
            self._navigate_to_directory(file_path)
        else:
            # Двойной клик на файл — открываем
            if self._on_file_double_clicked is not None:
                self._on_file_double_clicked(file_path)

    def _navigate_to_directory(self, dir_path: Path) -> None:
        """Перейти в указанную директорию."""
        # Находим и выбираем директорию в дереве
        dir_index = self._dir_model.index(str(dir_path))
        if dir_index.isValid():
            self._dir_tree.setCurrentIndex(dir_index)
            self._dir_tree.expand(dir_index)

    def _show_file_context_menu(self, pos) -> None:
        """Показать контекстное меню для файла."""
        index = self._file_list.indexAt(pos)

        menu = QMenu(self._file_list)

        if index.isValid():
            file_path = Path(self._file_model.filePath(index))

            if file_path.is_file():
                open_action = QAction("Open", self._file_list)
                open_action.triggered.connect(lambda: self._open_file(file_path))
                menu.addAction(open_action)

                menu.addSeparator()

            # Показать в проводнике
            reveal_action = QAction("Show in Explorer", self._file_list)
            reveal_action.triggered.connect(lambda: self._reveal_in_explorer(file_path))
            menu.addAction(reveal_action)

            menu.addSeparator()

        # Создать директорию (доступно всегда)
        create_dir_action = QAction("Create Directory...", self._file_list)
        create_dir_action.triggered.connect(self._create_directory)
        menu.addAction(create_dir_action)

        menu.addSeparator()

        # Обновить
        refresh_action = QAction("Refresh", self._file_list)
        refresh_action.triggered.connect(self._refresh)
        menu.addAction(refresh_action)

        menu.exec(self._file_list.mapToGlobal(pos))

    def _open_file(self, file_path: Path) -> None:
        """Открыть файл (вызывает callback)."""
        if self._on_file_double_clicked is not None:
            self._on_file_double_clicked(file_path)

    def _reveal_in_explorer(self, path: Path) -> None:
        """Открыть путь в системном файловом менеджере."""
        import subprocess
        import platform

        if platform.system() == "Windows":
            if path.is_file():
                subprocess.run(["explorer", "/select,", str(path)])
            else:
                subprocess.run(["explorer", str(path)])
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", "-R", str(path)])
        else:  # Linux
            subprocess.run(["xdg-open", str(path.parent if path.is_file() else path)])

    def _create_directory(self) -> None:
        """Создать новую директорию в текущей папке."""
        current_dir = self.current_directory
        if current_dir is None:
            return

        name, ok = QInputDialog.getText(
            self._file_list,
            "Create Directory",
            "Directory name:",
        )

        if ok and name:
            new_dir = current_dir / name
            try:
                new_dir.mkdir(parents=False, exist_ok=False)
                self._refresh()
            except FileExistsError:
                QMessageBox.warning(
                    self._file_list,
                    "Error",
                    f"Directory '{name}' already exists.",
                )
            except OSError as e:
                QMessageBox.warning(
                    self._file_list,
                    "Error",
                    f"Failed to create directory: {e}",
                )

    def _refresh(self) -> None:
        """Обновить содержимое."""
        if self._root_path is not None:
            self.set_root_path(self._root_path)
