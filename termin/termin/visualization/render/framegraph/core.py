from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Set, Tuple, TYPE_CHECKING
from collections import deque

from termin._native.render import (
    TcPass,
    TcPassRef,
    tc_pass_registry_register_python,
    tc_pass_registry_has,
)

if TYPE_CHECKING:
    from tgfx import FramebufferHandle


class FramePass:
    """
    Логический проход кадра.

    reads  – какие ресурсы этот проход читает (по именам). Вычисляется динамически.
    writes – какие ресурсы он пишет. Вычисляется динамически.
    enabled – включён ли проход; отключённые пассы полностью игнорируются
              при построении графа (не участвуют в зависимостях, не вызывают конфликтов).
    passthrough – если True, пасс остаётся в графе, но просто копирует input → output
                  без реальной обработки (используется для временного отключения эффектов).

    Inplace-семантика определяется через get_inplace_aliases():
        Если метод возвращает непустой список пар [(read, write), ...],
        то пасс считается inplace — он читает и пишет один и тот же
        физический ресурс под разными именами.

    Внутренние точки (internal debug points):
        Некоторые пассы могут объявлять «внутренние» точки наблюдения,
        связанные с их внутренними сущностями (например, отдельные меши,
        стадии рендера и т.п.). По умолчанию проход не имеет таких точек.
    """

    # Поля для редактирования в инспекторе (подклассы переопределяют)
    inspect_fields: dict = {}

    # Категория пасса для организации в меню редактора пайплайна
    category: str = "Other"

    # Входы и выходы для node editor: список кортежей (name, socket_type)
    # socket_type: "fbo", "texture", "shadow"
    node_inputs: list = []
    node_outputs: list = []

    # Inplace пары: список кортежей (input_name, output_name)
    # Для этих пар input и output используют один и тот же FBO
    node_inplace_pairs: list = []

    def __init__(self, pass_name: str = "FramePass", viewport_name: str | None = None):
        self.pass_name = pass_name
        self.enabled = True
        self.passthrough = False

        # Viewport name for resolution and camera context
        # None = offscreen pass (uses explicit resolution from ResourceSpec)
        self.viewport_name = viewport_name

        # Конфигурация внутренней точки дебага.
        self.debug_internal_symbol: str | None = None
        # SDL окно дебаггера для блита промежуточного состояния.
        self._debugger_window: Any = None
        # Callback для передачи depth buffer дебаггеру: (numpy_array) -> None
        self._depth_capture_callback: "Callable[[Any], None] | None" = None
        # Callback для сообщения об ошибке чтения depth: (str) -> None
        self._depth_error_callback: "Callable[[str], None] | None" = None

        # C handle for tc_pass system (TcPass owns tc_pass, frees it in destructor)
        self._tc_pass_handle: "TcPass" = TcPass(self, self.__class__.__name__)
        self._tc_pass_handle.pass_name = pass_name

    @property
    def _tc_pass(self) -> "TcPassRef":
        """Return TcPassRef for C interop."""
        return self._tc_pass_handle.ref()

    # ---- reads/writes как вычисляемые свойства --------------------------------

    @property
    def reads(self) -> Set[str]:
        """Ресурсы которые пасс читает. Вычисляется динамически."""
        return self.compute_reads()

    @property
    def writes(self) -> Set[str]:
        """Ресурсы которые пасс пишет. Вычисляется динамически."""
        return self.compute_writes()

    def compute_reads(self) -> Set[str]:
        """Вычисляет множество читаемых ресурсов. Подклассы переопределяют."""
        return set()

    def compute_writes(self) -> Set[str]:
        """Вычисляет множество записываемых ресурсов. Подклассы переопределяют."""
        return set()

    def __init_subclass__(cls, **kwargs):
        """Register subclass in InspectRegistry and pass type registry."""
        super().__init_subclass__(**kwargs)

        # Don't register base classes
        if cls.__name__ in ("FramePass", "RenderFramePass"):
            return

        # Register pass type in C registry with class for factory
        if not tc_pass_registry_has(cls.__name__):
            tc_pass_registry_register_python(cls.__name__, cls)

        try:
            from termin._native.inspect import InspectRegistry
            registry = InspectRegistry.instance()

            # Register only own fields (not inherited)
            own_fields = cls.__dict__.get('inspect_fields', {})
            if own_fields:
                registry.register_python_fields(cls.__name__, own_fields)

            # Find parent type and register inheritance
            parent_name = None
            for klass in cls.__mro__[1:]:
                if klass.__name__ in ("FramePass", "RenderFramePass"):
                    parent_name = klass.__name__
                    break
                if 'inspect_fields' in klass.__dict__:
                    parent_name = klass.__name__
                    break

            if parent_name:
                registry.set_type_parent(cls.__name__, parent_name)
        except ImportError:
            pass

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

    def set_debug_internal_point(self, symbol: str | None) -> None:
        """
        Устанавливает (или сбрасывает) активную внутреннюю точку дебага.

        symbol:
            Имя внутреннего символа, на который следует «подписаться».
            None — сброс настройки.

        Когда установлен символ и _capture_fbo, пасс при отрисовке
        этого символа будет блитить текущее состояние в capture FBO.
        """
        self.debug_internal_symbol = symbol

    def get_debug_internal_point(self) -> str | None:
        """Возвращает текущий символ внутренней точки дебага."""
        return self.debug_internal_symbol

    def set_debugger_window(
        self,
        window,
        depth_callback: Callable[[Any], None] | None = None,
        depth_error_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Устанавливает SDL окно дебаггера для блита промежуточного состояния.

        Args:
            window: SDL окно дебаггера. None — отключить.
            depth_callback: Callback для передачи depth buffer (numpy array).
            depth_error_callback: Callback для сообщения об ошибке чтения depth.
        """
        self._debugger_window = window
        self._depth_capture_callback = depth_callback
        self._depth_error_callback = depth_error_callback

    def get_debugger_window(self):
        """Возвращает SDL окно дебаггера или None."""
        return self._debugger_window

    # ---- Сериализация ---------------------------------------------

    def serialize_data(self) -> dict:
        """
        Сериализует данные пасса через InspectRegistry.

        Использует тот же механизм, что и PythonComponent - kind handlers
        применяются для enum, handles и т.д.
        """
        from termin._native.inspect import InspectRegistry
        return InspectRegistry.instance().serialize_all(self)

    def deserialize_data(self, data: dict) -> None:
        """
        Десериализует данные пасса через InspectRegistry.

        Использует тот же механизм, что и PythonComponent - kind handlers
        применяются для enum, handles и т.д.
        """
        if not data:
            return
        from termin._native.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_all(self, data)

    def serialize(self) -> dict:
        """
        Сериализует FramePass в словарь.

        Использует InspectRegistry для сериализации полей.
        """
        result = {
            "type": self.__class__.__name__,
            "pass_name": self.pass_name,
            "enabled": self.enabled,
            "passthrough": self.passthrough,
            "data": self.serialize_data(),
        }
        if self.viewport_name is not None:
            result["viewport_name"] = self.viewport_name
        return result

    @classmethod
    def deserialize(cls, data: dict, resource_manager=None) -> "FramePass":
        """
        Десериализует FramePass из словаря.

        Использует ResourceManager для поиска зарегистрированного
        класса по имени типа.

        Args:
            data: Словарь с сериализованными данными
            resource_manager: ResourceManager для поиска класса

        Returns:
            Экземпляр FramePass

        Raises:
            ValueError: если тип не найден или данные некорректны
        """
        pass_type = data.get("type")
        if pass_type is None:
            raise ValueError("Missing 'type' in FramePass data")

        # Получаем класс из ResourceManager
        if resource_manager is None:
            from termin.visualization.core.resources import ResourceManager
            resource_manager = ResourceManager.instance()

        pass_cls = resource_manager.get_frame_pass(pass_type)
        if pass_cls is None:
            raise ValueError(f"Unknown FramePass type: {pass_type}")

        # Создаём экземпляр и десериализуем данные
        instance = pass_cls._deserialize_instance(data, resource_manager)

        # Восстанавливаем базовые поля
        instance.enabled = data.get("enabled", True)
        instance.passthrough = data.get("passthrough", False)
        instance.viewport_name = data.get("viewport_name", "")

        # Десериализуем данные через TcPassRef (unified for C++ and Python passes)
        instance._tc_pass.deserialize_data(data.get("data", {}))

        return instance

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "FramePass":
        """
        Создаёт экземпляр из сериализованных данных.

        Подклассы должны переопределить этот метод для правильной
        инициализации с их специфическими параметрами.

        Базовая реализация создаёт экземпляр с pass_name.
        """
        return cls(pass_name=data.get("pass_name", "unnamed"))


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

        # для in-place логики
        modified_inputs: Set[str] = set()        # какие имена уже были входом inplace-пасса
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
