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
from PyQt6.QtGui import QFileSystemModel, QAction, QPixmap, QPainter, QColor, QBrush, QPen, QIcon, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QModelIndex, QDir, QFileInfo, QMimeData, QObject, QEvent, QPoint
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QFileIconProvider

from termin.editor.settings import EditorSettings
from termin.editor.drag_drop import EditorMimeTypes, create_asset_path_mime_data


def _create_material_icon() -> QIcon:
    """Создаёт иконку материала — сфера с градиентом."""
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Фон — тёмный круг (тень)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(40, 40, 40)))
    painter.drawEllipse(2, 2, size - 4, size - 4)

    # Основная сфера с градиентом
    from PyQt6.QtGui import QRadialGradient
    gradient = QRadialGradient(size * 0.35, size * 0.35, size * 0.45)
    gradient.setColorAt(0.0, QColor(180, 120, 220))  # Светлый центр (фиолетовый)
    gradient.setColorAt(0.5, QColor(120, 60, 180))   # Средний тон
    gradient.setColorAt(1.0, QColor(60, 20, 100))    # Тёмный край

    painter.setBrush(QBrush(gradient))
    painter.drawEllipse(2, 2, size - 4, size - 4)

    # Блик
    highlight = QRadialGradient(size * 0.3, size * 0.25, size * 0.15)
    highlight.setColorAt(0.0, QColor(255, 255, 255, 180))
    highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(QBrush(highlight))
    painter.drawEllipse(int(size * 0.2), int(size * 0.15), int(size * 0.3), int(size * 0.25))

    painter.end()
    return QIcon(pixmap)


def _create_shader_icon() -> QIcon:
    """Создаёт иконку шейдера — документ с кодом."""
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Фон документа
    painter.setPen(QPen(QColor(80, 80, 80), 1))
    painter.setBrush(QBrush(QColor(50, 55, 65)))
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 3, 3)

    # "Код" — цветные линии
    painter.setPen(Qt.PenStyle.NoPen)

    # Строка 1 — ключевое слово (оранжевый)
    painter.setBrush(QBrush(QColor(230, 150, 80)))
    painter.drawRect(6, 7, 10, 2)

    # Строка 2 — тип (голубой)
    painter.setBrush(QBrush(QColor(100, 180, 220)))
    painter.drawRect(6, 12, 8, 2)
    painter.setBrush(QBrush(QColor(180, 180, 180)))
    painter.drawRect(16, 12, 6, 2)

    # Строка 3 — функция (зелёный)
    painter.setBrush(QBrush(QColor(130, 200, 130)))
    painter.drawRect(6, 17, 12, 2)

    # Строка 4 — значение (фиолетовый)
    painter.setBrush(QBrush(QColor(180, 130, 200)))
    painter.drawRect(6, 22, 14, 2)

    painter.end()
    return QIcon(pixmap)


def _create_pipeline_icon() -> QIcon:
    """Создаёт иконку пайплайна — стрелки/блоки процесса."""
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Три блока (пассы) соединённые стрелками
    block_color = QColor(80, 160, 120)
    arrow_color = QColor(200, 200, 200)

    painter.setPen(Qt.PenStyle.NoPen)

    # Блок 1 (верх)
    painter.setBrush(QBrush(block_color))
    painter.drawRoundedRect(4, 4, 10, 8, 2, 2)

    # Блок 2 (середина)
    painter.setBrush(QBrush(block_color.lighter(110)))
    painter.drawRoundedRect(11, 12, 10, 8, 2, 2)

    # Блок 3 (низ)
    painter.setBrush(QBrush(block_color.lighter(120)))
    painter.drawRoundedRect(18, 20, 10, 8, 2, 2)

    # Стрелки между блоками
    painter.setPen(QPen(arrow_color, 1.5))
    painter.drawLine(14, 10, 16, 14)  # блок1 -> блок2
    painter.drawLine(21, 18, 23, 22)  # блок2 -> блок3

    painter.end()
    return QIcon(pixmap)


