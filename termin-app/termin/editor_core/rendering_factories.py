"""Toolkit-neutral rendering factory resolution and registration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any


_logger = logging.getLogger(__name__)


class PipelineAssetResolver:
    """Resolve serialized pipeline identifiers through the editor asset catalog."""

    def __init__(
        self,
        resource_manager: object,
        *,
        make_editor_pipeline: Callable[[], object] | None = None,
    ) -> None:
        self._resource_manager = resource_manager
        self._make_editor_pipeline = make_editor_pipeline

    def resolve(self, identifier: str) -> object | None:
        key = identifier.strip()
        if not key or key in ("Default", "(Default)"):
            return None
        if key == "(Editor)":
            if self._make_editor_pipeline is None:
                _logger.error("Cannot resolve editor pipeline: no editor pipeline factory is installed")
                return None
            return self._make_editor_pipeline()

        pipeline = None
        if "-" in key:
            pipeline = self._resource_manager.get_pipeline_by_uuid(key)
        if pipeline is None:
            pipeline = self._resource_manager.get_pipeline(key)
        if pipeline is None:
            _logger.error("Cannot resolve rendering pipeline asset '%s'", key)
        return pipeline


class RenderingFactoryRegistration:
    """Own RenderingManager display/pipeline callbacks as one lifecycle unit."""

    def __init__(
        self,
        manager: object,
        *,
        display_factory: Callable[[str], Any],
        pipeline_factory: Callable[[str], Any],
    ) -> None:
        self._manager = manager
        self._display_factory = display_factory
        self._pipeline_factory = pipeline_factory
        self._installed = False

    @property
    def installed(self) -> bool:
        return self._installed

    def install(self) -> None:
        if self._installed:
            return
        self._manager.set_display_factory(self._display_factory)
        try:
            self._manager.set_pipeline_factory(self._pipeline_factory)
        except Exception:
            _logger.exception("Rendering pipeline factory registration failed; rolling back")
            self._manager.set_display_factory(None)
            raise
        self._installed = True

    def close(self) -> None:
        if not self._installed:
            return
        first_error: BaseException | None = None
        try:
            self._manager.set_pipeline_factory(None)
        except Exception as error:
            _logger.exception("Rendering pipeline factory cleanup failed")
            first_error = error
        try:
            self._manager.set_display_factory(None)
        except Exception as error:
            _logger.exception("Rendering display factory cleanup failed")
            if first_error is None:
                first_error = error
        self._installed = False
        if first_error is not None:
            raise RuntimeError("rendering factory cleanup failed") from first_error


__all__ = ["PipelineAssetResolver", "RenderingFactoryRegistration"]
