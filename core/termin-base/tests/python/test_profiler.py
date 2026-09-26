from types import SimpleNamespace

from termin.base.profiler import Profiler


def test_profiler_build_sections_preserves_order_and_branch_names():
    sections = [
        SimpleNamespace(parent_index=-1, name="Root", cpu_ms=8.0, children_ms=5.0, call_count=1),
        SimpleNamespace(parent_index=0, name="Shared", cpu_ms=3.0, children_ms=0.0, call_count=2),
        SimpleNamespace(parent_index=-1, name="Other", cpu_ms=4.0, children_ms=2.0, call_count=1),
        SimpleNamespace(parent_index=2, name="Shared", cpu_ms=2.0, children_ms=0.0, call_count=3),
        SimpleNamespace(parent_index=0, name="Last", cpu_ms=2.0, children_ms=0.0, call_count=1),
    ]
    result = {}
    Profiler.instance()._build_sections(sections, result)

    assert list(result) == ["Root", "Other"]
    assert list(result["Root"].children) == ["Shared", "Last"]
    assert result["Root"].children["Shared"].call_count == 2
    assert result["Other"].children["Shared"].call_count == 3
    assert result["Root"].cpu_ms == 8.0
    assert result["Root"].children_ms == 5.0


def test_profiler_build_sections_keeps_last_duplicate_sibling_value():
    sections = [
        SimpleNamespace(parent_index=-1, name="Root", cpu_ms=1.0, children_ms=0.0, call_count=1),
        SimpleNamespace(parent_index=0, name="Same", cpu_ms=1.0, children_ms=0.0, call_count=1),
        SimpleNamespace(parent_index=0, name="Other", cpu_ms=1.0, children_ms=0.0, call_count=1),
        SimpleNamespace(parent_index=0, name="Same", cpu_ms=2.0, children_ms=0.0, call_count=2),
    ]
    result = {}
    Profiler.instance()._build_sections(sections, result)

    assert list(result["Root"].children) == ["Same", "Other"]
    assert result["Root"].children["Same"].cpu_ms == 2.0


def test_profiler_last_complete_frame_excludes_open_history_slot():
    profiler = Profiler.instance()
    previous_enabled = profiler.enabled
    profiler.enabled = True
    profiler.clear_history()
    try:
        profiler.begin_frame()
        with profiler.section("First"):
            pass
        assert profiler.last_complete_frame() is None
        profiler.end_frame()

        first = profiler.last_complete_frame()
        assert first is not None
        assert list(first.sections) == ["First"]

        profiler.begin_frame()
        with profiler.section("Second"):
            pass
        assert profiler.last_complete_frame().frame_number == first.frame_number
        profiler.end_frame()
        assert profiler.last_complete_frame().frame_number == first.frame_number + 1
    finally:
        if profiler._current_frame is not None:
            profiler.end_frame()
        profiler.clear_history()
        profiler.enabled = previous_enabled


def test_profiler_history_after_preserves_raw_timing_and_reports_gaps():
    profiler = Profiler.instance()
    previous_enabled = profiler.enabled
    profiler.enabled = True
    profiler.clear_history()
    try:
        profiler._tc.begin_frame_with_info(1000.0, 19.0, 16.0, 3.0, 0)
        open_number = profiler._current_frame.frame_number
        assert profiler.history_after(open_number - 1).frames == ()
        profiler.end_frame()

        batch = profiler.history_after(open_number - 1)
        assert batch.dropped_count == 0
        assert [frame.frame_number for frame in batch.frames] == [open_number]
        frame = batch.frames[0]
        assert frame.start_time_ms == 1000.0
        assert frame.interval_ms == 19.0
        assert frame.target_interval_ms == 16.0
        assert frame.deadline_lateness_ms == 3.0
        assert frame.active_ms == frame.total_ms

        for index in range(125):
            profiler._tc.begin_frame_with_info(
                2000.0 + index * 16.0,
                16.0,
                16.0,
                0.0,
                0,
            )
            profiler.end_frame()
        overwritten = profiler.history_after(open_number)
        assert overwritten.dropped_count == 5
        assert len(overwritten.frames) == 120
        assert overwritten.frames[-1].frame_number == open_number + 125
    finally:
        if profiler._current_frame is not None:
            profiler.end_frame()
        profiler.clear_history()
        profiler.enabled = previous_enabled
