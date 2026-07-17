import pytest

from tcbase.profiler import FrameProfile, HistoryBatch, SectionTiming
from termin.editor_core.profiler_capture import (
    ProfilerCaptureCoordinator,
    ProfilerCaptureSession,
    project_captured_sections,
)
from termin.editor_core.profiler_model import ProfilerController


def _frame(
    number: int,
    interval: float,
    *,
    active: float = 5.0,
    target: float = 16.0,
    lateness: float = 0.0,
    missed: int = 0,
) -> FrameProfile:
    return FrameProfile(
        frame_number=number,
        start_time_ms=number * target,
        interval_ms=interval,
        active_ms=active,
        total_ms=active,
        target_interval_ms=target,
        deadline_lateness_ms=lateness,
        missed_intervals=missed,
    )


class FakeHistoryProfiler:
    def __init__(self, source_capacity: int = 120) -> None:
        self.enabled = False
        self.source_capacity = source_capacity
        self.frames: list[FrameProfile] = []

    def append(self, frame: FrameProfile) -> None:
        self.frames.append(frame)
        self.frames = self.frames[-self.source_capacity :]

    def history_after(self, cursor: int) -> HistoryBatch:
        oldest = self.frames[0].frame_number if self.frames else -1
        newest = self.frames[-1].frame_number if self.frames else -1
        dropped = max(0, oldest - cursor - 1) if cursor >= 0 and oldest >= 0 else 0
        return HistoryBatch(
            frames=tuple(frame for frame in self.frames if frame.frame_number > cursor),
            dropped_count=dropped,
            oldest_frame_number=oldest,
            newest_frame_number=newest,
        )

    def last_complete_frame(self) -> FrameProfile | None:
        return self.frames[-1] if self.frames else None

    def clear_history(self) -> None:
        self.frames.clear()


def test_capture_coordinator_keeps_profiler_enabled_until_last_consumer_releases():
    profiler = FakeHistoryProfiler()
    coordinator = ProfilerCaptureCoordinator(profiler)
    coordinator.acquire("summary")
    coordinator.acquire("frame-window")
    coordinator.release("summary")
    assert profiler.enabled
    assert coordinator.consumers == ("frame-window",)
    coordinator.release("frame-window")
    assert not profiler.enabled


def test_summary_controller_does_not_clear_or_disable_another_capture():
    profiler = FakeHistoryProfiler()
    coordinator = ProfilerCaptureCoordinator(profiler)
    coordinator.acquire("frame-window")
    controller = ProfilerController(
        profiler,
        capture_coordinator=coordinator,
        consumer_id="summary",
    )
    controller.set_enabled(True)
    profiler.append(_frame(1, 16.0))
    controller.clear()
    assert profiler.frames
    controller.set_enabled(False)
    assert profiler.enabled
    assert not controller.enabled
    coordinator.release("frame-window")


def test_capture_pause_resume_skips_frames_produced_while_paused():
    profiler = FakeHistoryProfiler()
    coordinator = ProfilerCaptureCoordinator(profiler)
    session = ProfilerCaptureSession(coordinator, capacity=8)
    profiler.append(_frame(1, 16.0))
    session.start_capture()
    assert session.poll() == 1
    session.pause()
    profiler.append(_frame(2, 40.0))
    assert session.poll() == 0
    session.start_capture()
    profiler.append(_frame(3, 17.0))
    assert session.poll() == 1
    assert [frame.frame_number for frame in session.frames] == [1, 3]
    assert session.frames[-1].pacing_gap_ms is None


def test_capture_reports_source_gap_and_reconciles_evicted_selection():
    profiler = FakeHistoryProfiler(source_capacity=3)
    coordinator = ProfilerCaptureCoordinator(profiler)
    session = ProfilerCaptureSession(coordinator, capacity=2)
    session.start_capture()
    profiler.append(_frame(1, 16.0))
    assert session.poll() == 1
    assert session.select_frame(1)
    for number in range(2, 7):
        profiler.append(_frame(number, 16.0))
    assert session.poll() == 3
    assert session.source_dropped_count == 2
    assert [frame.frame_number for frame in session.frames] == [5, 6]
    assert session.selected_frame is None
    assert session.frames[0].source_gap_before == 0


def test_capture_statistics_and_hitch_navigation_use_raw_intervals():
    profiler = FakeHistoryProfiler()
    coordinator = ProfilerCaptureCoordinator(profiler)
    session = ProfilerCaptureSession(coordinator, capacity=8, hitch_ratio=1.25)
    session.start_capture()
    for number, interval in enumerate((10.0, 20.0, 30.0, 40.0), start=1):
        profiler.append(
            _frame(number, interval, lateness=max(0.0, interval - 16.0))
        )
    assert session.poll() == 4
    stats = session.statistics()
    assert stats.frame_count == 4
    assert stats.interval_p50_ms == 25.0
    assert stats.interval_p95_ms == 38.5
    assert stats.interval_p99_ms == pytest.approx(39.7)
    assert stats.max_interval_ms == 40.0
    assert stats.hitch_count == 2
    assert session.select_frame(1)
    assert session.select_adjacent_hitch(1)
    assert session.selected_frame_number == 3
    assert session.select_adjacent_hitch(1)
    assert session.selected_frame_number == 4
    assert session.select_adjacent_hitch(-1)
    assert session.selected_frame_number == 3


def test_raw_frame_section_projection_preserves_hierarchy_and_self_time():
    frame = _frame(7, 18.0, active=10.0)
    frame.sections = {
        "Render": SectionTiming(
            "Render",
            cpu_ms=8.0,
            children_ms=5.0,
            call_count=1,
            children={
                "Opaque": SectionTiming("Opaque", cpu_ms=5.0, call_count=3),
            },
        ),
        "Input": SectionTiming("Input", cpu_ms=1.0, call_count=1),
    }

    rows = project_captured_sections(frame)

    assert [row.path for row in rows] == [
        ("Render",),
        ("Render", "Opaque"),
        ("Input",),
    ]
    assert rows[0].self_ms == 3.0
    assert rows[0].percent == 80.0
    assert rows[0].coverage_percent == 62.5
    assert rows[1].call_count == 3
