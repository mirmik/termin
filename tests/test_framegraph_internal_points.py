from __future__ import annotations

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
            inplace=inplace,
        )
        self._internal_symbols = ["a", "b", "c"]

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
    assert p.debug_internal_output is None
    assert p.get_debug_internal_point() == (None, None)

    # можно задать и прочитать конфигурацию
    p.set_debug_internal_point("foo", "debug_out")
    assert p.debug_internal_symbol == "foo"
    assert p.debug_internal_output == "debug_out"
    assert p.get_debug_internal_point() == ("foo", "debug_out")

    # и сбросить её обратно
    p.set_debug_internal_point(None, None)
    assert p.debug_internal_symbol is None
    assert p.debug_internal_output is None
    assert p.get_debug_internal_point() == (None, None)


def test_framegraph_builds_with_and_without_debug_internal_point():
    """
    Граф должен:
    * корректно строиться, когда у пассов есть внутренние символы,
      но точка дебага не выбрана;
    * так же корректно строиться, когда точка дебага выбрана
      (в том числе с указанием отдельного ресурса вывода).
    В обоих случаях alias-группы зависят только от reads/writes,
    а не от настроек внутренних точек.
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
    # debug-ресурс не фигурирует, так как мы его не задавали
    assert "debug_b" not in groups1

    # 2) С установленной точкой дебага на втором пассе
    p2.set_debug_internal_point("b", "debug_b")

    graph2 = FrameGraph([p1, p2])
    schedule2 = [p.pass_name for p in graph2.build_schedule()]
    # порядок выполнения не должен измениться
    assert schedule2 == ["A", "B"]

    groups2 = graph2.fbo_alias_groups()
    # alias-группы по-прежнему зависят только от reads/writes
    assert groups2["a"] == {"a"}
    assert groups2["b"] == {"b"}
    # debug-ресурс не попадает в alias-группы, так как FrameGraph
    # не рассматривает его как обычный выход пасса
    assert "debug_b" not in groups2
    # canonical_resource для debug-ресурса должен вернуть его же имя
    # (FrameGraph о нём ничего не знает)
    assert graph2.canonical_resource("debug_b") == "debug_b"
