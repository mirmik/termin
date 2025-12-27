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

Использует C ядро (TcProfiler) для минимального overhead.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Iterator, NamedTuple

from termin._native.profiler import TcProfiler


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
    Делегирует к C ядру TcProfiler для быстрого замера времени.
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
        self._tc = TcProfiler.instance()
        self._history_size = history_size

    @property
    def _current_frame(self):
        """Текущий кадр (None если не в процессе профилирования)."""
        return self._tc.current_frame

    @property
    def enabled(self) -> bool:
        """Включён ли профайлер."""
        return self._tc.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Включает/выключает профайлер."""
        self._tc.enabled = value

    @property
    def profile_components(self) -> bool:
        """Детальное профилирование компонентов (Update, FixedUpdate)."""
        return self._tc.profile_components

    @profile_components.setter
    def profile_components(self, value: bool) -> None:
        """Включает/выключает детальное профилирование компонентов."""
        self._tc.profile_components = value

    @property
    def history(self) -> List[FrameProfile]:
        """История профилей кадров (конвертируется из C данных)."""
        return self._convert_history()

    def clear_history(self) -> None:
        """Очищает историю профилей."""
        self._tc.clear_history()

    def begin_frame(self) -> None:
        """
        Начинает профилирование нового кадра.

        Вызывайте в начале игрового цикла.
        Идемпотентен — если frame уже начат, ничего не делает.
        """
        self._tc.begin_frame()

    def end_frame(self) -> None:
        """
        Завершает профилирование кадра.

        Вызывайте в конце игрового цикла.
        """
        self._tc.end_frame()

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
        if not self._tc.enabled:
            yield
            return

        self._tc.begin_section(name)
        try:
            yield
        finally:
            self._tc.end_section()

    def _convert_history(self) -> List[FrameProfile]:
        """Конвертирует C историю в Python FrameProfile объекты."""
        result = []
        for c_frame in self._tc.history:
            frame = FrameProfile(
                frame_number=c_frame.frame_number,
                total_ms=c_frame.total_ms,
            )
            # Build hierarchical sections from flat C array
            self._build_sections(c_frame.sections, frame.sections)
            result.append(frame)
        return result

    def _build_sections(self, c_sections: list, out: Dict[str, SectionTiming], parent_idx: int = -1) -> None:
        """Рекурсивно строит иерархию секций из плоского C массива."""
        for i, s in enumerate(c_sections):
            if s.parent_index == parent_idx:
                timing = SectionTiming(
                    name=s.name,
                    cpu_ms=s.cpu_ms,
                    call_count=s.call_count,
                )
                out[s.name] = timing
                # Recursively add children
                self._build_sections(c_sections, timing.children, i)

    def last_frame(self) -> FrameProfile | None:
        """Возвращает последний завершённый профиль кадра."""
        history = self._convert_history()
        return history[-1] if history else None

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
        history = self._convert_history()
        if not history:
            return {}

        recent = history[-frames:]
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

        history = self._convert_history()

        # Сортируем: сначала по глубине, потом по времени внутри уровня
        sorted_sections = sorted(detailed.items(), key=lambda x: (x[0].count("/"), -x[1].cpu_ms))

        # Считаем общее время (только root секции)
        total = sum(stats.cpu_ms for name, stats in sorted_sections if "/" not in name)

        print(f"\n=== Profiler Report (avg {min(frames, len(history))} frames) ===")
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
