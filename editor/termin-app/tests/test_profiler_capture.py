from tcbase.profiler import FrameProfile

from termin.editor_core.profiler_capture import ProfilerCaptureCoordinator
from termin.editor_core.profiler_model import ProfilerController


class FakeHistoryProfiler:
    def __init__(self) -> None:
        self.enabled = False
        self.frames: list[FrameProfile] = []

    def last_complete_frame(self) -> FrameProfile | None:
        return self.frames[-1] if self.frames else None

    def clear_history(self) -> None:
        self.frames.clear()


def test_capture_coordinator_keeps_profiler_enabled_until_last_consumer_releases():
    profiler = FakeHistoryProfiler()
    coordinator = ProfilerCaptureCoordinator(profiler)
    coordinator.acquire("summary")
    coordinator.acquire("another-summary")
    coordinator.release("summary")
    assert profiler.enabled
    assert coordinator.consumers == ("another-summary",)
    coordinator.release("another-summary")
    assert not profiler.enabled


def test_summary_controller_does_not_clear_another_legacy_consumer():
    profiler = FakeHistoryProfiler()
    coordinator = ProfilerCaptureCoordinator(profiler)
    coordinator.acquire("another-summary")
    controller = ProfilerController(
        profiler,
        capture_coordinator=coordinator,
        consumer_id="summary",
    )
    controller.set_enabled(True)
    profiler.frames.append(FrameProfile(frame_number=1))
    controller.clear()
    assert profiler.frames
    controller.set_enabled(False)
    assert profiler.enabled
    coordinator.release("another-summary")
