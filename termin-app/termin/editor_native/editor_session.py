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
    """Own dependency-ordered native editor initialization stages."""

    def __init__(
        self,
        *,
        failure_injector: Callable[[str], None] | None = None,
    ) -> None:
        self._failure_injector = failure_injector
        self._stages: list[EditorSessionStage] = []
        self._closed = False

    @classmethod
    def build(
        cls,
        compose: Callable[[EditorSession], None],
        *,
        failure_injector: Callable[[str], None] | None = None,
    ) -> EditorSession:
        """Compose a session and roll back every owned stage on failure."""
        session = cls(failure_injector=failure_injector)
        try:
            compose(session)
        except Exception:
            _logger.exception("Editor session initialization failed")
            session.close()
            raise
        return session

    @property
    def closed(self) -> bool:
        return self._closed

    def begin_stage(self, name: str) -> EditorSessionStage:
        """Start an owned stage and expose its boundary for failure injection."""
        if self._closed:
            raise RuntimeError("editor session is closed")
        if any(stage.name == name for stage in self._stages):
            raise ValueError(f"editor session stage '{name}' already exists")

        stage = EditorSessionStage(name)
        self._stages.append(stage)
        if self._failure_injector is not None:
            self._failure_injector(name)
        return stage

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        stages = self._stages
        self._stages = []
        for stage in reversed(stages):
            stage.close()


__all__ = ["EditorSession", "EditorSessionStage"]
