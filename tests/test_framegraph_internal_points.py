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

    Когда debug_internal_output установлен, он попадает в effective_writes
    и учитывается при построении графа зависимостей и создании FBO.
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
    # основные alias-группы сохраняются
    assert groups2["a"] == {"a"}
    assert groups2["b"] == {"b"}
    # debug-ресурс теперь учитывается в effective_writes и появляется в группах
    # (это позволяет framegraph создать для него FBO)
    assert "debug_b" in groups2
    assert groups2["debug_b"] == {"debug_b"}
    # canonical_resource для debug-ресурса возвращает его имя
    assert graph2.canonical_resource("debug_b") == "debug_b"


def test_inplace_pass_with_debug_internal_output():
    """
    Inplace-пасс с установленным debug_internal_output должен:
    * корректно строиться (валидация не должна упасть)
    * иметь debug-ресурс в writes после set_debug_internal_point
    * создавать отдельную группу FBO для debug-ресурса
    """
    # Inplace пасс: 1 read, 1 write + debug output
    p_inplace = FramePass(
        pass_name="InplaceWithDebug",
        reads={"input"},
        writes={"output"},
        inplace=True,
    )
    p_inplace.set_debug_internal_point("some_symbol", "debug_output")

    # Проверяем, что writes включает и output, и debug_output
    assert "output" in p_inplace.writes
    assert "debug_output" in p_inplace.writes
    assert len(p_inplace.writes) == 2

    # Граф должен корректно строиться
    p_source = FramePass(pass_name="Source", writes={"input"})
    graph = FrameGraph([p_source, p_inplace])
    schedule = [p.pass_name for p in graph.build_schedule()]
    assert schedule == ["Source", "InplaceWithDebug"]

    # Alias группы должны содержать debug_output отдельно
    groups = graph.fbo_alias_groups()
    # input и output — синонимы (inplace)
    assert "input" in groups
    # debug_output — отдельная группа
    assert "debug_output" in groups
    assert groups["debug_output"] == {"debug_output"}

    # При сбросе debug_internal_point, debug_output должен удалиться из writes
    p_inplace.set_debug_internal_point(None, None)
    assert "output" in p_inplace.writes
    assert "debug_output" not in p_inplace.writes
    assert len(p_inplace.writes) == 1


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
