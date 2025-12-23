"""
Иерархический профайлер движка.

Использование:
    from termin.core.profiler import Profiler

    profiler = Profiler.instance()
    profiler.enabled = True

    # В игровом цикле:
    profiler.begin_frame()

    with profiler.section("Physics"):
        simulate()

    with profiler.section("Render"):
        with profiler.section("Shadow"):
            ...
        with profiler.section("Color"):
            ...

    profiler.end_frame()

    # Получить результаты:
    avg = profiler.average(60)
    for name, ms in avg.items():
        print(f"{name}: {ms:.2f}ms")

Когда профайлер выключен (enabled=False), overhead минимален —
одна проверка bool в начале каждого метода.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Iterator, NamedTuple


class SectionStats(NamedTuple):
    """Статистика секции профилирования."""
    cpu_ms: float
    call_count: int


@dataclass
class SectionTiming:
    """Тайминг одной секции профилирования."""

    name: str
    cpu_ms: float = 0.0
    call_count: int = 0
    children: Dict[str, "SectionTiming"] = field(default_factory=dict)


@dataclass
class FrameProfile:
    """Профиль одного кадра."""

    frame_number: int
    total_ms: float = 0.0
    sections: Dict[str, SectionTiming] = field(default_factory=dict)


class Profiler:
    """
    Иерархический профайлер с минимальным overhead.

    Singleton — используйте Profiler.instance() для получения экземпляра.
    """

    _instance: "Profiler | None" = None

    @classmethod
    def instance(cls) -> "Profiler":
        """Возвращает singleton экземпляр профайлера."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, history_size: int = 120):
        """
        Инициализирует профайлер.

        Args:
            history_size: Количество кадров в истории (по умолчанию 120 = 2 секунды при 60 FPS).
        """
        self._enabled = False
        self._profile_components = False  # Детальное профилирование компонентов
        self._history: List[FrameProfile] = []
        self._history_size = history_size
        self._frame_count = 0
        self._section_stack: List[SectionTiming] = []
        self._current_frame: FrameProfile | None = None
        self._frame_start: float = 0.0

    @property
    def enabled(self) -> bool:
        """Включён ли профайлер."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Включает/выключает профайлер."""
        self._enabled = value
        if not value:
            # Сбрасываем состояние при выключении
            self._current_frame = None
            self._section_stack.clear()

    @property
    def profile_components(self) -> bool:
        """Детальное профилирование компонентов (Update, FixedUpdate)."""
        return self._profile_components

    @profile_components.setter
    def profile_components(self, value: bool) -> None:
        """Включает/выключает детальное профилирование компонентов."""
        self._profile_components = value

    @property
    def history(self) -> List[FrameProfile]:
        """История профилей кадров."""
        return self._history

    def clear_history(self) -> None:
        """Очищает историю профилей."""
        self._history.clear()

    def begin_frame(self) -> None:
        """
        Начинает профилирование нового кадра.

        Вызывайте в начале игрового цикла.
        Идемпотентен — если frame уже начат, ничего не делает.
        """
        if not self._enabled:
            return

        # Идемпотентность: если frame уже начат, не начинаем новый
        if self._current_frame is not None:
            return

        self._current_frame = FrameProfile(frame_number=self._frame_count)
        self._frame_count += 1
        self._section_stack.clear()
        self._frame_start = time.perf_counter()

    def end_frame(self) -> None:
        """
        Завершает профилирование кадра.

        Вызывайте в конце игрового цикла.
        """
        if not self._enabled or self._current_frame is None:
            return

        self._current_frame.total_ms = (time.perf_counter() - self._frame_start) * 1000.0

        self._history.append(self._current_frame)
        if len(self._history) > self._history_size:
            self._history.pop(0)

        self._current_frame = None

    @contextmanager
    def section(self, name: str) -> Iterator[None]:
        """
        Context manager для измерения секции кода.

        Секции могут быть вложенными:

            with profiler.section("Render"):
                with profiler.section("Shadow"):
                    render_shadows()
                with profiler.section("Color"):
                    render_color()

        Args:
            name: Имя секции для отображения в профайлере.
        """
        if not self._enabled or self._current_frame is None:
            yield
            return

        # Находим словарь для текущего уровня вложенности
        if self._section_stack:
            sections = self._section_stack[-1].children
        else:
            sections = self._current_frame.sections

        # Получаем или создаём тайминг для секции
        if name not in sections:
            sections[name] = SectionTiming(name=name)
        timing = sections[name]

        self._section_stack.append(timing)
        start = time.perf_counter()

        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0
            timing.cpu_ms += elapsed
            timing.call_count += 1
            self._section_stack.pop()

    def last_frame(self) -> FrameProfile | None:
        """Возвращает последний завершённый профиль кадра."""
        return self._history[-1] if self._history else None

    def average(self, frames: int = 60) -> Dict[str, float]:
        """
        Возвращает усреднённые времена по секциям.

        Args:
            frames: Количество последних кадров для усреднения.

        Returns:
            Словарь "путь/секции" -> среднее время в мс.
            Например: {"Render": 8.5, "Render/Shadow": 2.1, "Render/Color": 5.2}
        """
        detailed = self.detailed_average(frames)
        return {name: stats.cpu_ms for name, stats in detailed.items()}

    def detailed_average(self, frames: int = 60) -> Dict[str, SectionStats]:
        """
        Возвращает детальную статистику по секциям.

        Args:
            frames: Количество последних кадров для усреднения.

        Returns:
            Словарь "путь/секции" -> SectionStats(cpu_ms, call_count).
            call_count — среднее количество вызовов за кадр.
        """
        if not self._history:
            return {}

        recent = self._history[-frames:]
        totals: Dict[str, List[tuple]] = {}  # path -> [(cpu_ms, call_count), ...]

        def collect(sections: Dict[str, SectionTiming], prefix: str = "") -> None:
            for name, timing in sections.items():
                full_path = f"{prefix}{name}" if prefix else name
                totals.setdefault(full_path, []).append((timing.cpu_ms, timing.call_count))
                collect(timing.children, f"{full_path}/")

        for frame in recent:
            collect(frame.sections)

        result = {}
        for name, samples in totals.items():
            avg_ms = sum(s[0] for s in samples) / len(samples)
            avg_count = sum(s[1] for s in samples) / len(samples)
            result[name] = SectionStats(cpu_ms=avg_ms, call_count=round(avg_count))
        return result

    def print_report(self, frames: int = 60) -> None:
        """
        Печатает отчёт профилирования в консоль.

        Args:
            frames: Количество кадров для усреднения.
        """
        detailed = self.detailed_average(frames)
        if not detailed:
            print("No profiling data")
            return

        # Сортируем: сначала по глубине, потом по времени внутри уровня
        sorted_sections = sorted(detailed.items(), key=lambda x: (x[0].count("/"), -x[1].cpu_ms))

        # Считаем общее время (только root секции)
        total = sum(stats.cpu_ms for name, stats in sorted_sections if "/" not in name)

        print(f"\n=== Profiler Report (avg {min(frames, len(self._history))} frames) ===")
        if total > 0:
            print(f"Total: {total:.2f}ms ({1000/total:.0f} FPS)")
        print()

        for name, stats in sorted_sections:
            indent = "  " * name.count("/")
            base_name = name.split("/")[-1]
            pct = (stats.cpu_ms / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 5)
            count_str = f"x{stats.call_count}" if stats.call_count > 1 else ""
            print(f"{indent}{base_name:20} {stats.cpu_ms:6.2f}ms {pct:5.1f}% {count_str:>5} {bar}")

        print()