def _create_scene_icon() -> QIcon:
    """Создаёт иконку сцены — кубик в перспективе."""
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Изометрический куб
    from PyQt6.QtGui import QPolygon
    from PyQt6.QtCore import QPoint

    cx, cy = size // 2, size // 2 + 2
    s = 10  # размер грани

    # Верхняя грань (светлая)
    top = QPolygon([
        QPoint(cx, cy - s),
        QPoint(cx + s, cy - s // 2),
        QPoint(cx, cy),
        QPoint(cx - s, cy - s // 2),
    ])
    painter.setPen(QPen(QColor(60, 60, 60), 1))
    painter.setBrush(QBrush(QColor(100, 160, 220)))
    painter.drawPolygon(top)

    # Левая грань (средняя)
    left = QPolygon([
        QPoint(cx - s, cy - s // 2),
        QPoint(cx, cy),
        QPoint(cx, cy + s),
        QPoint(cx - s, cy + s // 2),
    ])
    painter.setBrush(QBrush(QColor(70, 120, 180)))
    painter.drawPolygon(left)

    # Правая грань (тёмная)
    right = QPolygon([
        QPoint(cx, cy),
        QPoint(cx + s, cy - s // 2),
        QPoint(cx + s, cy + s // 2),
        QPoint(cx, cy + s),
    ])
    painter.setBrush(QBrush(QColor(50, 90, 140)))
    painter.drawPolygon(right)

    painter.end()
    return QIcon(pixmap)


def _create_prefab_icon() -> QIcon:
    """Создаёт иконку префаба — кубик с символом P."""
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    from PyQt6.QtGui import QPolygon, QFont
    from PyQt6.QtCore import QPoint, QRectF

    cx, cy = size // 2, size // 2 + 2
    s = 10  # размер грани

    # Верхняя грань (светлая, зелёный оттенок)
    top = QPolygon([
        QPoint(cx, cy - s),
        QPoint(cx + s, cy - s // 2),
        QPoint(cx, cy),
        QPoint(cx - s, cy - s // 2),
    ])
    painter.setPen(QPen(QColor(60, 60, 60), 1))
    painter.setBrush(QBrush(QColor(120, 200, 140)))
    painter.drawPolygon(top)

    # Левая грань (средняя)
    left = QPolygon([
        QPoint(cx - s, cy - s // 2),
        QPoint(cx, cy),
        QPoint(cx, cy + s),
        QPoint(cx - s, cy + s // 2),
    ])
    painter.setBrush(QBrush(QColor(80, 160, 100)))
    painter.drawPolygon(left)

    # Правая грань (тёмная)
    right = QPolygon([
        QPoint(cx, cy),
        QPoint(cx + s, cy - s // 2),
        QPoint(cx + s, cy + s // 2),
        QPoint(cx, cy + s),
    ])
    painter.setBrush(QBrush(QColor(50, 120, 70)))
    painter.drawPolygon(right)

    # Буква "P" в центре
    painter.setPen(QPen(QColor(255, 255, 255), 1))
    font = QFont("Arial", 10, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "P")

    painter.end()
    return QIcon(pixmap)


def _create_voxels_icon() -> QIcon:
    """Создаёт иконку воксельной сетки — 3D сетка из кубиков."""
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    from PyQt6.QtGui import QPolygon
    from PyQt6.QtCore import QPoint

    # Рисуем несколько маленьких кубиков в изометрии
    def draw_voxel(cx, cy, s, color_top, color_left, color_right):
        # Верхняя грань
        top = QPolygon([
            QPoint(cx, cy - s),
            QPoint(cx + s, cy - s // 2),
            QPoint(cx, cy),
            QPoint(cx - s, cy - s // 2),
        ])
        painter.setPen(QPen(QColor(40, 40, 40), 1))
        painter.setBrush(QBrush(color_top))
        painter.drawPolygon(top)

        # Левая грань
        left = QPolygon([
            QPoint(cx - s, cy - s // 2),
            QPoint(cx, cy),
            QPoint(cx, cy + s),
            QPoint(cx - s, cy + s // 2),
        ])
        painter.setBrush(QBrush(color_left))
        painter.drawPolygon(left)

        # Правая грань
        right = QPolygon([
            QPoint(cx, cy),
            QPoint(cx + s, cy - s // 2),
            QPoint(cx + s, cy + s // 2),
            QPoint(cx, cy + s),
        ])
        painter.setBrush(QBrush(color_right))
        painter.drawPolygon(right)

    # Сетка из кубиков (синие оттенки)
    s = 5  # размер грани кубика

    # Нижний ряд
    draw_voxel(10, 22, s, QColor(100, 160, 220), QColor(60, 120, 180), QColor(40, 100, 160))
    draw_voxel(18, 26, s, QColor(100, 160, 220), QColor(60, 120, 180), QColor(40, 100, 160))

    # Средний ряд
    draw_voxel(18, 18, s, QColor(120, 180, 240), QColor(80, 140, 200), QColor(60, 120, 180))
    draw_voxel(26, 22, s, QColor(120, 180, 240), QColor(80, 140, 200), QColor(60, 120, 180))

    # Верхний кубик
    draw_voxel(18, 10, s, QColor(140, 200, 255), QColor(100, 160, 220), QColor(80, 140, 200))

    painter.end()
    return QIcon(pixmap)


class AssetIconProvider(QFileIconProvider):
    """Провайдер иконок для ассетов проекта."""

    def __init__(self):
        super().__init__()
        self._material_icon = _create_material_icon()
        self._shader_icon = _create_shader_icon()
        self._scene_icon = _create_scene_icon()
        self._pipeline_icon = _create_pipeline_icon()
        self._prefab_icon = _create_prefab_icon()
        self._voxels_icon = _create_voxels_icon()

    def icon(self, info_or_type):
        # info_or_type может быть QFileInfo или IconType
        if isinstance(info_or_type, QFileInfo):
            suffix = info_or_type.suffix().lower()
            if suffix == "material":
                return self._material_icon
            elif suffix == "shader":
                return self._shader_icon
            elif suffix == "scene":
                return self._scene_icon
            elif suffix == "pipeline":
                return self._pipeline_icon
            elif suffix == "prefab":
                return self._prefab_icon
            elif suffix == "voxels":
                return self._voxels_icon

        return super().icon(info_or_type)


class PrefabDragFilter(QObject):
    """
    Event filter для обработки drag prefab/fbx файлов из QListView.

    Перехватывает начало drag и создаёт кастомный QDrag с ASSET_PATH mime data.
    """

    DRAGGABLE_EXTENSIONS = {".prefab", ".fbx"}

    def __init__(self, list_view: QListView, file_model: QFileSystemModel, parent=None):
        super().__init__(parent)
        self._list_view = list_view
        self._file_model = file_model
        self._drag_start_pos: QPoint | None = None
        self._drag_start_index: QModelIndex | None = None
        # События мыши идут во viewport, не в сам QListView
        self._viewport = list_view.viewport()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is not self._viewport:
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_pos = event.position().toPoint()
                # Запоминаем индекс под курсором
                self._drag_start_index = self._list_view.indexAt(self._drag_start_pos)

        elif event.type() == QEvent.Type.MouseMove:
            if self._drag_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
                # Проверяем, достаточно ли мышь сдвинулась для начала drag
                from PyQt6.QtWidgets import QApplication
                distance = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
                if distance >= QApplication.startDragDistance():
                    if self._start_prefab_drag():
                        self._drag_start_pos = None
                        self._drag_start_index = None
                        return True
                    self._drag_start_pos = None
                    self._drag_start_index = None

        elif event.type() == QEvent.Type.MouseButtonRelease:
            self._drag_start_pos = None
            self._drag_start_index = None

        return False

    def _start_prefab_drag(self) -> bool:
        """Начинает drag операцию для prefab файла. Возвращает True если drag начат."""
        index = self._drag_start_index
        if index is None or not index.isValid():
            return False

        file_path = self._file_model.filePath(index)
        if not file_path:
            return False

        # Только для prefab файлов
        if not any(file_path.lower().endswith(ext) for ext in self.DRAGGABLE_EXTENSIONS):
            return False

        drag = QDrag(self._list_view)
        mime_data = create_asset_path_mime_data(file_path)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)
        return True


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

    # Глобальный путь к текущему проекту (устанавливается в set_root_path)
    current_project_path: Path | None = None

    # Расширения файлов, которые показываем
    SUPPORTED_EXTENSIONS = {
        ".scene",     # Сцены
        ".prefab",    # Префабы
        ".shader",    # Шейдеры
        ".material",  # Материалы
        ".pipeline",  # Рендер-пайплайны
        ".voxels",    # Воксельные сетки
        ".json",      # Конфиги
        ".png", ".jpg", ".jpeg", ".tga", ".bmp",  # Текстуры
        ".stl", ".obj", ".fbx", ".gltf", ".glb",  # Модели
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

        # Провайдер иконок для ассетов
        self._icon_provider = AssetIconProvider()

        # Модели файловой системы
        self._dir_model = QFileSystemModel()
        self._file_model = QFileSystemModel()

        # Устанавливаем провайдер иконок
        self._file_model.setIconProvider(self._icon_provider)

        # Фильтр для drag prefab файлов (устанавливается на viewport)
        self._drag_filter = PrefabDragFilter(file_list, self._file_model, parent=file_list)
        file_list.viewport().installEventFilter(self._drag_filter)

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
        # Drag обрабатывается через PrefabDragFilter

        # Подключаем сигналы
        self._dir_tree.selectionModel().currentChanged.connect(self._on_dir_selected)
        self._file_list.doubleClicked.connect(self._on_file_double_click)
        self._file_list.clicked.connect(self._on_file_click)
        self._file_list.customContextMenuRequested.connect(self._show_file_context_menu)

        # Горячая клавиша Delete для удаления
        self._delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self._file_list)
        self._delete_shortcut.activated.connect(self._on_delete_pressed)

        # Устанавливаем корневую директорию
        if root_path is not None:
            self.set_root_path(root_path)

    def set_root_path(self, path: str | Path) -> None:
        """Установить корневую директорию проекта."""
        path = Path(path).resolve()
        if not path.exists():
            return

        self._root_path = path
        ProjectBrowser.current_project_path = path
        self._current_file_dir = path  # Текущая директория в правой панели
        path_str = str(path)

        # Устанавливаем корень для обеих моделей
        self._dir_model.setRootPath(path_str)
        self._file_model.setRootPath(path_str)

        # Устанавливаем корневой индекс для дерева — показываем сам корень
        # (его содержимое будет видно, но выйти выше нельзя)
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
        """Текущая директория (отображаемая в правой панели)."""
        return getattr(self, "_current_file_dir", None) or self._root_path

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

        dir_path = Path(self._dir_model.filePath(current))

        # Проверяем, что не выходим за пределы корня проекта
        if self._root_path is not None:
            try:
                dir_path.relative_to(self._root_path)
            except ValueError:
                # Пытаемся выйти за пределы корня — возвращаемся
                if previous.isValid():
                    self._dir_tree.setCurrentIndex(previous)
                return

        self._current_file_dir = dir_path

        # Обновляем список файлов для выбранной директории
        file_index = self._file_model.index(str(dir_path))
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
        # Проверяем, что не выходим за пределы корня
        if self._root_path is not None:
            try:
                dir_path.relative_to(self._root_path)
            except ValueError:
                return

        self._current_file_dir = dir_path

        # Находим и выбираем директорию в дереве
        dir_index = self._dir_model.index(str(dir_path))
        if dir_index.isValid():
            self._dir_tree.setCurrentIndex(dir_index)
            self._dir_tree.expand(dir_index)

        # Обновляем список файлов
        file_index = self._file_model.index(str(dir_path))
        self._file_list.setRootIndex(file_index)

    def _can_go_up(self) -> bool:
        """Проверяет, можно ли перейти на уровень вверх."""
        current = self.current_directory
        root = self._root_path
        if current is None or root is None:
            return False
        return current != root

    def _go_up(self) -> None:
        """Перейти на уровень вверх."""
        current = self.current_directory
        if current is None or not self._can_go_up():
            return

        parent = current.parent
        self._navigate_to_directory(parent)

    def _go_to_root(self) -> None:
        """Перейти в корень проекта."""
        if self._root_path is not None:
            self._navigate_to_directory(self._root_path)

    def _show_file_context_menu(self, pos) -> None:
        """Показать контекстное меню для файла."""
        index = self._file_list.indexAt(pos)

        menu = QMenu(self._file_list)

        # Навигация — если мы не в корне
        if self._can_go_up():
            go_up_action = QAction("Go Up", self._file_list)
            go_up_action.triggered.connect(self._go_up)
            menu.addAction(go_up_action)

            go_root_action = QAction("Go to Root", self._file_list)
            go_root_action.triggered.connect(self._go_to_root)
            menu.addAction(go_root_action)

            menu.addSeparator()

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

            # Удалить
            delete_action = QAction("Delete", self._file_list)
            delete_action.triggered.connect(lambda: self._delete_item(file_path))
            menu.addAction(delete_action)

            menu.addSeparator()

        # --- Подменю Create ---
        create_menu = menu.addMenu("Create")

        create_dir_action = QAction("Directory...", self._file_list)
        create_dir_action.triggered.connect(self._create_directory)
        create_menu.addAction(create_dir_action)

        create_menu.addSeparator()

        create_material_action = QAction("Material...", self._file_list)
        create_material_action.triggered.connect(self._create_material)
        create_menu.addAction(create_material_action)

        create_shader_action = QAction("Shader...", self._file_list)
        create_shader_action.triggered.connect(self._create_shader)
        create_menu.addAction(create_shader_action)

        create_line_shader_action = QAction("Line Shader...", self._file_list)
        create_line_shader_action.triggered.connect(self._create_line_shader)
        create_menu.addAction(create_line_shader_action)

        create_component_action = QAction("Component...", self._file_list)
        create_component_action.triggered.connect(self._create_component)
        create_menu.addAction(create_component_action)

        create_pipeline_action = QAction("Render Pipeline...", self._file_list)
        create_pipeline_action.triggered.connect(self._create_pipeline)
        create_menu.addAction(create_pipeline_action)

        create_menu.addSeparator()

        create_prefab_action = QAction("Prefab...", self._file_list)
        create_prefab_action.triggered.connect(self._create_prefab)
        create_menu.addAction(create_prefab_action)

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

    def _on_delete_pressed(self) -> None:
        """Обработчик нажатия клавиши Delete."""
        selected = self.selected_file
        if selected is not None:
            self._delete_item(selected)

    def _delete_item(self, path: Path) -> None:
        """Удалить файл или директорию."""
        import shutil

        if path.is_file():
            msg = f"Delete file '{path.name}'?"
        else:
            msg = f"Delete directory '{path.name}' and all its contents?"

        reply = QMessageBox.question(
            self._file_list,
            "Confirm Delete",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
            self._refresh()
        except OSError as e:
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"Failed to delete: {e}",
            )

    def _create_material(self) -> None:
        """Создать новый файл материала."""
        current_dir = self.current_directory
        if current_dir is None:
            return

        name, ok = QInputDialog.getText(
            self._file_list,
            "Create Material",
            "Material name:",
            text="NewMaterial",
        )

        if not ok or not name:
            return

        # Убираем расширение если пользователь его ввёл
        if name.endswith(".material"):
            name = name[:-9]

        file_path = current_dir / f"{name}.material"

        if file_path.exists():
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"File '{file_path.name}' already exists.",
            )
            return

        # Болванка материала
        template = '''{
    "shader": "DefaultShader",
    "uniforms": {
    },
    "textures": {
    }
}
'''

        try:
            file_path.write_text(template, encoding="utf-8")
            self._refresh()
        except OSError as e:
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"Failed to create material: {e}",
            )

    def _create_shader(self) -> None:
        """Создать новый файл шейдера."""
        current_dir = self.current_directory
        if current_dir is None:
            return

        name, ok = QInputDialog.getText(
            self._file_list,
            "Create Shader",
            "Shader name:",
            text="NewShader",
        )

        if not ok or not name:
            return

        # Убираем расширение если пользователь его ввёл
        if name.endswith(".shader"):
            name = name[:-7]

        file_path = current_dir / f"{name}.shader"

        if file_path.exists():
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"File '{file_path.name}' already exists.",
            )
            return

        # Болванка шейдера
        template = f'''@program {name}

@phase opaque

@property Float u_time = 0.0
@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)

@stage vertex
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec2 v_texcoord;

void main() {{
    v_normal = mat3(u_model) * a_normal;
    v_texcoord = a_texcoord;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}}

@stage fragment
#version 330 core

in vec3 v_normal;
in vec2 v_texcoord;

uniform vec4 u_color;

out vec4 frag_color;

void main() {{
    vec3 normal = normalize(v_normal);
    float light = max(dot(normal, vec3(0.0, 1.0, 0.0)), 0.2);
    frag_color = vec4(u_color.rgb * light, u_color.a);
}}
'''

        try:
            file_path.write_text(template, encoding="utf-8")
            self._refresh()
        except OSError as e:
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"Failed to create shader: {e}",
            )

    def _create_line_shader(self) -> None:
        """Создать шейдер для линий с billboard geometry shader."""
        current_dir = self.current_directory
        if current_dir is None:
            return

        name, ok = QInputDialog.getText(
            self._file_list,
            "Create Line Shader",
            "Shader name:",
            text="LineShader",
        )

        if not ok or not name:
            return

        # Убираем расширение если пользователь его ввёл
        if name.endswith(".shader"):
            name = name[:-7]

        file_path = current_dir / f"{name}.shader"

        if file_path.exists():
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"File '{file_path.name}' already exists.",
            )
            return

        # Шаблон billboard line shader с круглыми стыками
        template = f'''@program {name}

@phase opaque

@property Float u_width = 0.05
@property Color u_color = Color(1.0, 1.0, 1.0, 1.0)

// ============================================================
// Vertex Shader — просто передаёт позицию в мировых координатах
// ============================================================
@stage vertex
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;

out vec3 v_world_pos;

void main() {{
    v_world_pos = (u_model * vec4(a_position, 1.0)).xyz;
}}

// ============================================================
// Geometry Shader — разворачивает GL_LINES в billboard quads
// с круглыми заглушками на концах для сглаживания стыков
// ============================================================
@stage geometry
#version 330 core

layout(lines) in;
// 4 для quad + 2 круга * 6 сегментов * 3 вершины = 4 + 36 = 40
layout(triangle_strip, max_vertices = 48) out;

in vec3 v_world_pos[];

uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_width;

const int CIRCLE_SEGMENTS = 6;
const float PI = 3.14159265359;

// Позиция камеры (извлекаем из view matrix)
vec3 get_camera_pos(mat4 view) {{
    mat3 rot = mat3(view);
    vec3 d = vec3(view[3]);
    return -d * rot;
}}

// Рисует полный круг в точке стыка (отдельными треугольниками)
void emit_circle(vec3 center, vec3 perp, vec3 tangent, float radius, mat4 vp) {{
    for (int i = 0; i < CIRCLE_SEGMENTS; i++) {{
        float a0 = float(i) / float(CIRCLE_SEGMENTS) * 2.0 * PI;
        float a1 = float(i + 1) / float(CIRCLE_SEGMENTS) * 2.0 * PI;

        vec3 p0 = center + (perp * cos(a0) + tangent * sin(a0)) * radius;
        vec3 p1 = center + (perp * cos(a1) + tangent * sin(a1)) * radius;

        // Треугольник: center -> p0 -> p1
        gl_Position = vp * vec4(center, 1.0);
        EmitVertex();
        gl_Position = vp * vec4(p0, 1.0);
        EmitVertex();
        gl_Position = vp * vec4(p1, 1.0);
        EmitVertex();
        EndPrimitive();
    }}
}}

void main() {{
    vec3 p0 = v_world_pos[0];
    vec3 p1 = v_world_pos[1];

    vec3 camera_pos = get_camera_pos(u_view);

    // Направление линии
    vec3 line_dir = normalize(p1 - p0);

    // Направление к камере (среднее для обоих концов)
    vec3 mid = (p0 + p1) * 0.5;
    vec3 to_camera = normalize(camera_pos - mid);

    // Перпендикуляр к линии в плоскости, обращённой к камере
    vec3 perp = normalize(cross(line_dir, to_camera));

    float half_width = u_width * 0.5;

    mat4 vp = u_projection * u_view;

    // Основной quad линии
    vec3 v0 = p0 - perp * half_width;
    vec3 v1 = p0 + perp * half_width;
    vec3 v2 = p1 - perp * half_width;
    vec3 v3 = p1 + perp * half_width;

    gl_Position = vp * vec4(v0, 1.0);
    EmitVertex();
    gl_Position = vp * vec4(v1, 1.0);
    EmitVertex();
    gl_Position = vp * vec4(v2, 1.0);
    EmitVertex();
    gl_Position = vp * vec4(v3, 1.0);
    EmitVertex();
    EndPrimitive();

    // Круглые заглушки на обоих концах сегмента
    // tangent = line_dir для ориентации круга в плоскости billboard
    emit_circle(p0, perp, line_dir, half_width, vp);
    emit_circle(p1, perp, line_dir, half_width, vp);
}}

// ============================================================
// Fragment Shader — выводит цвет
// ============================================================
@stage fragment
#version 330 core

uniform vec4 u_color;

out vec4 frag_color;

void main() {{
    frag_color = u_color;
}}
'''

        try:
            file_path.write_text(template, encoding="utf-8")
            self._refresh()
        except OSError as e:
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"Failed to create line shader: {e}",
            )

    def _create_component(self) -> None:
        """Создать новый файл компонента."""
        current_dir = self.current_directory
        if current_dir is None:
            return

        name, ok = QInputDialog.getText(
            self._file_list,
            "Create Component",
            "Component class name:",
            text="NewComponent",
        )

        if not ok or not name:
            return

        # Преобразуем имя класса в snake_case для имени файла
        import re
        file_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

        # Убираем расширение если пользователь его ввёл
        if file_name.endswith(".py"):
            file_name = file_name[:-3]

        file_path = current_dir / f"{file_name}.py"

        if file_path.exists():
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"File '{file_path.name}' already exists.",
            )
            return

        # Болванка компонента
        template = f'''"""
{name} component.
"""

from __future__ import annotations

from termin.visualization.core.component import Component


class {name}(Component):
    """
    Custom component.

    Attributes:
        speed: Movement speed.
    """

    def __init__(self, speed: float = 1.0):
        super().__init__()
        self.speed = speed

    def on_start(self) -> None:
        """Called when the component is first activated."""
        pass

    def on_update(self, dt: float) -> None:
        """Called every frame.

        Args:
            dt: Delta time in seconds.
        """
        pass

    def on_destroy(self) -> None:
        """Called when the component is destroyed."""
        pass
'''

        try:
            file_path.write_text(template, encoding="utf-8")
            self._refresh()
        except OSError as e:
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"Failed to create component: {e}",
            )

    def _create_pipeline(self) -> None:
        """Создать новый файл рендер-пайплайна."""
        import json

        current_dir = self.current_directory
        if current_dir is None:
            return

        name, ok = QInputDialog.getText(
            self._file_list,
            "Create Render Pipeline",
            "Pipeline name:",
            text="NewPipeline",
        )

        if not ok or not name:
            return

        # Убираем расширение если пользователь его ввёл
        if name.endswith(".pipeline"):
            name = name[:-9]

        file_path = current_dir / f"{name}.pipeline"

        if file_path.exists():
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"File '{file_path.name}' already exists.",
            )
            return

        # Болванка пайплайна — базовый набор пассов
        template = {
            "passes": [
                {
                    "type": "SkyBoxPass",
                    "pass_name": "Skybox",
                    "enabled": True,
                    "input_res": "empty",
                    "output_res": "skybox",
                },
                {
                    "type": "ColorPass",
                    "pass_name": "Color",
                    "enabled": True,
                    "input_res": "skybox",
                    "output_res": "color",
                    "shadow_res": None,
                    "phase_mark": "opaque",
                },
                {
                    "type": "PostProcessPass",
                    "pass_name": "PostFX",
                    "enabled": True,
                    "input_res": "color",
                    "output_res": "color_pp",
                    "effects": [],
                },
                {
                    "type": "CanvasPass",
                    "pass_name": "Canvas",
                    "enabled": True,
                    "src": "color_pp",
                    "dst": "color_ui",
                },
                {
                    "type": "PresentToScreenPass",
                    "pass_name": "Present",
                    "enabled": True,
                    "input_res": "color_ui",
                    "output_res": "DISPLAY",
                },
            ],
            "pipeline_specs": [
                {
                    "resource": "empty",
                    "resource_type": "fbo",
                    "clear_color": [0.1, 0.1, 0.1, 1.0],
                    "clear_depth": 1.0,
                }
            ],
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(template, f, indent=2, ensure_ascii=False)
            self._refresh()
        except OSError as e:
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"Failed to create pipeline: {e}",
            )

    def _create_prefab(self) -> None:
        """Создать новый файл префаба."""
        current_dir = self.current_directory
        if current_dir is None:
            return

        name, ok = QInputDialog.getText(
            self._file_list,
            "Create Prefab",
            "Prefab name:",
            text="NewPrefab",
        )

        if not ok or not name:
            return

        # Убираем расширение если пользователь его ввёл
        if name.endswith(".prefab"):
            name = name[:-7]

        file_path = current_dir / f"{name}.prefab"

        if file_path.exists():
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"File '{file_path.name}' already exists.",
            )
            return

        # Создаём пустой префаб через PrefabPersistence
        try:
            from termin.editor.prefab_persistence import PrefabPersistence
            from termin.visualization.core.resources import ResourceManager

            persistence = PrefabPersistence(ResourceManager.instance())
            persistence.create_empty(file_path, name=name)
            self._refresh()
        except Exception as e:
            QMessageBox.warning(
                self._file_list,
                "Error",
                f"Failed to create prefab: {e}",
            )
