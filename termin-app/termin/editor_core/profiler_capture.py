"""Toolkit-neutral raw frame capture and hitch analysis."""

from __future__ import annotations

from dataclasses import dataclass

from tcbase.profiler import FrameProfile, Profiler, SectionTiming


@dataclass(frozen=True)
class CapturedFrame:
    profile: FrameProfile
    pacing_gap_ms: float | None
    source_gap_before: int
    hitch: bool

    @property
    def frame_number(self) -> int:
        return self.profile.frame_number

    @property
    def interval_ms(self) -> float:
        return self.profile.interval_ms

    @property
    def active_ms(self) -> float:
        return self.profile.active_ms


@dataclass(frozen=True)
class FrameRangeStatistics:
    frame_count: int
    interval_p50_ms: float
    interval_p95_ms: float
    interval_p99_ms: float
    max_interval_ms: float
    max_active_ms: float
    max_lateness_ms: float
    hitch_count: int
    source_dropped_count: int


@dataclass(frozen=True)
class CapturedSectionRow:
    """One stable tree row projected from a single raw captured frame."""

    path: tuple[str, ...]
    name: str
    inclusive_ms: float
    self_ms: float
    percent: float
    coverage_percent: float
    call_count: int
    has_children: bool


def project_captured_sections(frame: FrameProfile) -> tuple[CapturedSectionRow, ...]:
    """Project raw section timings without smoothing or frontend state."""

    denominator = max(float(frame.active_ms), float(frame.total_ms), 0.0)
    rows: list[CapturedSectionRow] = []

    def append_sections(
        sections: dict[str, SectionTiming],
        prefix: tuple[str, ...],
    ) -> None:
        ordered = sorted(sections.items(), key=lambda item: (-item[1].cpu_ms, item[0]))
        for name, timing in ordered:
            path = (*prefix, name)
            inclusive_ms = max(float(timing.cpu_ms), 0.0)
            children_ms = max(float(timing.children_ms), 0.0)
            rows.append(
                CapturedSectionRow(
                    path=path,
                    name=name,
                    inclusive_ms=inclusive_ms,
                    self_ms=max(inclusive_ms - children_ms, 0.0),
                    percent=(inclusive_ms / denominator * 100.0 if denominator > 0.0 else 0.0),
                    coverage_percent=(
                        children_ms / inclusive_ms * 100.0 if inclusive_ms > 0.0 else 0.0
                    ),
                    call_count=int(timing.call_count),
                    has_children=bool(timing.children),
                )
            )
            append_sections(timing.children, path)

    append_sections(frame.sections, ())
    return tuple(rows)


class ProfilerCaptureCoordinator:
    """Arbitrate the process-global profiler between frontend consumers."""

    def __init__(self, profiler: Profiler | None = None) -> None:
        self.profiler = profiler if profiler is not None else Profiler.instance()
        self._consumers: set[str] = set()

    @property
    def consumers(self) -> tuple[str, ...]:
        return tuple(sorted(self._consumers))

    def acquire(self, consumer_id: str) -> None:
        if not consumer_id:
            raise ValueError("profiler capture consumer_id must not be empty")
        self._consumers.add(consumer_id)
        self.profiler.enabled = True

    def release(self, consumer_id: str) -> None:
        self._consumers.discard(consumer_id)
        if not self._consumers:
            self.profiler.enabled = False


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


