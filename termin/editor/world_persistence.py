"""World persistence - save/load/reset functionality.

WorldPersistence is the SINGLE OWNER of Scene lifecycle.
All other components should access scene via world_persistence.scene property.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.resources import ResourceManager


def numpy_encoder(obj):
    """Конвертер numpy типов в Python типы для JSON."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class WorldPersistence:
    """
    Единственный владелец жизненного цикла Scene.

    Ответственности:
    - Владение Scene (создание, уничтожение, замена)
    - Сериализация/десериализация сцены и ресурсов
    - Атомарная запись файлов
    - Уведомление подписчиков о смене сцены

    ВАЖНО: Все остальные компоненты должны получать scene через
    свойство world_persistence.scene, а не хранить свою ссылку.
    """

    def __init__(
        self,
        scene: "Scene",
        resource_manager: "ResourceManager",
        scene_factory: Optional[Callable[[], "Scene"]] = None,
        on_scene_changed: Optional[Callable[["Scene"], None]] = None,
        get_editor_camera_data: Optional[Callable[[], dict]] = None,
        set_editor_camera_data: Optional[Callable[[dict], None]] = None,
        get_selected_entity_name: Optional[Callable[[], str | None]] = None,
        select_entity_by_name: Optional[Callable[[str], None]] = None,
        get_displays_data: Optional[Callable[[], list]] = None,
        set_displays_data: Optional[Callable[[list], None]] = None,
        rescan_file_resources: Optional[Callable[[], None]] = None,
    ):
        """
        Args:
            scene: Начальная сцена
            resource_manager: Менеджер ресурсов
            scene_factory: Фабрика для создания новой пустой сцены.
                          Если None, используется Scene()
            on_scene_changed: Колбэк, вызываемый при смене сцены.
                             Получает новую сцену как аргумент.
            get_editor_camera_data: Колбэк для получения данных камеры редактора.
            set_editor_camera_data: Колбэк для установки данных камеры редактора.
            get_selected_entity_name: Колбэк для получения имени выделенной сущности.
            select_entity_by_name: Колбэк для выделения сущности по имени.
            get_displays_data: Колбэк для получения данных дисплеев/вьюпортов.
            set_displays_data: Колбэк для восстановления дисплеев/вьюпортов.
            rescan_file_resources: Колбэк для пересканирования файловых ресурсов проекта.
        """
        self._scene = scene
        self._resource_manager = resource_manager
        self._scene_factory = scene_factory
        self._on_scene_changed = on_scene_changed
        self._get_editor_camera_data = get_editor_camera_data
        self._set_editor_camera_data = set_editor_camera_data
        self._get_selected_entity_name = get_selected_entity_name
        self._select_entity_by_name = select_entity_by_name
        self._get_displays_data = get_displays_data
        self._set_displays_data = set_displays_data
        self._rescan_file_resources = rescan_file_resources
        self._current_scene_path: str | None = None

    @property
    def scene(self) -> "Scene":
        """Текущая сцена. Всегда используйте это свойство для доступа к сцене."""
        return self._scene

    @property
    def resource_manager(self) -> "ResourceManager":
        """Менеджер ресурсов."""
        return self._resource_manager

    @property
    def current_scene_path(self) -> str | None:
        """Путь к текущему файлу сцены (None если сцена не сохранена)."""
        return self._current_scene_path

    def _create_new_scene(self) -> "Scene":
        """Создаёт новую пустую сцену."""
        if self._scene_factory is not None:
            return self._scene_factory()
        from termin.visualization.core.scene import Scene
        return Scene()

    def _replace_scene(self, new_scene: "Scene") -> None:
        """
        Заменяет текущую сцену на новую и уведомляет подписчиков.
        """
        old_scene = self._scene
        self._scene = new_scene

        # Уведомляем подписчиков
        if self._on_scene_changed is not None:
            self._on_scene_changed(new_scene)

    def replace_scene(self, new_scene: "Scene", reset_path: bool = True) -> None:
        """
        Public method to replace current scene.

        Used by PrefabEditController for isolation mode.

        Args:
            new_scene: New scene to set as current.
            reset_path: If True, resets current_scene_path to None.
        """
        if reset_path:
            self._current_scene_path = None
        self._replace_scene(new_scene)

    def save(self, file_path: str) -> dict:
        """
        Сохраняет сцену в JSON файл.

        Формат файла .scene:
        {
            "version": "1.0",
            "scene": { ... },
            "editor": {
                "camera": { ... },
                "selected_entity": "..."
            },
            "resources": { ... }
        }

        Returns:
            Статистика: entities, materials, meshes count
        """
        # Получаем данные камеры редактора
        editor_camera_data = None
        if self._get_editor_camera_data is not None:
            editor_camera_data = self._get_editor_camera_data()

        # Получаем имя выделенной сущности
        selected_entity_name = None
        if self._get_selected_entity_name is not None:
            selected_entity_name = self._get_selected_entity_name()

        # Получаем данные дисплеев
        displays_data = None
        if self._get_displays_data is not None:
            displays_data = self._get_displays_data()

        # Формируем данные редактора
        editor_data = {}
        if editor_camera_data is not None:
            editor_data["camera"] = editor_camera_data
        if selected_entity_name is not None:
            editor_data["selected_entity"] = selected_entity_name
        if displays_data is not None:
            editor_data["displays"] = displays_data

        data = {
            "version": "1.0",
            "scene": self._scene.serialize(),
            "editor": editor_data,
            "resources": self._resource_manager.serialize(),
        }

        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=numpy_encoder)

        # Атомарная запись
        dir_path = os.path.dirname(file_path) or "."
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            dir=dir_path,
            delete=False
        ) as f:
            f.write(json_str)
            temp_path = f.name

        os.replace(temp_path, file_path)

        # Запоминаем путь к сцене
        self._current_scene_path = file_path

        return {
            "entities": sum(1 for e in self._scene.entities if e.transform.parent is None and e.serializable),
            "materials": len(self._resource_manager.materials),
            "meshes": len(self._resource_manager._mesh_assets),
        }

    def load(self, file_path: str) -> dict:
        """
        Загружает мир из JSON файла.
        Создаёт НОВУЮ сцену и заменяет текущую.

        Args:
            file_path: Путь к файлу

        Returns:
            Статистика: loaded_entities, materials, meshes count
        """
        with open(file_path, "r", encoding="utf-8") as f:
            json_str = f.read()
        data = json.loads(json_str)

        result = self._restore_from_data(data)

        # Запоминаем путь к сцене
        self._current_scene_path = file_path

        return result

    def reset(self) -> None:
        """
        Полная очистка мира.
        Создаёт НОВУЮ пустую сцену.
        """
        # Сбрасываем путь к сцене
        self._current_scene_path = None

        # Создаём новую пустую сцену
        new_scene = self._create_new_scene()
        self._replace_scene(new_scene)

    def save_state(self) -> dict:
        """
        Сохраняет текущее состояние в память (для game mode).

        Returns:
            Сериализованное состояние (глубокая копия)
        """
        # Получаем данные камеры редактора
        editor_camera_data = None
        if self._get_editor_camera_data is not None:
            editor_camera_data = self._get_editor_camera_data()

        # Получаем имя выделенной сущности
        selected_entity_name = None
        if self._get_selected_entity_name is not None:
            selected_entity_name = self._get_selected_entity_name()

        # Получаем данные дисплеев
        displays_data = None
        if self._get_displays_data is not None:
            displays_data = self._get_displays_data()

        # Формируем данные редактора
        editor_data = {}
        if editor_camera_data is not None:
            editor_data["camera"] = editor_camera_data
        if selected_entity_name is not None:
            editor_data["selected_entity"] = selected_entity_name
        if displays_data is not None:
            editor_data["displays"] = displays_data

        data = {
            "resources": self._resource_manager.serialize(),
            "scene": self._scene.serialize(),
            "editor": editor_data,
        }
        return copy.deepcopy(data)

    def restore_state(self, state: dict) -> None:
        """
        Восстанавливает состояние из памяти (для game mode).
        Создаёт НОВУЮ сцену из сохранённых данных.

        Args:
            state: Сохранённое состояние из save_state()
        """
        self._restore_from_data(state)

    def _restore_from_data(self, data: dict) -> dict:
        """
        Внутренний метод восстановления из данных.
        Создаёт новую сцену и загружает в неё данные.

        Поддерживает новый формат .scene:
        {
            "scene": {...},
            "editor": {"camera": {...}, "selected_entity": "..."},
            "resources": {...}
        }

        И старый формат .world.json для обратной совместимости:
        {
            "scenes": [{...}],
            "resources": {...}
        }
        """

        # Создаём новую сцену
        new_scene = self._create_new_scene()

        # Загружаем данные в новую сцену
        # Поддержка нового формата "scene" и старого "scenes"
        scene_data = data.get("scene") or (data.get("scenes", [None])[0])
        loaded_count = 0
        if scene_data:
            loaded_count = new_scene.load_from_data(
                scene_data,
                context=None,
                update_settings=True
            )

        # Заменяем текущую сцену
        self._replace_scene(new_scene)

        # Уведомляем компоненты о старте в режиме редактора
        new_scene.notify_editor_start()

        # Восстанавливаем состояние редактора
        # Новый формат: data["editor"]["camera"], data["editor"]["selected_entity"]
        # Старый формат: scene_data["editor_camera"], data["editor_state"]["selected_entity_name"]
        editor_data = data.get("editor", {})

        # Камера редактора
        editor_camera_data = editor_data.get("camera")
        # Обратная совместимость: старый формат в scene_data
        if editor_camera_data is None and scene_data:
            editor_camera_data = scene_data.get("editor_camera")
        if editor_camera_data is not None and self._set_editor_camera_data is not None:
            self._set_editor_camera_data(editor_camera_data)

        # Выделение
        selected_name = editor_data.get("selected_entity")
        # Обратная совместимость: старый формат
        if selected_name is None:
            editor_state = data.get("editor_state", {})
            selected_name = editor_state.get("selected_entity_name")
        if selected_name and self._select_entity_by_name is not None:
            self._select_entity_by_name(selected_name)

        # Дисплеи и вьюпорты
        displays_data = editor_data.get("displays")
        if displays_data is not None and self._set_displays_data is not None:
            self._set_displays_data(displays_data)

        return {
            "loaded_entities": loaded_count,
            "materials": len(self._resource_manager.materials),
            "meshes": len(self._resource_manager._mesh_assets),
        }
