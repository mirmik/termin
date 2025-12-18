"""
Диалог просмотра состояния ResourceManager.

Показывает зарегистрированные материалы, меши, текстуры и компоненты.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QDialogButtonBox,
    QPushButton,
    QLabel,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from termin.editor.project_file_watcher import ProjectFileWatcher

from termin.visualization.core.resources import ResourceManager


class ResourceManagerViewer(QDialog):
    """
    Диалог просмотра состояния ResourceManager.
    """

    def __init__(
        self,
        resource_manager: ResourceManager,
        project_file_watcher: "ProjectFileWatcher | None" = None,
        parent=None,
    ):
        super().__init__(parent)
        self._resource_manager = resource_manager
        self._project_file_watcher = project_file_watcher

        self.setWindowTitle("Resource Manager")
        self.setMinimumSize(600, 400)

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        """Создаёт UI диалога."""
        layout = QVBoxLayout(self)

        # Табы для разных типов ресурсов
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        # Материалы
        self._materials_tree = QTreeWidget()
        self._materials_tree.setHeaderLabels(["Name", "Source", "Phases", "Shader"])
        self._materials_tree.setAlternatingRowColors(True)
        self._tab_widget.addTab(self._materials_tree, "Materials")

        # Меши
        self._meshes_tree = QTreeWidget()
        self._meshes_tree.setHeaderLabels(["Name", "Vertices", "Indices"])
        self._meshes_tree.setAlternatingRowColors(True)
        self._tab_widget.addTab(self._meshes_tree, "Meshes")

        # Текстуры
        self._textures_tree = QTreeWidget()
        self._textures_tree.setHeaderLabels(["Name", "Source", "Size"])
        self._textures_tree.setAlternatingRowColors(True)
        self._tab_widget.addTab(self._textures_tree, "Textures")

        # Компоненты
        self._components_tree = QTreeWidget()
        self._components_tree.setHeaderLabels(["Name", "Module"])
        self._components_tree.setAlternatingRowColors(True)
        self._tab_widget.addTab(self._components_tree, "Components")

        # Отслеживаемые файлы
        self._watched_tree = QTreeWidget()
        self._watched_tree.setHeaderLabels(["File", "Resources"])
        self._watched_tree.setAlternatingRowColors(True)
        self._tab_widget.addTab(self._watched_tree, "Watched Files")

        # Статус
        self._status_label = QLabel()
        layout.addWidget(self._status_label)

        # Кнопки
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def refresh(self) -> None:
        """Обновляет содержимое всех вкладок."""
        self._refresh_materials()
        self._refresh_meshes()
        self._refresh_textures()
        self._refresh_components()
        self._refresh_watched()
        self._update_status()

    def _refresh_materials(self) -> None:
        """Обновляет список материалов."""
        self._materials_tree.clear()

        for name, mat in sorted(self._resource_manager.materials.items()):
            source = mat.source_path or "(inline)"
            phases = len(mat.phases)
            shader_path = getattr(mat, 'shader_path', None) or ""

            item = QTreeWidgetItem([name, source, str(phases), shader_path])
            self._materials_tree.addTopLevelItem(item)

            # Добавляем фазы как дочерние элементы
            for i, phase in enumerate(mat.phases):
                phase_item = QTreeWidgetItem([
                    f"Phase {i}: {phase.phase_mark}",
                    f"priority={phase.priority}",
                    f"uniforms: {len(phase.uniforms)}",
                    f"textures: {len(phase.textures)}",
                ])
                item.addChild(phase_item)

        self._materials_tree.resizeColumnToContents(0)
        self._materials_tree.resizeColumnToContents(1)

    def _refresh_meshes(self) -> None:
        """Обновляет список мешей."""
        self._meshes_tree.clear()

        for name, asset in sorted(self._resource_manager._mesh_assets.items()):
            vertices = "?"
            indices = "?"

            # Пытаемся получить информацию о меше из asset
            mesh = asset.data
            if mesh is not None:
                if hasattr(mesh, 'vertices') and mesh.vertices is not None:
                    vertices = str(len(mesh.vertices))
                if hasattr(mesh, 'triangles') and mesh.triangles is not None:
                    indices = str(len(mesh.triangles) * 3)

            item = QTreeWidgetItem([name, vertices, indices])
            self._meshes_tree.addTopLevelItem(item)

        self._meshes_tree.resizeColumnToContents(0)

    def _refresh_textures(self) -> None:
        """Обновляет список текстур."""
        self._textures_tree.clear()

        for name, asset in sorted(self._resource_manager._texture_assets.items()):
            source = str(asset.source_path) if asset.source_path else "(generated)"
            size = f"{asset.width}x{asset.height}"

            item = QTreeWidgetItem([name, source, size])
            self._textures_tree.addTopLevelItem(item)

        self._textures_tree.resizeColumnToContents(0)
        self._textures_tree.resizeColumnToContents(1)

    def _refresh_components(self) -> None:
        """Обновляет список компонентов."""
        self._components_tree.clear()

        for name, cls in sorted(self._resource_manager.components.items()):
            module = cls.__module__ if hasattr(cls, '__module__') else "?"

            item = QTreeWidgetItem([name, module])
            self._components_tree.addTopLevelItem(item)

        self._components_tree.resizeColumnToContents(0)
        self._components_tree.resizeColumnToContents(1)

    def _refresh_watched(self) -> None:
        """Обновляет список отслеживаемых файлов и директорий."""
        self._watched_tree.clear()

        watcher = self._project_file_watcher
        if watcher is None:
            return

        # By Extension — статистика по всем расширениям
        all_files_stats = watcher.get_all_files_by_extension()
        if all_files_stats:
            total_files = watcher.get_all_files_count()
            all_item = QTreeWidgetItem(["By Extension", f"{total_files} files"])
            self._watched_tree.addTopLevelItem(all_item)
            for ext, count in all_files_stats.items():
                child = QTreeWidgetItem([ext, str(count)])
                all_item.addChild(child)

        # Директории
        watched_dirs = watcher.watched_dirs
        if watched_dirs:
            dirs_item = QTreeWidgetItem(["Watched Directories", f"{len(watched_dirs)} dirs"])
            self._watched_tree.addTopLevelItem(dirs_item)
            for path in sorted(watched_dirs):
                child = QTreeWidgetItem([path, "directory"])
                dirs_item.addChild(child)

        # Файлы по типам (из процессоров)
        for processor in watcher.get_all_processors():
            tracked = processor.get_tracked_files()
            if tracked:
                type_name = processor.resource_type.capitalize()
                type_item = QTreeWidgetItem([f"{type_name} Files", f"{len(tracked)} files"])
                self._watched_tree.addTopLevelItem(type_item)
                for path, names in sorted(tracked.items()):
                    resources = ", ".join(sorted(names)) if names else "(pending)"
                    child = QTreeWidgetItem([path, resources])
                    type_item.addChild(child)

        self._watched_tree.expandAll()
        self._watched_tree.resizeColumnToContents(0)

    def _update_status(self) -> None:
        """Обновляет строку статуса."""
        rm = self._resource_manager
        watcher = self._project_file_watcher

        if watcher is not None:
            watching = "enabled" if watcher.is_enabled else "disabled"
            watched_dirs = len(watcher.watched_dirs)
            watched_files = watcher.get_file_count()
        else:
            watching = "disabled"
            watched_dirs = 0
            watched_files = 0

        self._status_label.setText(
            f"Materials: {len(rm.materials)} | "
            f"Meshes: {len(rm._mesh_assets)} | "
            f"Textures: {len(rm._texture_assets)} | "
            f"Components: {len(rm.components)} | "
            f"Watching: {watching} ({watched_dirs} dirs, {watched_files} files)"
        )
