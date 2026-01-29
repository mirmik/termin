from __future__ import annotations

from pathlib import Path
from typing import Callable, TYPE_CHECKING

from PyQt6.QtWidgets import QFileDialog, QListView, QTreeView

from termin.editor.project_browser import ProjectBrowser
from termin.editor.settings import EditorSettings
from termin.editor.external_editor import open_in_text_editor

if TYPE_CHECKING:
    from termin.editor.inspector_controller import InspectorController


class EditorProjectController:
    def __init__(
        self,
        parent,
        settings: EditorSettings,
        inspector_controller: "InspectorController | None",
        log_message: Callable[[str], None],
        update_window_title: Callable[[], None],
        on_project_reset: Callable[[], None],
        on_load_scene: Callable[[str], None],
        on_open_prefab: Callable[[str], None],
    ) -> None:
        self._parent = parent
        self._settings = settings
        self._inspector_controller = inspector_controller
        self._log_message = log_message
        self._update_window_title = update_window_title
        self._on_project_reset = on_project_reset
        self._on_load_scene = on_load_scene
        self._on_open_prefab = on_open_prefab

        self._project_browser: ProjectBrowser | None = None
        self._current_project_file: Path | None = None
        self._project_name: str | None = None

    @property
    def project_name(self) -> str | None:
        return self._project_name

    @property
    def project_browser(self) -> ProjectBrowser | None:
        return self._project_browser

    @property
    def current_project_file(self) -> Path | None:
        return self._current_project_file

    def get_project_path(self) -> str | None:
        if self._project_browser is None or self._project_browser.root_path is None:
            return None
        return str(self._project_browser.root_path)

    def get_project_root_path(self) -> Path | None:
        if self._project_browser is None:
            return None
        return self._project_browser.root_path

    def init_project_browser(
        self,
        project_dir_tree: QTreeView | None,
        project_file_list: QListView | None,
    ) -> ProjectBrowser | None:
        if project_dir_tree is None or project_file_list is None:
            return None

        # Загружаем последний открытый проект (если есть валидный .terminproj)
        project_file = self._settings.get_last_project_file()

        project_root: Path | None = None
        if project_file is not None:
            project_root = project_file.parent
            self._current_project_file = project_file

        self._project_browser = ProjectBrowser(
            dir_tree=project_dir_tree,
            file_list=project_file_list,
            root_path=project_root,
            on_file_selected=self._on_project_file_selected,
            on_file_double_clicked=self._on_project_file_double_clicked,
        )

        # Обновляем имя проекта и заголовок окна
        if project_root is not None:
            self._project_name = project_root.name
            # Загружаем настройки проекта
            from termin.project.settings import ProjectSettingsManager
            ProjectSettingsManager.instance().set_project_path(project_root)
            # Загружаем настройки навигации для проекта
            from termin.navmesh.settings import NavigationSettingsManager
            NavigationSettingsManager.instance().set_project_path(project_root)
            # Загружаем C++ модули
            self._load_project_modules(project_root)
        else:
            self._project_name = None
        self._update_window_title()

        return self._project_browser

    def new_project(self) -> None:
        """Создать новый проект (.terminproj файл)."""
        current_dir = str(Path.cwd())
        if self._current_project_file is not None:
            current_dir = str(self._current_project_file.parent)

        file_path, _ = QFileDialog.getSaveFileName(
            self._parent,
            "Create New Project",
            current_dir,
            "Termin Project (*.terminproj)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )

        if not file_path:
            return

        # Добавляем расширение если не указано
        if not file_path.endswith(".terminproj"):
            file_path += ".terminproj"

        project_file = Path(file_path)

        # Создаём пустой файл проекта (пока просто пустой JSON)
        import json
        project_data = {
            "version": 1,
            "name": project_file.stem,
        }
        project_file.write_text(json.dumps(project_data, indent=2), encoding="utf-8")

        self.load_project_file(project_file)

    def open_project(self) -> None:
        """Открыть существующий проект (.terminproj файл)."""
        current_dir = str(Path.cwd())
        if self._current_project_file is not None:
            current_dir = str(self._current_project_file.parent)

        file_path, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Open Project",
            current_dir,
            "Termin Project (*.terminproj)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )

        if not file_path:
            return

        project_file = Path(file_path)
        if not project_file.exists() or project_file.suffix != ".terminproj":
            return

        self.load_project_file(project_file)

    def load_project_file(self, project_file: Path) -> None:
        """Загрузить проект из файла .terminproj."""
        project_root = project_file.parent

        self._current_project_file = project_file
        self._project_name = project_root.name

        if self._project_browser is not None:
            self._project_browser.set_root_path(str(project_root))

        self._update_window_title()

        # Сохраняем путь для следующего запуска
        self._settings.set_last_project_file(project_file)

        # Загружаем настройки проекта
        from termin.project.settings import ProjectSettingsManager
        ProjectSettingsManager.instance().set_project_path(project_root)

        # Загружаем настройки навигации для проекта
        from termin.navmesh.settings import NavigationSettingsManager
        NavigationSettingsManager.instance().set_project_path(project_root)

        self._log_message(f"Opened project: {project_file}")

        # Загружаем C++ модули
        self._load_project_modules(project_root)

        # Сбрасываем сцену и пересканируем ресурсы
        self._on_project_reset()

    def _load_project_modules(self, project_root: Path) -> None:
        """Load all C++ modules from the project directory."""
        from termin._native import log
        from termin.editor.module_scanner import ModuleScanner

        log.info(f"[ProjectController] Loading modules from: {project_root}")

        scanner = ModuleScanner(
            on_module_loaded=self._on_module_loaded,
        )
        loaded, failed = scanner.scan_and_load(str(project_root))

        if loaded > 0:
            self._log_message(f"Loaded {loaded} C++ module(s)")
        if failed > 0:
            self._log_message(f"Failed to load {failed} C++ module(s)")

    def _on_module_loaded(self, name: str, success: bool, error: str) -> None:
        """Callback for module load events."""
        if success:
            self._log_message(f"Loaded module: {name}")
        else:
            self._log_message(f"Failed to load module {name}: {error}")

    def _on_project_file_selected(self, file_path) -> None:
        """Обработчик выбора файла в Project Browser (одинарный клик)."""
        if self._inspector_controller is None:
            return

        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".material":
            # Материал — открываем в инспекторе материалов
            self._inspector_controller.show_material_inspector_for_file(str(path))
        elif suffix == ".pipeline":
            # Пайплайн — открываем в инспекторе пайплайнов
            self._inspector_controller.show_pipeline_inspector_for_file(str(path))
        elif suffix in (".png", ".jpg", ".jpeg", ".tga", ".bmp"):
            # Текстура — открываем в инспекторе текстур
            self._inspector_controller.show_texture_inspector_for_file(str(path))
        elif suffix in (".stl", ".obj"):
            # Меш — открываем в инспекторе мешей
            self._inspector_controller.show_mesh_inspector_for_file(str(path))
        elif suffix in (".glb", ".gltf"):
            # GLB — открываем в инспекторе GLB
            self._inspector_controller.show_glb_inspector_for_file(str(path))

    def _on_project_file_double_clicked(self, file_path) -> None:
        """Обработчик двойного клика на файл в Project Browser."""
        path = Path(file_path)

        # Обработка разных типов файлов
        if path.suffix == ".scene":
            # Это файл сцены — загружаем
            self._on_load_scene(str(path))

        elif path.suffix == ".prefab":
            # Это файл префаба — открываем в режиме изоляции
            self._on_open_prefab(str(path))

        elif path.suffix in (".png", ".jpg", ".jpeg", ".tga", ".bmp", ".hdr",
                               ".stl", ".obj", ".glb", ".gltf", ".fbx",
                               ".wav", ".mp3", ".ogg",
                               ".dll", ".so", ".pyd", ".exe"):
            # Бинарные файлы — не открываем в текстовом редакторе
            self._log_message(f"Cannot open binary file: {path.name}")

        else:
            # Все остальные файлы — открываем в текстовом редакторе
            open_in_text_editor(str(path), parent=self._parent, log_message=self._log_message)
