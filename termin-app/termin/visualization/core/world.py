"""World class for scene management."""

from __future__ import annotations

import json
from typing import List, Optional

from termin.visualization.core.scene import Scene
from termin.assets.resources import ResourceManager


class World:
    """
    Коллекция сцен.

    Чистый контейнер для сцен без логики рендеринга.
    Используется редактором и игрой для хранения игровых данных.
    """

    def __init__(self):
        self.scenes: List[Scene] = []

    def add_scene(self, scene: Scene) -> Scene:
        """Добавляет сцену в мир."""
        self.scenes.append(scene)
        return scene

    def remove_scene(self, scene: Scene) -> None:
        """Удаляет сцену из мира."""
        if scene in self.scenes:
            self.scenes.remove(scene)

    def update(self, dt: float) -> None:
        """Обновляет все сцены."""
        from tcbase.profiler import Profiler
        profiler = Profiler.instance()

        with profiler.section("World"):
            for scene in self.scenes:
                scene.update(dt)

    # --- Сериализация ---

    def serialize(self, resource_manager: Optional[ResourceManager] = None) -> dict:
        """
        Сериализует мир в словарь.

        Включает:
        - resources: Все ресурсы из ResourceManager
        - scenes: Все сцены
        """
        rm = resource_manager or ResourceManager.instance()
        return {
            "version": "1.0",
            "resources": rm.serialize(),
            "scenes": [scene.serialize() for scene in self.scenes],
        }

    def save_to_file(self, path: str, resource_manager: Optional[ResourceManager] = None) -> None:
        """
        Сохраняет мир в JSON файл.

        Параметры:
            path: Путь к файлу для сохранения
            resource_manager: ResourceManager для сериализации ресурсов
        """
        data = self.serialize(resource_manager)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def deserialize(cls, data: dict) -> "World":
        """
        Восстанавливает мир из сериализованных данных.
        """
        world = cls()

        # Восстанавливаем ресурсы в глобальный ResourceManager
        rm = ResourceManager.instance()
        resources_data = data.get("resources", {})
        if resources_data:
            restored_rm = ResourceManager.deserialize(resources_data)
            rm.materials.update(restored_rm.materials)
            rm._mesh_assets.update(restored_rm._mesh_assets)
            rm._texture_assets.update(restored_rm._texture_assets)

        # Восстанавливаем сцены
        for scene_data in data.get("scenes", []):
            scene = Scene.deserialize(scene_data)
            world.add_scene(scene)

        return world

    @classmethod
    def load_from_file(cls, path: str) -> "World":
        """
        Загружает мир из JSON файла.

        Параметры:
            path: Путь к файлу

        Возвращает:
            Новый World с восстановленным состоянием
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.deserialize(data)
