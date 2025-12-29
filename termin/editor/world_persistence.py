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


def _validate_serializable(obj, path: str = ""):
    """Проверяет, что объект содержит только JSON-сериализуемые типы.

    Допустимые типы: dict, list, str, int, float, bool, None, numpy types.
    Raises TypeError с путём к невалидному объекту.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return
    if isinstance(obj, (np.floating, np.integer)):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _validate_serializable(v, f"{path}.{k}" if path else k)
        return
    if isinstance(obj, (list, tuple, np.ndarray)):
        for i, v in enumerate(obj):
            _validate_serializable(v, f"{path}[{i}]")
        return
    raise TypeError(f"Non-serializable type {type(obj).__name__} at path: {path or 'root'}")


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
        get_expanded_entities: Optional[Callable[[], list[str]]] = None,
        set_expanded_entities: Optional[Callable[[list[str]], None]] = None,
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
            get_expanded_entities: Колбэк для получения списка развёрнутых entity.
            set_expanded_entities: Колбэк для восстановления развёрнутых entity.
            rescan_file_resources: Колбэк для пересканирования файловых ресурсов проекта.
        """
        self._editor_scene = scene
        self._game_scene: "Scene | None" = None  # Copy for game mode
        self._resource_manager = resource_manager
        self._scene_factory = scene_factory
        self._on_scene_changed = on_scene_changed
        self._get_editor_camera_data = get_editor_camera_data
        self._set_editor_camera_data = set_editor_camera_data
        self._get_selected_entity_name = get_selected_entity_name
        self._select_entity_by_name = select_entity_by_name
        self._get_displays_data = get_displays_data
        self._set_displays_data = set_displays_data
        self._get_expanded_entities = get_expanded_entities
        self._set_expanded_entities = set_expanded_entities
        self._rescan_file_resources = rescan_file_resources
        self._current_scene_path: str | None = None
        self._resources_initialized: bool = False

    def initialize_resources(self) -> None:
        """
        Initialize file resources once on startup.
        Should be called once after editor is ready.
        """
        if self._resources_initialized:
            return
        self._resources_initialized = True

        if self._rescan_file_resources is not None:
            self._rescan_file_resources()

    @property
    def scene(self) -> "Scene":
        """Текущая сцена. Возвращает game scene если в game mode, иначе editor scene."""
        if self._game_scene is not None:
            return self._game_scene
        return self._editor_scene

    @property
    def editor_scene(self) -> "Scene":
        """Editor scene (оригинал). Используется для undo/redo."""
        return self._editor_scene

    @property
    def is_game_mode(self) -> bool:
        """True если сейчас game mode."""
        return self._game_scene is not None

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

    def _replace_editor_scene(self, new_scene: "Scene") -> None:
        """
        Заменяет editor scene на новую и уведомляет подписчиков.
        """
        self._editor_scene = new_scene

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
        self._replace_editor_scene(new_scene)

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

        # Получаем развёрнутые entity
        expanded_entities = None
        if self._get_expanded_entities is not None:
            expanded_entities = self._get_expanded_entities()

        # Формируем данные редактора
        editor_data = {}
        if editor_camera_data is not None:
            editor_data["camera"] = editor_camera_data
        if selected_entity_name is not None:
            editor_data["selected_entity"] = selected_entity_name
        if displays_data is not None:
            editor_data["displays"] = displays_data
        if expanded_entities:
            editor_data["expanded_entities"] = expanded_entities

        scene_data = self._editor_scene.serialize()
        _validate_serializable(scene_data, "scene")

        resources_data = self._resource_manager.serialize()
        _validate_serializable(resources_data, "resources")

        data = {
            "version": "1.0",
            "scene": scene_data,
            "editor": editor_data,
            "resources": resources_data,
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
            "entities": sum(1 for e in self._editor_scene.entities if e.transform.parent is None and e.serializable),
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
        self._replace_editor_scene(new_scene)

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

        # Получаем развёрнутые entity
        expanded_entities = None
        if self._get_expanded_entities is not None:
            expanded_entities = self._get_expanded_entities()

        # Формируем данные редактора
        editor_data = {}
        if editor_camera_data is not None:
            editor_data["camera"] = editor_camera_data
        if selected_entity_name is not None:
            editor_data["selected_entity"] = selected_entity_name
        if displays_data is not None:
            editor_data["displays"] = displays_data
        if expanded_entities:
            editor_data["expanded_entities"] = expanded_entities

        data = {
            "resources": self._resource_manager.serialize(),
            "scene": self._editor_scene.serialize(),
            "editor": editor_data,
            "scene_path": self._current_scene_path,
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
        # Restore scene path (important for prefab edit mode exit)
        self._current_scene_path = state.get("scene_path")

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
        self._replace_editor_scene(new_scene)

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

        # Развёрнутые entity в дереве
        expanded_entities = editor_data.get("expanded_entities")
        if expanded_entities is not None and self._set_expanded_entities is not None:
            self._set_expanded_entities(expanded_entities)

        return {
            "loaded_entities": loaded_count,
            "materials": len(self._resource_manager.materials),
            "meshes": len(self._resource_manager._mesh_assets),
        }

    # --- Game Mode ---

    def enter_game_mode(self) -> "Scene":
        """
        Входит в game mode: создаёт копию editor scene для игры.

        Editor scene остаётся нетронутой. Все изменения в game mode
        происходят в копии и не влияют на оригинал.

        Returns:
            Game scene (копия) для переключения viewport'ов.
        """
        if self._game_scene is not None:
            return self._game_scene

        # Сериализуем editor scene
        scene_data = self._editor_scene.serialize()

        # Создаём копию (каждая сцена имеет свой entity pool)
        self._game_scene = self._create_new_scene()
        self._game_scene.load_from_data(scene_data, context=None, update_settings=True)

        return self._game_scene

    def exit_game_mode(self) -> "Scene":
        """
        Выходит из game mode: уничтожает копию, возвращает editor scene.

        Returns:
            Editor scene (оригинал) для переключения viewport'ов.
        """
        self._game_scene = None
        return self._editor_scene
