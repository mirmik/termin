"""World persistence - save/load/reset functionality."""

from __future__ import annotations

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
    Управляет сохранением/загрузкой/сбросом мира.

    Ответственности:
    - Сериализация/десериализация сцены и ресурсов
    - Атомарная запись файлов
    - Очистка и пересоздание мира
    """

    def __init__(
        self,
        scene: "Scene",
        resource_manager: "ResourceManager",
        on_before_reset: Optional[Callable[[], None]] = None,
        on_after_reset: Optional[Callable[[], None]] = None,
        on_after_load: Optional[Callable[[], None]] = None,
    ):
        self._scene = scene
        self._resource_manager = resource_manager
        self._on_before_reset = on_before_reset
        self._on_after_reset = on_after_reset
        self._on_after_load = on_after_load

    def save(self, file_path: str) -> dict:
        """
        Сохраняет мир в JSON файл.

        Returns:
            Статистика: entities, materials, meshes count
        """
        data = {
            "version": "1.0",
            "resources": self._resource_manager.serialize(),
            "scenes": [self._scene.serialize()],
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

        return {
            "entities": sum(1 for e in self._scene.entities if e.transform.parent is None and e.serializable),
            "materials": len(self._resource_manager.materials),
            "meshes": len(self._resource_manager.meshes),
        }

    def load(self, file_path: str, clear_scene: bool = True) -> dict:
        """
        Загружает мир из JSON файла.

        Args:
            file_path: Путь к файлу
            clear_scene: Очистить сцену перед загрузкой

        Returns:
            Статистика: loaded_entities, materials, meshes count
        """
        with open(file_path, "r", encoding="utf-8") as f:
            json_str = f.read()
        data = json.loads(json_str)

        if clear_scene:
            self._clear_serializable_entities()

        # Восстанавливаем ресурсы
        self._load_resources(data.get("resources", {}))

        # Загружаем первую сцену
        loaded_count = 0
        scenes = data.get("scenes", [])
        if scenes:
            loaded_count = self._scene.load_from_data(
                scenes[0],
                context=None,
                update_settings=clear_scene
            )

        if self._on_after_load:
            self._on_after_load()

        return {
            "loaded_entities": loaded_count,
            "materials": len(self._resource_manager.materials),
            "meshes": len(self._resource_manager.meshes),
        }

    def reset(self) -> None:
        """
        Полная очистка мира.
        Удаляет ВСЕ entities (включая редакторские) и ресурсы.
        """
        if self._on_before_reset:
            self._on_before_reset()

        # Удаляем ВСЕ entities
        for entity in list(self._scene.entities):
            self._scene.remove(entity)

        # Очищаем ресурсы
        self._resource_manager.materials.clear()
        self._resource_manager.meshes.clear()
        self._resource_manager.textures.clear()

        if self._on_after_reset:
            self._on_after_reset()

    def _clear_serializable_entities(self) -> None:
        """Удаляет только serializable entities."""
        for entity in list(self._scene.entities):
            if entity.serializable:
                self._scene.remove(entity)

    def _load_resources(self, resources_data: dict) -> None:
        """Загружает ресурсы из сериализованных данных."""
        from termin.visualization.core.resources import ResourceManager

        if not resources_data:
            return

        restored_rm = ResourceManager.deserialize(resources_data)
        self._resource_manager.materials.update(restored_rm.materials)
        self._resource_manager.meshes.update(restored_rm.meshes)
        self._resource_manager.textures.update(restored_rm.textures)
