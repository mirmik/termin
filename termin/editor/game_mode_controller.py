"""Game mode controller - handles play/stop and game loop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from PyQt6.QtCore import QTimer, QElapsedTimer

if TYPE_CHECKING:
    from termin.editor.world_persistence import WorldPersistence


class GameModeController:
    """
    Управляет игровым режимом редактора.

    Ответственности:
    - Сохранение/восстановление состояния сцены при входе/выходе
    - Игровой цикл (таймер + update)
    - Переключение режимов window

    ВАЖНО: Использует WorldPersistence для доступа к сцене.
    Не хранит собственную ссылку на scene.
    """

    def __init__(
        self,
        world_persistence: "WorldPersistence",
        on_mode_changed: Optional[Callable[[bool], None]] = None,
        on_request_update: Optional[Callable[[], None]] = None,
        on_tick: Optional[Callable[[float], None]] = None,
    ):
        self._world_persistence = world_persistence
        self._on_mode_changed = on_mode_changed
        self._on_request_update = on_request_update
        self._on_tick = on_tick

        self._game_mode = False
        self._saved_state: dict | None = None

        # Game loop timer (~60 FPS)
        self._game_timer = QTimer()
        self._game_timer.timeout.connect(self._tick)
        self._elapsed_timer = QElapsedTimer()

    @property
    def scene(self):
        """Текущая сцена (всегда актуальная)."""
        return self._world_persistence.scene

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

        # Сохраняем состояние через WorldPersistence
        self._saved_state = self._world_persistence.save_state()

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

        # Восстанавливаем состояние через WorldPersistence
        # Это создаст НОВУЮ сцену и вызовет on_scene_changed
        if self._saved_state is not None:
            self._world_persistence.restore_state(self._saved_state)
            self._saved_state = None

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

        # Обновляем сцену (получаем актуальную через property)
        self.scene.update(dt)

        if self._on_tick is not None:
            self._on_tick(dt)

        # Перерисовываем viewport
        if self._on_request_update:
            self._on_request_update()
