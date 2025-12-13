from __future__ import annotations

from typing import List, Tuple

from termin.visualization.render.framegraph.core import FrameGraph, FramePass


class DummyPass(FramePass):
    def __init__(self, name: str, reads=None, writes=None, inplace: bool = False):
        if reads is None:
            reads = set()
        if writes is None:
            writes = set()
        super().__init__(
            pass_name=name,
            reads=set(reads),
            writes=set(writes),
        )
        self._internal_symbols = ["a", "b", "c"]
        # Для inplace храним явную пару алиасов
        self._inplace = inplace
        if inplace and reads and writes:
            self._inplace_src = list(reads)[0] if reads else None
            self._inplace_dst = list(writes)[0] if writes else None
        else:
            self._inplace_src = None
            self._inplace_dst = None

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        if self._inplace and self._inplace_src and self._inplace_dst:
            return [(self._inplace_src, self._inplace_dst)]
        return []

    def get_internal_symbols(self) -> list[str]:
        return list(self._internal_symbols)


def test_framepass_has_no_internal_symbols_by_default():
    p = FramePass(pass_name="simple")
    assert p.get_internal_symbols() == []


def test_custom_pass_can_expose_internal_symbols():
    p = DummyPass(name="dummy")
    assert p.get_internal_symbols() == ["a", "b", "c"]


def test_debug_internal_point_configuration_is_mutable():
    p = FramePass(pass_name="p", reads={"in"}, writes={"out"})
    # по умолчанию точки дебага не заданы
    assert p.debug_internal_symbol is None
    assert p.get_debug_internal_point() is None

    # можно задать и прочитать конфигурацию
    p.set_debug_internal_point("foo")
    assert p.debug_internal_symbol == "foo"
    assert p.get_debug_internal_point() == "foo"

    # и сбросить её обратно
    p.set_debug_internal_point(None)
    assert p.debug_internal_symbol is None
    assert p.get_debug_internal_point() is None


def test_debugger_window_configuration():
    """Тест для set_debugger_window / get_debugger_window."""
    p = FramePass(pass_name="p")

    # По умолчанию окно не задано
    assert p.get_debugger_window() is None

    # Можно задать окно и callback
    mock_window = object()
    mock_callback = lambda x: None
    p.set_debugger_window(mock_window, mock_callback)
    assert p.get_debugger_window() is mock_window
    assert p._depth_capture_callback is mock_callback

    # Можно сбросить
    p.set_debugger_window(None)
    assert p.get_debugger_window() is None


def test_framegraph_builds_with_and_without_debug_internal_point():
    """
    Граф должен:
    * корректно строиться, когда у пассов есть внутренние символы,
      но точка дебага не выбрана;
    * так же корректно строиться, когда точка дебага выбрана.
    """
    p1 = FramePass(pass_name="A", reads=set(), writes={"a"})
    p2 = DummyPass(name="B", reads={"a"}, writes={"b"})

    # 1) Без конфигурации точки дебага
    graph1 = FrameGraph([p1, p2])
    schedule1 = [p.pass_name for p in graph1.build_schedule()]
    assert schedule1 == ["A", "B"]

    groups1 = graph1.fbo_alias_groups()
    # оба ресурса независимы и имеют свои канонические имена
    assert groups1["a"] == {"a"}
    assert groups1["b"] == {"b"}

    # 2) С установленной точкой дебага на втором пассе
    p2.set_debug_internal_point("b")

    graph2 = FrameGraph([p1, p2])
    schedule2 = [p.pass_name for p in graph2.build_schedule()]
    # порядок выполнения не должен измениться
    assert schedule2 == ["A", "B"]

    groups2 = graph2.fbo_alias_groups()
    # основные alias-группы сохраняются
    assert groups2["a"] == {"a"}
    assert groups2["b"] == {"b"}


def test_inplace_pass_with_debug_internal_point():
    """
    Inplace-пасс с установленным debug_internal_point должен
    корректно строиться (валидация не должна упасть).
    """
    # Inplace пасс: 1 read, 1 write
    p_inplace = DummyPass(
        name="InplaceWithDebug",
        reads={"input"},
        writes={"output"},
        inplace=True,
    )
    p_inplace.set_debug_internal_point("some_symbol")

    # Проверяем, что writes остаётся как есть (debug больше не добавляется в writes)
    assert "output" in p_inplace.writes
    assert len(p_inplace.writes) == 1

    # Граф должен корректно строиться
    p_source = FramePass(pass_name="Source", writes={"input"})
    graph = FrameGraph([p_source, p_inplace])
    schedule = [p.pass_name for p in graph.build_schedule()]
    assert schedule == ["Source", "InplaceWithDebug"]

    # Alias группы
    groups = graph.fbo_alias_groups()
    # input и output — синонимы (inplace)
    assert "input" in groups


# ---- Тесты для enabled флага ----

def test_framepass_enabled_by_default():
    """По умолчанию пасс включён."""
    p = FramePass(pass_name="test")
    assert p.enabled is True


def test_disabled_pass_not_in_schedule():
    """Отключённый пасс не попадает в расписание."""
    p1 = FramePass(pass_name="A", writes={"a"})
    p2 = FramePass(pass_name="B", reads={"a"}, writes={"b"})
    p3 = FramePass(pass_name="C", reads={"b"}, writes={"c"})

    # Все пассы включены — все в расписании
    graph1 = FrameGraph([p1, p2, p3])
    schedule1 = [p.pass_name for p in graph1.build_schedule()]
    assert schedule1 == ["A", "B", "C"]

    # Отключаем средний пасс
    p2.enabled = False
    graph2 = FrameGraph([p1, p2, p3])
    schedule2 = [p.pass_name for p in graph2.build_schedule()]
    # B отключён, его нет в расписании
    # C читает из b, но b никто не пишет — C всё равно выполнится
    # (просто получит пустой/внешний ресурс)
    assert "B" not in schedule2
    assert "A" in schedule2
    assert "C" in schedule2


def test_disabled_pass_does_not_conflict_writes():
    """
    Отключённый пасс не участвует в проверке конфликтов writes.
    Два пасса могут писать в один ресурс, если один из них отключён.
    """
    p1 = FramePass(pass_name="Writer1", writes={"shared"})
    p2 = FramePass(pass_name="Writer2", writes={"shared"})

    # Оба включены — конфликт
    from termin.visualization.render.framegraph.core import FrameGraphMultiWriterError
    import pytest

    with pytest.raises(FrameGraphMultiWriterError):
        FrameGraph([p1, p2]).build_schedule()

    # Отключаем один — конфликта нет
    p2.enabled = False
    graph = FrameGraph([p1, p2])
    schedule = [p.pass_name for p in graph.build_schedule()]
    assert schedule == ["Writer1"]


def test_disabled_pass_not_in_alias_groups():
    """Отключённый пасс не добавляет свои ресурсы в alias-группы."""
    p1 = FramePass(pass_name="A", writes={"a"})
    p2 = FramePass(pass_name="B", writes={"b"}, enabled=False)

    graph = FrameGraph([p1, p2])
    graph.build_schedule()  # нужно вызвать для построения canonical_resources
    groups = graph.fbo_alias_groups()

    assert "a" in groups
    assert "b" not in groups  # B отключён, его ресурс не учитывается