class ProfilerCaptureSession:
    """Bounded raw-frame analysis session consumed by profiler frontends."""

    def __init__(
        self,
        coordinator: ProfilerCaptureCoordinator,
        *,
        consumer_id: str = "frame-profiler",
        capacity: int = 600,
        hitch_ratio: float = 1.25,
    ) -> None:
        if capacity <= 0:
            raise ValueError("profiler capture capacity must be positive")
        if hitch_ratio <= 1.0:
            raise ValueError("profiler hitch_ratio must be greater than one")
        if not consumer_id:
            raise ValueError("profiler capture consumer_id must not be empty")
        self.coordinator = coordinator
        self.consumer_id = consumer_id
        self.capacity = int(capacity)
        self.hitch_ratio = float(hitch_ratio)
        self._frames: list[CapturedFrame] = []
        self._cursor = -1
        self._capturing = False
        self._started = False
        self._follow_latest = True
        self._selected_frame_number: int | None = None
        self._source_dropped_count = 0
        self._revision = 1

    @property
    def frames(self) -> tuple[CapturedFrame, ...]:
        return tuple(self._frames)

    @property
    def capturing(self) -> bool:
        return self._capturing

    @property
    def follow_latest(self) -> bool:
        return self._follow_latest

    @property
    def selected_frame_number(self) -> int | None:
        return self._selected_frame_number

    @property
    def selected_frame(self) -> CapturedFrame | None:
        if self._selected_frame_number is None:
            return None
        return next(
            (frame for frame in self._frames if frame.frame_number == self._selected_frame_number),
            None,
        )

    @property
    def source_dropped_count(self) -> int:
        return self._source_dropped_count

    @property
    def revision(self) -> int:
        return self._revision

    def start_capture(self) -> None:
        if self._capturing:
            return
        if self._started:
            self._skip_source_to_latest()
        self.coordinator.acquire(self.consumer_id)
        self._capturing = True
        self._started = True
        self._revision += 1

    def pause(self) -> None:
        if not self._capturing:
            return
        self._capturing = False
        self.coordinator.release(self.consumer_id)
        self._revision += 1

    def close(self) -> None:
        self.pause()

    def clear(self) -> None:
        self._frames.clear()
        self._selected_frame_number = None
        self._source_dropped_count = 0
        self._skip_source_to_latest()
        self._revision += 1

    def _skip_source_to_latest(self) -> None:
        batch = self.coordinator.profiler.history_after(self._cursor)
        if batch.newest_frame_number >= 0:
            self._cursor = batch.newest_frame_number

    def poll(self) -> int:
        if not self._capturing:
            return 0
        batch = self.coordinator.profiler.history_after(self._cursor)
        if batch.newest_frame_number >= 0:
            self._cursor = batch.newest_frame_number
        if not batch.frames:
            if batch.dropped_count:
                self._source_dropped_count += batch.dropped_count
                self._revision += 1
            return 0

        self._source_dropped_count += batch.dropped_count
        previous = self._frames[-1] if self._frames else None
        for index, profile in enumerate(batch.frames):
            consecutive = previous is not None and profile.frame_number == previous.frame_number + 1
            pacing_gap = (
                max(0.0, profile.interval_ms - previous.active_ms)
                if consecutive and profile.interval_ms > 0.0
                else None
            )
            target = profile.target_interval_ms
            hitch = profile.missed_intervals > 0 or (
                target > 0.0 and profile.interval_ms > target * self.hitch_ratio
            )
            captured = CapturedFrame(
                profile=profile,
                pacing_gap_ms=pacing_gap,
                source_gap_before=batch.dropped_count if index == 0 else 0,
                hitch=hitch,
            )
            self._frames.append(captured)
            previous = captured

        overflow = max(0, len(self._frames) - self.capacity)
        if overflow:
            del self._frames[:overflow]
        if self._follow_latest and self._frames:
            self._selected_frame_number = self._frames[-1].frame_number
        elif self.selected_frame is None:
            self._selected_frame_number = None
        self._revision += 1
        return len(batch.frames)

    def set_follow_latest(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._follow_latest == enabled:
            return
        self._follow_latest = enabled
        if enabled and self._frames:
            self._selected_frame_number = self._frames[-1].frame_number
        self._revision += 1

    def select_frame(self, frame_number: int) -> bool:
        if not any(frame.frame_number == frame_number for frame in self._frames):
            return False
        self._selected_frame_number = int(frame_number)
        self._follow_latest = False
        self._revision += 1
        return True

    def select_adjacent_hitch(self, direction: int) -> bool:
        if direction == 0:
            return False
        hitches = [frame.frame_number for frame in self._frames if frame.hitch]
        if not hitches:
            return False
        selected = self._selected_frame_number
        candidates = (
            [number for number in hitches if selected is None or number > selected]
            if direction > 0
            else [number for number in hitches if selected is None or number < selected]
        )
        if not candidates:
            return False
        target = candidates[0] if direction > 0 else candidates[-1]
        return self.select_frame(target)

    def statistics(
        self,
        start_frame_number: int | None = None,
        end_frame_number: int | None = None,
    ) -> FrameRangeStatistics:
        frames = [
            frame
            for frame in self._frames
            if (start_frame_number is None or frame.frame_number >= start_frame_number)
            and (end_frame_number is None or frame.frame_number <= end_frame_number)
        ]
        intervals = [frame.interval_ms for frame in frames if frame.interval_ms > 0.0]
        return FrameRangeStatistics(
            frame_count=len(frames),
            interval_p50_ms=_percentile(intervals, 0.50),
            interval_p95_ms=_percentile(intervals, 0.95),
            interval_p99_ms=_percentile(intervals, 0.99),
            max_interval_ms=max(intervals, default=0.0),
            max_active_ms=max((frame.active_ms for frame in frames), default=0.0),
            max_lateness_ms=max(
                (frame.profile.deadline_lateness_ms for frame in frames),
                default=0.0,
            ),
            hitch_count=sum(frame.hitch for frame in frames),
            source_dropped_count=sum(frame.source_gap_before for frame in frames),
        )


__all__ = [
    "CapturedFrame",
    "CapturedSectionRow",
    "FrameRangeStatistics",
    "ProfilerCaptureCoordinator",
    "ProfilerCaptureSession",
    "project_captured_sections",
]
