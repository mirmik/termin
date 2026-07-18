"""Enable arbitration for legacy Python profiler summaries.

The standalone frame capture no longer lives here: its ring, analysis and UI
models are owned by the native ``FrameProfilerController``.
"""

from __future__ import annotations

from tcbase.profiler import Profiler


class ProfilerCaptureCoordinator:
    """Arbitrate the legacy process-global profiler enable request."""

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


__all__ = ["ProfilerCaptureCoordinator"]
