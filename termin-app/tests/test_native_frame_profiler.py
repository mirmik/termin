from tcbase.profiler import FrameProfile, HistoryBatch, SectionTiming

from termin.editor_core.profiler_capture import (
    ProfilerCaptureCoordinator,
    ProfilerCaptureSession,
)
from termin.editor_native.frame_profiler import (
    build_native_frame_profiler,
    connect_frame_profiler_command,
)


class FakeHistoryProfiler:
    def __init__(self) -> None:
        self.enabled = False
        self.frames: list[FrameProfile] = []

    def history_after(self, cursor: int) -> HistoryBatch:
        return HistoryBatch(
            frames=tuple(frame for frame in self.frames if frame.frame_number > cursor),
            dropped_count=0,
            oldest_frame_number=self.frames[0].frame_number if self.frames else -1,
            newest_frame_number=self.frames[-1].frame_number if self.frames else -1,
        )


class FakeWindow:
    def __init__(self, on_close) -> None:
        self.closed = False
        self._on_close = on_close
        self.render_requests = 0

    def request_render_update(self) -> None:
        self.render_requests += 1

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self._on_close()


class FakeWindowManager:
    def __init__(self) -> None:
        self.created = []

    def create_window(self, title, width, height, *, document, on_close):
        window = FakeWindow(on_close)
        self.created.append((title, width, height, document, window))
        return window


class FakeMenuRoute:
    def __init__(self) -> None:
        self.callback = None

    def connect_activated(self, callback) -> None:
        self.callback = callback


def _build_profiler(window_manager, session, *, request_render=lambda: None):
    include_ui = {"value": False}
    profiler = build_native_frame_profiler(
        window_manager,
        session,
        request_render=request_render,
        get_include_ui=lambda: include_ui["value"],
        set_include_ui=lambda value: include_ui.__setitem__("value", value),
    )
    return profiler, include_ui


def _frame(number: int, interval_ms: float) -> FrameProfile:
    return FrameProfile(
        frame_number=number,
        interval_ms=interval_ms,
        active_ms=8.0,
        total_ms=8.0,
        target_interval_ms=16.0,
        deadline_lateness_ms=max(interval_ms - 16.0, 0.0),
        sections={
            "Engine": SectionTiming(
                "Engine",
                cpu_ms=7.0,
                children_ms=4.0,
                children={"Render": SectionTiming("Render", cpu_ms=4.0)},
            )
        },
    )


def test_native_frame_profiler_projects_capture_and_timeline_selection():
    source = FakeHistoryProfiler()
    session = ProfilerCaptureSession(ProfilerCaptureCoordinator(source), capacity=16)
    session.start_capture()
    source.frames.extend([_frame(1, 16.0), _frame(2, 28.0)])
    assert session.poll() == 2
    renders = []

    profiler, include_ui = _build_profiler(
        object(),
        session,
        request_render=lambda: renders.append(True),
    )

    assert len(profiler.timeline_model.samples) == 2
    assert profiler.timeline.selected_id == 2
    assert profiler.section_model.node_count == 2
    assert profiler.timeline.select(1)
    assert session.selected_frame_number == 1
    assert not session.follow_latest
    assert profiler.command_model.command(profiler.commands["follow"]).data.checked is False
    assert renders
    assert profiler.command_model.command(profiler.commands["capture"]).data.label == "Pause"
    assert not profiler.command_model.command(profiler.commands["include-ui"]).data.checked
    profiler.set_include_ui(True)
    profiler.refresh(force=True)
    assert include_ui["value"]
    assert profiler.command_model.command(profiler.commands["include-ui"]).data.checked


def test_native_frame_profiler_clear_keeps_capture_enabled():
    source = FakeHistoryProfiler()
    session = ProfilerCaptureSession(ProfilerCaptureCoordinator(source), capacity=16)
    session.start_capture()
    source.frames.append(_frame(1, 16.0))
    session.poll()
    profiler, _include_ui = _build_profiler(object(), session)

    profiler.clear()

    assert session.capturing
    assert source.enabled
    assert profiler.timeline_model.samples == []
    assert profiler.section_model.node_count == 0


def test_native_frame_profiler_window_lifecycle_preserves_buffer_and_releases_capture():
    source = FakeHistoryProfiler()
    session = ProfilerCaptureSession(ProfilerCaptureCoordinator(source), capacity=16)
    manager = FakeWindowManager()
    profiler, _include_ui = _build_profiler(manager, session)
    profiler.refresh_interval_seconds = 0.0
    route = FakeMenuRoute()
    connect_frame_profiler_command(route, 42, profiler)

    route.callback(0, 42, None)
    assert session.capturing
    assert len(manager.created) == 1
    source.frames.append(_frame(1, 16.0))
    assert profiler.update()
    profiler.dismiss()
    assert not session.capturing
    assert len(session.frames) == 1

    source.frames.append(_frame(2, 40.0))
    assert profiler.show()
    source.frames.append(_frame(3, 17.0))
    assert profiler.update()
    assert [frame.frame_number for frame in session.frames] == [1, 3]
    assert len(manager.created) == 2
    profiler.close()


def test_native_frame_profiler_throttles_projection_without_skipping_capture():
    source = FakeHistoryProfiler()
    session = ProfilerCaptureSession(ProfilerCaptureCoordinator(source), capacity=16)
    session.start_capture()
    profiler, _include_ui = _build_profiler(object(), session)
    profiler.window = FakeWindow(lambda: None)
    profiler.refresh_interval_seconds = 60.0
    source.frames.append(_frame(1, 16.0))

    assert not profiler.update()
    assert [frame.frame_number for frame in session.frames] == [1]
    assert profiler.timeline_model.samples == []

    profiler.refresh_interval_seconds = 0.0
    assert profiler.update()
    assert [sample.stable_id for sample in profiler.timeline_model.samples] == [1]


def test_native_frame_profiler_appends_timeline_samples_incrementally():
    source = FakeHistoryProfiler()
    session = ProfilerCaptureSession(ProfilerCaptureCoordinator(source), capacity=16)
    session.start_capture()
    profiler, _include_ui = _build_profiler(object(), session)
    profiler.window = FakeWindow(lambda: None)
    profiler.refresh_interval_seconds = 0.0

    source.frames.append(_frame(1, 16.0))
    assert profiler.update()
    first_revision = profiler.timeline_model.revision
    assert [sample.stable_id for sample in profiler.timeline_model.samples] == [1]

    source.frames.append(_frame(2, 17.0))
    assert profiler.update()
    assert profiler.timeline_model.revision == first_revision + 1
    assert [sample.stable_id for sample in profiler.timeline_model.samples] == [1, 2]
