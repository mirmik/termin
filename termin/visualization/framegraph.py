# termin/visualization/framegraph.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set
from collections import deque


@dataclass
class FramePass:
    """
    Логический проход кадра.

    reads  – какие ресурсы этот проход читает (по именам).
    writes – какие ресурсы он пишет.
    """
    name: str
    reads: Set[str] = field(default_factory=set)
    writes: Set[str] = field(default_factory=set)

    def __repr__(self) -> str:
        return f"FramePass({self.name!r})"


class FrameGraphError(Exception):
    """Базовая ошибка графа кадра."""


class FrameGraphMultiWriterError(FrameGraphError):
    """Один и тот же ресурс пишут несколько пассов."""


class FrameGraphCycleError(FrameGraphError):
    """В графе зависимостей обнаружен цикл."""


class FrameGraph:
    """
    Простейший frame graph: на вход – набор FramePass,
    на выход – топологически отсортированный список пассов.
    """

    def __init__(self, passes: Iterable[FramePass]):
        self._passes: List[FramePass] = list(passes)

    # ------------------------------------------------------------------ #
    # ВНУТРЕННЕЕ ПРЕДСТАВЛЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ
    # ------------------------------------------------------------------ #
    # Всё строим на ИНДЕКСАХ пассов (0..N-1), а не на самих объектах,
    # чтобы вообще не зависеть от их hash/eq.
    # ------------------------------------------------------------------ #

    def _build_dependency_graph(self):
        """
        Строит граф зависимостей между пассами.

        Возвращает:
            adjacency: dict[int, list[int]]
                для каждого индекса пасса – список индексов пассов,
                которые зависят от него (есть ребро writer -> reader).
            in_degree: dict[int, int]
                количество входящих рёбер для каждого пасса.
        """
        writer_for: Dict[str, int] = {}          # ресурс -> индекс писателя
        readers_for: Dict[str, List[int]] = {}   # ресурс -> список индексов читателей

        n = len(self._passes)

        # 1) собираем writer-ов и reader-ов
        for idx, p in enumerate(self._passes):
            # кто пишет ресурс
            for res in p.writes:
                if res in writer_for:
                    other_idx = writer_for[res]
                    other = self._passes[other_idx]
                    raise FrameGraphMultiWriterError(
                        f"Resource {res!r} is written by multiple passes: "
                        f"{other.name!r} and {p.name!r}"
                    )
                writer_for[res] = idx

            # кто читает ресурс
            for res in p.reads:
                lst = readers_for.setdefault(res, [])
                if idx not in lst:
                    lst.append(idx)

        # 2) adjacency и in_degree по индексам
        adjacency: Dict[int, List[int]] = {i: [] for i in range(n)}
        in_degree: Dict[int, int] = {i: 0 for i in range(n)}

        # Для каждого ресурса: writer -> все его reader-ы
        for res, w_idx in writer_for.items():
            for r_idx in readers_for.get(res, ()):
                if r_idx == w_idx:
                    continue  # на всякий случай, не создаём петли
                if r_idx not in adjacency[w_idx]:
                    adjacency[w_idx].append(r_idx)
                    in_degree[r_idx] += 1

        return adjacency, in_degree

    # ------------------------------------------------------------------ #
    # ТОПОЛОГИЧЕСКАЯ СОРТИРОВКА (Kahn)
    # ------------------------------------------------------------------ #

    def build_schedule(self) -> List[FramePass]:
        """
        Возвращает список пассов в порядке выполнения,
        учитывая зависимости read-after-write.

        Бросает:
            - FrameGraphMultiWriterError, если один ресурс пишут несколько пассов.
            - FrameGraphCycleError, если обнаружен цикл.
        """
        adjacency, in_degree = self._build_dependency_graph()

        # Все пассы с in_degree == 0 можно запускать сразу.
        # Используем очередь, чтобы по возможности сохранить
        # исходный порядок там, где нет явных зависимостей.
        ready = deque(i for i, deg in in_degree.items() if deg == 0)
        schedule_indices: List[int] = []

        while ready:
            idx = ready.popleft()
            schedule_indices.append(idx)

            for dep in adjacency[idx]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    ready.append(dep)

        if len(schedule_indices) != len(self._passes):
            # Остались вершины с in_degree > 0 → цикл
            problematic = [self._passes[i].name for i, deg in in_degree.items() if deg > 0]
            raise FrameGraphCycleError(
                "Frame graph contains a dependency cycle involving passes: "
                + ", ".join(problematic)
            )

        # Конвертируем индексы обратно в реальные пассы
        return [self._passes[i] for i in schedule_indices]
