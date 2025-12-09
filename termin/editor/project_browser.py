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
        ".scene",     # Сцены
        ".shader",    # Шейдеры
        ".material",  # Материалы
        ".json",      # Конфиги
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

        create_component_action = QAction("Component...", self._file_list)
        create_component_action.triggered.connect(self._create_component)
        create_menu.addAction(create_component_action)

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
    "shader": "path/to/shader.shader",
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
