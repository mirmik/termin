from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set, Tuple, Tuple
from collections import deque


@dataclass
class FramePass:
    """
    Логический проход кадра.

    reads  – какие ресурсы этот проход читает (по именам).
    writes – какие ресурсы он пишет.
    enabled – включён ли проход; отключённые пассы игнорируются при построении графа.

    Inplace-семантика определяется через get_inplace_aliases():
        Если метод возвращает непустой список пар [(read, write), ...],
        то пасс считается inplace — он читает и пишет один и тот же
        физический ресурс под разными именами.

    Внутренние точки (internal debug points):
        Некоторые пассы могут объявлять «внутренние» точки наблюдения,
        связанные с их внутренними сущностями (например, отдельные меши,
        стадии рендера и т.п.). По умолчанию проход не имеет таких точек.
    """
    pass_name: str
    reads: Set[str] = field(default_factory=set)
    writes: Set[str] = field(default_factory=set)
    enabled: bool = True

    # Конфигурация внутренней точки дебага (символ и целевой ресурс).
    debug_internal_symbol: str | None = None
    debug_internal_output: str | None = None

    def __repr__(self) -> str:
        return f"FramePass({self.pass_name!r})"

    # ---- API inplace-алиасов ---------------------------------------------

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """
        Возвращает список пар алиасов для inplace-операций.
        
        Каждая пара (read_name, write_name) означает, что пасс
        читает ресурс read_name и пишет в write_name, но физически
        это один и тот же ресурс (буфер).
        
        Пример:
            ColorPass читает "empty" и пишет "color" inplace:
            return [("empty", "color")]
        
        Пустой список означает, что пасс не является inplace.
        """
        return []

    @property
    def inplace(self) -> bool:
        """
        Является ли пасс inplace.
        
        Вычисляется динамически на основе get_inplace_aliases().
        """
        return len(self.get_inplace_aliases()) > 0

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
            # --- валидация inplace-пассов через get_inplace_aliases ---
            inplace_aliases = p.get_inplace_aliases()
            
            if inplace_aliases:
                # Валидируем каждый алиас
                for src, dst in inplace_aliases:
                    if src not in p.reads:
                        raise FrameGraphError(
                            f"Inplace alias source {src!r} not in reads of pass {p.pass_name!r}"
                        )
                    if dst not in p.writes:
                        raise FrameGraphError(
                            f"Inplace alias target {dst!r} not in writes of pass {p.pass_name!r}"
                        )
                    if src in modified_inputs:
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

        # 2) обработка алиасов для inplace-пассов из get_inplace_aliases
        for p in self._passes:
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
