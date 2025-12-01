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
    inplace – модифицирующий ли это проход (in-place по смыслу).
    enabled – включён ли проход; отключённые пассы игнорируются при построении графа.

    Внутренние точки (internal debug points):
        Некоторые пассы могут объявлять «внутренние» точки наблюдения,
        связанные с их внутренними сущностями (например, отдельные меши,
        стадии рендера и т.п.). По умолчанию проход не имеет таких точек.
    """
    pass_name: str
    reads: Set[str] = field(default_factory=set)
    writes: Set[str] = field(default_factory=set)
    inplace: bool = False
    enabled: bool = True

    # Конфигурация внутренней точки дебага (символ и целевой ресурс).
    debug_internal_symbol: str | None = None
    debug_internal_output: str | None = None

    def __repr__(self) -> str:
        return f"FramePass({self.pass_name!r})"

    # ---- API внутренних точек ---------------------------------------------

    def get_internal_symbols(self) -> List[str]:
        """
        Возвращает список доступных внутренних символов/точек для этого пасса.

        Базовая реализация ничего не знает о внутренних точках и
        возвращает пустой список. Конкретные реализации пассов могут
        переопределять метод и формировать список динамически.
        """
        return []

    def set_debug_internal_point(
        self,
        symbol: str | None,
        output_res: str | None = None,
    ) -> None:
        """
        Устанавливает (или сбрасывает) активную внутреннюю точку дебага.

        symbol:
            Имя внутреннего символа, на который следует «подписаться».
            None — сброс настройки.
        output_res:
            Имя ресурса (FBO), в который пасс при необходимости
            должен выводить состояние для выбранного символа.

        При установке output_res он добавляется в writes пасса,
        при сбросе — удаляется. Это позволяет framegraph корректно
        учитывать debug-ресурс при построении графа зависимостей.
        """
        # Удаляем старый debug_internal_output из writes, если он был
        if self.debug_internal_output is not None:
            self.writes.discard(self.debug_internal_output)

        self.debug_internal_symbol = symbol
        self.debug_internal_output = output_res

        # Добавляем новый debug_internal_output в writes
        if output_res is not None:
            self.writes.add(output_res)

    def get_debug_internal_point(self) -> tuple[str | None, str | None]:
        """
        Текущая конфигурация внутренней точки дебага:
        (symbol, output_res).
        """
        return self.debug_internal_symbol, self.debug_internal_output


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

    Пассы с enabled=False игнорируются при построении графа и
    не попадают в итоговое расписание.
    """

    def __init__(self, passes: Iterable[FramePass]):
        self._all_passes: List[FramePass] = list(passes)
        # Фильтруем только включённые пассы для построения графа
        self._passes: List[FramePass] = [p for p in self._all_passes if p.enabled]
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

        # для in-place логики
        modified_inputs: Set[str] = set()        # какие имена уже были входом inplace-пасса
        canonical: Dict[str, str] = {}           # локальная карта канонических имён

        n = len(self._passes)

        # 1) собираем writer-ов, reader-ов и валидируем inplace-пассы
        for idx, p in enumerate(self._passes):
            # --- валидация inplace-пассов ---
            # Inplace-пасс должен иметь ровно 1 read.
            # В writes может быть 1 основной ресурс + опционально debug_internal_output.
            # debug_internal_output не нарушает семантику inplace,
            # так как это отдельный ресурс для дебага.
            if p.inplace:
                if len(p.reads) != 1:
                    raise FrameGraphError(
                        f"Inplace pass {p.pass_name!r} must have exactly 1 read, "
                        f"got reads={p.reads}"
                    )
                # Определяем количество «основных» writes (без debug_internal_output)
                base_writes_count = len(p.writes)
                if p.debug_internal_output is not None:
                    base_writes_count -= 1
                if base_writes_count != 1:
                    raise FrameGraphError(
                        f"Inplace pass {p.pass_name!r} must have exactly 1 base write "
                        f"(excluding debug_internal_output), got {base_writes_count}"
                    )
                (src,) = p.reads
                if src in modified_inputs:
                    # этот ресурс уже модифицировался другим inplace-пассом
                    raise FrameGraphError(
                        f"Resource {src!r} is already modified by another inplace pass"
                    )
                modified_inputs.add(src)

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

        # 2) обработка алиасов для inplace-пассов
        # (это чисто справочная штука, на граф зависимостей не влияет)
        for p in self._passes:
            if not p.inplace:
                continue
            (src,) = p.reads
            # Находим основной write (не debug_internal_output)
            base_writes = [w for w in p.writes if w != p.debug_internal_output]
            (dst,) = base_writes

            src_canon = canonical.get(src, src)
            # выходу назначаем каноническое имя входа:
            # даже если у dst уже было "своё", переопределяем —
            # мы сознательно объявляем их синонимами.
            canonical[dst] = src_canon

        # сохраним карту канонических имён (вдруг пригодится снаружи)
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

        is_inplace = [p.inplace for p in self._passes]

        # две очереди:
        #   обычные пассы — в ready_normal
        #   inplace-пассы — в ready_inplace
        ready_normal: deque[int] = deque()
        ready_inplace: deque[int] = deque()

        for i in range(n):
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
                if in_degree[dep] == 0:
                    if is_inplace[dep]:
                        ready_inplace.append(dep)
                    else:
                        ready_normal.append(dep)

        if len(schedule_indices) != n:
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
