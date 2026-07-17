import pytest

from tcbase.profiler import FrameProfile, SectionTiming
from termin.editor_core.profiler_model import (
    ProfilerController,
    ProfilerPresentationModel,
)


def _frame(number, render_ms, events_ms=2.0):
    return FrameProfile(
        frame_number=number,
        total_ms=render_ms + events_ms,
        sections={
            "Render": SectionTiming(
                "Render",
                cpu_ms=render_ms,
                children_ms=render_ms * 0.5,
                call_count=1,
                children={
                    "Compose": SectionTiming(
                        "Compose",
                        cpu_ms=render_ms * 0.5,
                        call_count=2,
                    )
                },
            ),
            "Events": SectionTiming("Events", cpu_ms=events_ms, call_count=1),
        },
    )


def test_profiler_presentation_flattens_smooths_and_decays_sections():
    model = ProfilerPresentationModel(ema_alpha=0.5)
    first = model.update(_frame(1, 18.0))
    assert first.frame_ms == pytest.approx(20.0)
    assert first.fps == pytest.approx(50.0)
    assert [row.path for row in first.rows] == [
        ("Render",),
        ("Render", "Compose"),
        ("Events",),
    ]
    assert first.rows[0].percent == pytest.approx(90.0)
    assert first.rows[0].coverage_percent == pytest.approx(50.0)
    assert first.rows[1].depth == 1
    assert first.rows[1].call_count == 2

    second = model.update(_frame(2, 10.0, 2.0))
    assert second.frame_ms == pytest.approx(16.0)
    render = next(row for row in second.rows if row.path == ("Render",))
    assert render.cpu_ms == pytest.approx(14.0)

    empty = FrameProfile(frame_number=3, total_ms=8.0, sections={})
    third = model.update(empty)
    assert third.frame_ms == pytest.approx(12.0)
    assert next(row for row in third.rows if row.path == ("Render",)).cpu_ms == pytest.approx(7.0)


def test_profiler_presentation_keeps_slashes_structural_and_sorts_siblings_only():
    model = ProfilerPresentationModel(ema_alpha=1.0)
    frame = FrameProfile(
        frame_number=1,
        total_ms=20.0,
        sections={
            "Root/WithSlash": SectionTiming(
                "Root/WithSlash",
                cpu_ms=12.0,
                children_ms=3.0,
                children={"Child": SectionTiming("Child", cpu_ms=3.0)},
            ),
            "Other": SectionTiming("Other", cpu_ms=8.0),
        },
    )
    snapshot = model.update(frame)
    assert [row.path for row in snapshot.rows] == [
        ("Root/WithSlash",),
        ("Root/WithSlash", "Child"),
        ("Other",),
    ]
    assert snapshot.rows[0].has_children
    assert snapshot.rows[1].depth == 1


class FakeProfiler:
    def __init__(self):
        self.enabled = False
        self.frames = []
        self.clear_count = 0

    def clear_history(self):
        self.frames.clear()
        self.clear_count += 1

    def last_complete_frame(self):
        return self.frames[-1] if self.frames else None


def test_profiler_controller_controls_source_and_deduplicates_frames():
    profiler = FakeProfiler()
    include_ui = {"value": False}
    controller = ProfilerController(
        profiler,
        get_include_ui=lambda: include_ui["value"],
        set_include_ui=lambda value: include_ui.__setitem__("value", value),
    )

    controller.set_enabled(True)
    controller.set_include_ui(True)
    assert profiler.enabled and controller.include_ui
    profiler.frames.append(_frame(7, 14.0))
    assert controller.poll().frame_number == 7
    assert controller.poll() is None
    controller.clear()
    assert profiler.clear_count == 1
    controller.set_enabled(False)
    assert not profiler.enabled


def test_profiler_controller_requires_explicit_include_ui_boundary():
    controller = ProfilerController(FakeProfiler())
    with pytest.raises(RuntimeError, match="include-UI host boundary"):
        controller.set_include_ui(True)
