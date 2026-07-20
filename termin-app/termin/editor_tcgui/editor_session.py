"""Lifetime boundary for the legacy tcgui comparison frontend."""

from __future__ import annotations

from collections.abc import Callable


class TcguiEditorSession:
    """Own the tcgui loop connection and frontend teardown."""

    def __init__(
        self,
        loop_connection,
        prepare_engine_shutdown: Callable[[], None],
        close_backend: Callable[[], None],
    ) -> None:
        self._loop_connection = loop_connection
        self._prepare_engine_shutdown = prepare_engine_shutdown
        self._close_backend = close_backend
        self._prepared = False
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def prepared(self) -> bool:
        return self._prepared

    def prepare_engine_shutdown(self) -> None:
        if self._prepared:
            return
        self._prepared = True

        loop_connection = self._loop_connection
        self._loop_connection = None
        prepare = self._prepare_engine_shutdown
        self._prepare_engine_shutdown = None

        loop_connection.detach()
        prepare()

    def close(self) -> None:
        if self._closed:
            return
        if not self._prepared:
            raise RuntimeError(
                "TcguiEditorSession.close() requires prepare_engine_shutdown() "
                "and EngineCore.shutdown() first"
            )
        self._closed = True

        close_backend = self._close_backend
        self._close_backend = None
        close_backend()


__all__ = ["TcguiEditorSession"]
