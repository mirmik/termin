"""Game mode controller - handles play/stop and game loop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from PyQt6.QtCore import QTimer, QElapsedTimer

from termin.core.profiler import Profiler

if TYPE_CHECKING:
    from termin.editor.scene_manager import SceneManager
    from termin.visualization.core.scene import Scene


class GameModeController:
    """
    Управляет игровым режимом редактора.

    Ответственности:
    - Создание копии сцены для game mode
    - Игровой цикл (таймер + update)
    - Переключение режимов window

    При входе в game mode создаётся копия editor scene.
    Игра работает на копии, оригинал не изменяется.
    Undo/redo стек остаётся валидным.

    ВАЖНО: Использует SceneManager для доступа к сценам.
    """

    def __init__(
        self,
        scene_manager: "SceneManager",
        on_mode_changed: Optional[Callable[[bool, "Scene", dict], None]] = None,
        on_request_update: Optional[Callable[[], None]] = None,
        on_tick: Optional[Callable[[float], None]] = None,
        get_viewport_camera_names: Optional[Callable[[], dict]] = None,
    ):
        self._scene_manager = scene_manager
        self._on_mode_changed = on_mode_changed
        self._on_request_update = on_request_update
        self._on_tick = on_tick
        self._get_viewport_camera_names = get_viewport_camera_names

        self._game_mode = False

        # Game loop timer (~60 FPS)
        self._game_timer = QTimer()
        self._game_timer.timeout.connect(self._tick)
        self._elapsed_timer = QElapsedTimer()

    @property
    def scene(self):
        """Текущая сцена (game scene в game mode, иначе editor scene)."""
        if self._game_mode:
            return self._scene_manager.get_scene("game")
        return self._scene_manager.get_scene("editor")

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
        """Входит в игровой режим, создавая копию сцены."""
        if self._game_mode:
            return

        # Сохраняем имена камер ДО смены сцены
        camera_names = {}
        if self._get_viewport_camera_names is not None:
            camera_names = self._get_viewport_camera_names()

        # Создаём копию сцены для game mode
        game_scene = self._scene_manager.enter_game_mode()

        # Переключаем режим
        self._game_mode = True

        # Запускаем игровой цикл
        self._elapsed_timer.start()
        self._game_timer.start(16)  # ~60 FPS

        if self._on_mode_changed:
            self._on_mode_changed(True, game_scene, camera_names)

    def stop(self) -> None:
        """Выходит из игрового режима, возвращаясь к оригинальной сцене."""
        if not self._game_mode:
            return

        # Останавливаем игровой цикл
        self._game_timer.stop()

        # Сохраняем имена камер ДО уничтожения game scene
        camera_names = {}
        if self._get_viewport_camera_names is not None:
            camera_names = self._get_viewport_camera_names()

        # Выходим из game mode - копия уничтожается
        editor_scene = self._scene_manager.exit_game_mode()

        # Переключаем режим
        self._game_mode = False

        if self._on_mode_changed:
            self._on_mode_changed(False, editor_scene, camera_names)

    def _tick(self) -> None:
        """Вызывается таймером для обновления сцены."""
        if not self._game_mode:
            return

        profiler = Profiler.instance()
        profiler.begin_frame()

        # Вычисляем dt в секундах
        elapsed_ms = self._elapsed_timer.restart()
        dt = elapsed_ms / 1000.0

        # Обновляем game сцену
        game_scene = self._scene_manager.get_scene("game")
        if game_scene is not None:
            with profiler.section("Components"):
                game_scene.update(dt)

        if self._on_tick is not None:
            self._on_tick(dt)

        # Перерисовываем viewport (рендер добавит свои секции)
        if self._on_request_update:
            self._on_request_update()

        # Завершаем frame после рендера
        profiler.end_frame()
