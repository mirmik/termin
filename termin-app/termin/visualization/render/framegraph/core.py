from __future__ import annotations

from typing import Dict, Iterable, List, Set
from collections import deque

from termin.render_framework.python_pass import (
    PythonFramePass,
    FramePass,
    RenderFramePass,
    deserialize_pass,
)


class FrameGraphError(Exception):
    """Базовая ошибка графа кадра."""


class FrameGraphMultiWriterError(FrameGraphError):
    """Один и тот же ресурс пишут несколько пассов."""


class FrameGraphCycleError(FrameGraphError):
    """В графе зависимостей обнаружен цикл."""


class FrameGraph:
    """
    DEPRECATED: Используйте tc_frame_graph из termin._native.render.

    Текущая версия RenderEngine использует C реализацию (tc_frame_graph).
    Этот класс оставлен для обратной совместимости с framegraph_debugger,
    pipeline_runner и nodegraph/compiler. Будет удалён после их миграции.

    ---

    Простейший frame graph: на вход – набор FramePass,
    на выход – топологически отсортированный список пассов.

    Флаг enabled обрабатывается каждым пассом самостоятельно в execute().
    Inplace-пассы могут просто вернуться без действий (ресурс пройдёт насквозь).
    Non-inplace пассы могут блитить вход в выход или использовать другую логику.
    """

    def __init__(self, passes: Iterable[FramePass]):
        self._passes: List[FramePass] = list(passes)
        # карта "ресурс -> каноническое имя" (на будущее — для дебага / инспекции)
        self._canonical_resources: Dict[str, str] = {}

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

        canonical: Dict[str, str] = {}           # локальная карта канонических имён

        n = len(self._passes)

        # 1) собираем writer-ов, reader-ов и валидируем inplace-пассы
        for idx, p in enumerate(self._passes):
            # Пропускаем отключённые пассы — они не участвуют в графе
            if not p.enabled:
                continue

            # --- валидация inplace-пассов через get_inplace_aliases ---
            inplace_aliases = p.get_inplace_aliases()
            
            if inplace_aliases:
                # Валидируем каждый алиас
                for src, dst in inplace_aliases:
                    if dst not in p.writes:
                        raise FrameGraphError(
                            f"Inplace alias target {dst!r} not in writes of pass {p.pass_name!r}"
                        )
                    canonical.setdefault(src, src)
                    canonical.setdefault(dst, dst)

            # --- writer-ы ---
            for res in p.writes:
                if res in writer_for:
                    other_idx = writer_for[res]
                    other = self._passes[other_idx]
                    raise FrameGraphMultiWriterError(
                        f"Resource {res!r} is written by multiple passes: "
                        f"{other.pass_name!r} and {p.pass_name!r}"
                    )
                writer_for[res] = idx

                # каноническое имя: первое появление ресурса как writer
                canonical.setdefault(res, res)

            # --- reader-ы ---
            for res in p.reads:
                lst = readers_for.setdefault(res, [])
                if idx not in lst:
                    lst.append(idx)
                # если ресурс нигде не писали, но читают — считаем внешним входом
                canonical.setdefault(res, res)

        # 2) обработка алиасов для inplace-пассов из get_inplace_aliases
        for p in self._passes:
            if not p.enabled:
                continue
            inplace_aliases = p.get_inplace_aliases()
            for src, dst in inplace_aliases:
                src_canon = canonical.get(src, src)
                # выходу назначаем каноническое имя входа
                canonical[dst] = src_canon

        # сохраним карту канонических имён
        self._canonical_resources = canonical

        # 3) adjacency и in_degree по индексам
        adjacency: Dict[int, List[int]] = {i: [] for i in range(n)}
        in_degree: Dict[int, int] = {i: 0 for i in range(n)}

        # Для каждого ресурса: writer -> все его reader-ы
        for res, w_idx in writer_for.items():
            for r_idx in readers_for.get(res, ()):
                if r_idx == w_idx:
                    continue  # на всякий случай, не создаём петли writer->writer
                if r_idx not in adjacency[w_idx]:
                    adjacency[w_idx].append(r_idx)
                    in_degree[r_idx] += 1

        # 4) Inplace пассы должны ждать всех других читателей своего input'а.
        #    Иначе inplace пасс "испортит" ресурс до того, как другие его прочитают.
        for idx, p in enumerate(self._passes):
            if not p.enabled:
                continue
            inplace_aliases = p.get_inplace_aliases()
            for src, _dst in inplace_aliases:
                # Все читатели src (кроме самого inplace пасса) должны выполниться до него
                for other_idx in readers_for.get(src, ()):
                    if other_idx == idx:
                        continue
                    # other_idx -> idx (other должен выполниться до inplace)
                    if idx not in adjacency[other_idx]:
                        adjacency[other_idx].append(idx)
                        in_degree[idx] += 1

        return adjacency, in_degree

    # ------------------------------------------------------------------ #
    # ТОПОЛОГИЧЕСКАЯ СОРТИРОВКА (Kahn с приоритетом обычных пассов)
    # ------------------------------------------------------------------ #

    def build_schedule(self) -> List[FramePass]:
        """
        Возвращает список пассов в порядке выполнения,
        учитывая зависимости read-after-write.

        Бросает:
            - FrameGraphMultiWriterError, если один ресурс пишут несколько пассов.
            - FrameGraphCycleError, если обнаружен цикл.
            - FrameGraphError, если нарушены правила inplace-пассов.
        """
        adjacency, in_degree = self._build_dependency_graph()
        n = len(self._passes)

        # Индексы только включённых пассов
        enabled_indices = {i for i, p in enumerate(self._passes) if p.enabled}
        is_inplace = [p.inplace for p in self._passes]

        # две очереди:
        #   обычные пассы — в ready_normal
        #   inplace-пассы — в ready_inplace
        ready_normal: deque[int] = deque()
        ready_inplace: deque[int] = deque()

        for i in range(n):
            if i not in enabled_indices:
                continue
            if in_degree[i] == 0:
                if is_inplace[i]:
                    ready_inplace.append(i)
                else:
                    ready_normal.append(i)

        schedule_indices: List[int] = []

        while ready_normal or ready_inplace:
            # приоритет обычных пассов
            if ready_normal:
                idx = ready_normal.popleft()
            else:
                idx = ready_inplace.popleft()

            schedule_indices.append(idx)

            for dep in adjacency[idx]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0 and dep in enabled_indices:
                    if is_inplace[dep]:
                        ready_inplace.append(dep)
                    else:
                        ready_normal.append(dep)

        if len(schedule_indices) != len(enabled_indices):
            # Остались вершины с in_degree > 0 → цикл
            problematic = [self._passes[i].pass_name for i, deg in in_degree.items() if deg > 0]
            raise FrameGraphCycleError(
                "Frame graph contains a dependency cycle involving passes: "
                + ", ".join(problematic)
            )

        # Конвертируем индексы обратно в реальные пассы
        return [self._passes[i] for i in schedule_indices]

    # опционально — геттер канонического имени ресурса (на будущее)
    def canonical_resource(self, name: str) -> str:
        return self._canonical_resources.get(name, name)

    def fbo_alias_groups(self) -> Dict[str, Set[str]]:
        """
        Группы синонимов ресурсов по каноническим именам.

        Возвращает dict:
            канон -> множество всех имён, которые к нему сводятся.
        """
        groups: Dict[str, Set[str]] = {}
        for res, canon in self._canonical_resources.items():
            groups.setdefault(canon, set()).add(res)

        return groups
