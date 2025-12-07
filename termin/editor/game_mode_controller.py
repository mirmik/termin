"""Game mode controller - handles play/stop and game loop."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np
from PyQt5.QtCore import QTimer, QElapsedTimer

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.resources import ResourceManager


class GameModeController:
    """
    Управляет игровым режимом редактора.

    Ответственности:
    - Сохранение/восстановление состояния сцены при входе/выходе
    - Игровой цикл (таймер + update)
    - Переключение режимов window
    """

    def __init__(
        self,
        scene: "Scene",
        resource_manager: "ResourceManager",
        on_mode_changed: Optional[Callable[[bool], None]] = None,
        on_request_update: Optional[Callable[[], None]] = None,
        on_tick: Optional[Callable[[float], None]] = None,
    ):
        self._scene = scene
        self._resource_manager = resource_manager
        self._on_mode_changed = on_mode_changed
        self._on_request_update = on_request_update
        self._on_tick = on_tick

        self._game_mode = False
        self._saved_scene_state: dict | None = None

        # Game loop timer (~60 FPS)
        self._game_timer = QTimer()
        self._game_timer.timeout.connect(self._tick)
        self._elapsed_timer = QElapsedTimer()

    @property
    def is_playing(self) -> bool:
        return self._game_mode

    def toggle(self) -> None:
        """Переключает режим игры."""
        if self._game_mode:
            self.stop()
        else:
            self.play()

    def play(self) -> None:
        """Входит в игровой режим, сохраняя состояние сцены."""
        if self._game_mode:
            return

        # Сохраняем состояние сцены
        self._saved_scene_state = self._serialize_state()

        # Переключаем режим
        self._game_mode = True

        # Запускаем игровой цикл
        self._elapsed_timer.start()
        self._game_timer.start(16)  # ~60 FPS

        if self._on_mode_changed:
            self._on_mode_changed(True)

    def stop(self) -> None:
        """Выходит из игрового режима, восстанавливая состояние сцены."""
        if not self._game_mode:
            return

        # Останавливаем игровой цикл
        self._game_timer.stop()

        if self._saved_scene_state is not None:
            self._restore_state(self._saved_scene_state)
            self._saved_scene_state = None

        # Переключаем режим
        self._game_mode = False

        if self._on_mode_changed:
            self._on_mode_changed(False)

    def _tick(self) -> None:
        """Вызывается таймером для обновления сцены."""
        if not self._game_mode:
            return

        # Вычисляем dt в секундах
        elapsed_ms = self._elapsed_timer.restart()
        dt = elapsed_ms / 1000.0

        # Обновляем сцену
        self._scene.update(dt)

        if self._on_tick is not None:
            self._on_tick(dt)

        # Перерисовываем viewport
        if self._on_request_update:
            self._on_request_update()

    def _serialize_state(self) -> dict:
        """Сериализует текущее состояние сцены и ресурсов."""
        def numpy_encoder(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        data = {
            "resources": self._resource_manager.serialize(),
            "scene": self._scene.serialize(),
        }
        # Сериализуем в JSON и обратно для глубокого копирования
        json_str = json.dumps(data, default=numpy_encoder)
        return json.loads(json_str)

    def _restore_state(self, state: dict) -> None:
        """Восстанавливает состояние сцены и ресурсов."""
        from termin.visualization.core.resources import ResourceManager

        # Удаляем все serializable entities (игровые объекты)
        for entity in list(self._scene.entities):
            if entity.serializable:
                self._scene.remove(entity)

        # Очищаем и восстанавливаем ресурсы
        self._resource_manager.materials.clear()
        self._resource_manager.meshes.clear()
        self._resource_manager.textures.clear()

        resources_data = state.get("resources", {})
        if resources_data:
            restored_rm = ResourceManager.deserialize(resources_data)
            self._resource_manager.materials.update(restored_rm.materials)
            self._resource_manager.meshes.update(restored_rm.meshes)
            self._resource_manager.textures.update(restored_rm.textures)

        # Восстанавливаем сцену
        scene_data = state.get("scene", {})
        if scene_data:
            self._scene.load_from_data(scene_data, context=None, update_settings=True)
