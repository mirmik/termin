"""Toolkit-neutral profiler sampling, smoothing and section presentation."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from tcbase.profiler import FrameProfile, Profiler, SectionStats, SectionTiming


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProfilerSectionRow:
    path: tuple[str, ...]
    name: str
    depth: int
    cpu_ms: float
    percent: float
    coverage_percent: float
    call_count: int
    has_children: bool


@dataclass(frozen=True)
class ProfilerSnapshot:
    frame_number: int
    frame_ms: float
    fps: float
    rows: tuple[ProfilerSectionRow, ...]
    revision: int


def _flatten_sections(
    sections: dict[str, SectionTiming],
    prefix: tuple[str, ...] = (),
) -> dict[tuple[str, ...], SectionStats]:
    result: dict[tuple[str, ...], SectionStats] = {}
    for name, timing in sections.items():
        path = (*prefix, name)
        result[path] = SectionStats(
            cpu_ms=timing.cpu_ms,
            children_ms=timing.children_ms,
            call_count=timing.call_count,
        )
        result.update(_flatten_sections(timing.children, path))
    return result


class ProfilerPresentationModel:
    def __init__(self, *, ema_alpha: float = 0.1) -> None:
        if not 0.0 < ema_alpha <= 1.0:
            raise ValueError("ema_alpha must be within (0, 1]")
        self.ema_alpha = float(ema_alpha)
        self._section_ms: dict[tuple[str, ...], float] = {}
        self._children_ms: dict[tuple[str, ...], float] = {}
        self._calls: dict[tuple[str, ...], int] = {}
        self._total_ms: float | None = None
        self._revision = 0

    def reset(self) -> None:
        self._section_ms.clear()
        self._children_ms.clear()
        self._calls.clear()
        self._total_ms = None
        self._revision += 1

    def update(self, frame: FrameProfile) -> ProfilerSnapshot:
        sections = _flatten_sections(frame.sections)
        root_total = sum(
            stats.cpu_ms for path, stats in sections.items() if len(path) == 1
        )
        total = root_total if root_total > 0.0 else max(float(frame.total_ms), 0.0)
        alpha = self.ema_alpha
        if self._total_ms is None:
            self._total_ms = total
        else:
            self._total_ms = self._total_ms * (1.0 - alpha) + total * alpha

        for path, stats in sections.items():
            previous = self._section_ms.get(path)
            previous_children = self._children_ms.get(path)
            if previous is None:
                self._section_ms[path] = stats.cpu_ms
                self._children_ms[path] = stats.children_ms
            else:
                self._section_ms[path] = previous * (1.0 - alpha) + stats.cpu_ms * alpha
                self._children_ms[path] = (
                    (previous_children or 0.0) * (1.0 - alpha)
                    + stats.children_ms * alpha
                )
            self._calls[path] = stats.call_count

        expired: set[tuple[str, ...]] = set()
        for path in tuple(self._section_ms):
            if path in sections:
                continue
            self._section_ms[path] *= 1.0 - alpha
            self._children_ms[path] = self._children_ms.get(path, 0.0) * (1.0 - alpha)
            if self._section_ms[path] < 0.01:
                expired.add(path)

        # A tree-table cannot contain orphan rows. If a decayed parent expires,
        # retire its descendants with it even if their individual EMA happens to
        # remain just above the threshold.
        for expired_path in sorted(expired, key=len):
            for path in tuple(self._section_ms):
                if path[: len(expired_path)] != expired_path:
                    continue
                self._section_ms.pop(path, None)
                self._children_ms.pop(path, None)
                self._calls.pop(path, None)

        frame_ms = self._total_ms
        children: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
        for path in self._section_ms:
            children.setdefault(path[:-1], []).append(path)
        for siblings in children.values():
            siblings.sort(key=lambda path: (-self._section_ms[path], path[-1]))

        ordered_paths: list[tuple[str, ...]] = []

        def append_subtree(parent: tuple[str, ...]) -> None:
            for path in children.get(parent, ()):
                ordered_paths.append(path)
                append_subtree(path)

        append_subtree(())

        rows = []
        for path in ordered_paths:
            cpu_ms = self._section_ms[path]
            children_ms = self._children_ms.get(path, 0.0)
            rows.append(
                ProfilerSectionRow(
                    path=path,
                    name=path[-1],
                    depth=len(path) - 1,
                    cpu_ms=cpu_ms,
                    percent=cpu_ms / frame_ms * 100.0 if frame_ms > 0.0 else 0.0,
                    coverage_percent=(
                        children_ms / cpu_ms * 100.0 if cpu_ms > 0.0 else 0.0
                    ),
                    call_count=self._calls.get(path, 0),
                    has_children=bool(children.get(path)),
                )
            )
        self._revision += 1
        return ProfilerSnapshot(
            frame_number=frame.frame_number,
            frame_ms=frame_ms,
            fps=1000.0 / frame_ms if frame_ms > 0.0 else 0.0,
            rows=tuple(rows),
            revision=self._revision,
        )


class ProfilerController:
    def __init__(
        self,
        profiler: Profiler | None = None,
        *,
        presentation: ProfilerPresentationModel | None = None,
        get_include_ui: Callable[[], bool] | None = None,
        set_include_ui: Callable[[bool], None] | None = None,
    ) -> None:
        self.profiler = profiler if profiler is not None else Profiler.instance()
        self.presentation = (
            presentation if presentation is not None else ProfilerPresentationModel()
        )
        self._get_include_ui = get_include_ui
        self._set_include_ui = set_include_ui
        self._last_frame_number: int | None = None

    @property
    def enabled(self) -> bool:
        return self.profiler.enabled

    @property
    def detailed(self) -> bool:
        return self.profiler.detailed_rendering

    @property
    def include_ui(self) -> bool:
        if self._get_include_ui is None:
            return False
        return bool(self._get_include_ui())

    def set_enabled(self, enabled: bool) -> None:
        self.profiler.enabled = bool(enabled)
        if not enabled:
            self.presentation.reset()
            self._last_frame_number = None

    def set_detailed(self, detailed: bool) -> None:
        self.profiler.detailed_rendering = bool(detailed)

    def set_include_ui(self, include: bool) -> None:
        if self._set_include_ui is None:
            _logger.error("ProfilerController has no include-UI host boundary")
            raise RuntimeError("ProfilerController has no include-UI host boundary")
        self._set_include_ui(bool(include))

    def clear(self) -> None:
        self.profiler.clear_history()
        self.presentation.reset()
        self._last_frame_number = None

    def poll(self) -> ProfilerSnapshot | None:
        if not self.profiler.enabled:
            return None
        frame = self.profiler.last_complete_frame()
        if frame is None or frame.frame_number == self._last_frame_number:
            return None
        self._last_frame_number = frame.frame_number
        return self.presentation.update(frame)


__all__ = [
    "ProfilerController",
    "ProfilerPresentationModel",
    "ProfilerSectionRow",
    "ProfilerSnapshot",
]
