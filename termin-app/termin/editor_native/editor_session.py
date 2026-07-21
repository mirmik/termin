"""Explicit staged lifetime boundary for one native editor frontend."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar


_logger = logging.getLogger(__name__)
_T = TypeVar("_T")


@dataclass(slots=True)
class _OwnedObject:
    name: str
    value: object
    cleanup: Callable[[], None] | None


class EditorSessionStage:
    """Own objects created at one dependency-ordered initialization stage."""

    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("editor session stage name must not be empty")
        self.name = name
        self._objects: list[_OwnedObject] = []
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def own(
        self,
        name: str,
        value: _T,
        cleanup: Callable[[], None] | None = None,
    ) -> _T:
        """Retain one object and optionally register its teardown operation."""
        if self._closed:
            raise RuntimeError(f"editor session stage '{self.name}' is closed")
        if not name:
            raise ValueError("owned object name must not be empty")
        self._objects.append(_OwnedObject(name, value, cleanup))
        return value

    def add_cleanup(self, name: str, cleanup: Callable[[], None]) -> None:
        """Register teardown that does not correspond to a retained Python object."""
        self.own(name, cleanup, cleanup)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        objects = self._objects
        self._objects = []
        for owned in reversed(objects):
            if owned.cleanup is None:
                continue
            try:
                owned.cleanup()
            except Exception:
                _logger.exception(
                    "Editor session cleanup failed: stage='%s', object='%s'",
                    self.name,
                    owned.name,
                )


class EditorSession:
    """Own editor stages on both sides of the EngineCore shutdown boundary."""

    def __init__(
        self,
        *,
        failure_injector: Callable[[str], None] | None = None,
    ) -> None:
        self._failure_injector = failure_injector
        self._engine_stages: list[EditorSessionStage] = []
        self._backend_stages: list[EditorSessionStage] = []
        self._stage_names: set[str] = set()
        self._prepared = False
        self._closed = False

    @classmethod
    def build(
        cls,
        compose: Callable[[EditorSession], None],
        *,
        failure_injector: Callable[[str], None] | None = None,
        shutdown_engine: Callable[[], object] | None = None,
    ) -> EditorSession:
        """Compose a session and roll it back across the engine lifetime boundary."""
        session = cls(failure_injector=failure_injector)
        try:
            compose(session)
        except Exception:
            _logger.exception("Editor session initialization failed")
            session.prepare_engine_shutdown()
            if shutdown_engine is not None:
                try:
                    result = shutdown_engine()
                    if result is False:
                        _logger.error("EngineCore refused editor initialization rollback")
                except Exception:
                    _logger.exception("EngineCore shutdown failed during editor rollback")
            elif session._backend_stages:
                _logger.error(
                    "Editor rollback has post-engine stages but no engine shutdown callback"
                )
            session.close()
            raise
        return session

    @property
    def prepared(self) -> bool:
        return self._prepared

    @property
    def closed(self) -> bool:
        return self._closed

    def begin_stage(
        self,
        name: str,
        *,
        after_engine_shutdown: bool = False,
    ) -> EditorSessionStage:
        """Start an owned stage and expose its boundary for failure injection."""
        if self._closed:
            raise RuntimeError("editor session is closed")
        if self._prepared:
            raise RuntimeError("editor session is already prepared for engine shutdown")
        if name in self._stage_names:
            raise ValueError(f"editor session stage '{name}' already exists")

        stage = EditorSessionStage(name)
        self._stage_names.add(name)
        stages = self._backend_stages if after_engine_shutdown else self._engine_stages
        stages.append(stage)
        if self._failure_injector is not None:
            self._failure_injector(name)
        return stage

    def prepare_engine_shutdown(self) -> None:
        """Release loop/frontend consumers while the graphics device is still alive."""
        if self._prepared:
            return
        self._prepared = True

        stages = self._engine_stages
        self._engine_stages = []
        for stage in reversed(stages):
            stage.close()

    def close(self) -> None:
        """Release backend owners after EngineCore has completed shutdown."""
        if self._closed:
            return
        if not self._prepared:
            raise RuntimeError(
                "EditorSession.close() requires prepare_engine_shutdown() "
                "and EngineCore.shutdown() first"
            )
        self._closed = True

        stages = self._backend_stages
        self._backend_stages = []
        for stage in reversed(stages):
            stage.close()


__all__ = ["EditorSession", "EditorSessionStage"]
