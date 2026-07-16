"""Scoped ownership of the editor's primary render-scene attachment."""

from __future__ import annotations

import logging


_logger = logging.getLogger(__name__)


class PrimaryRenderSceneBinding:
    """Atomically rebind one owned render attachment without touching others."""

    def __init__(self, connector, scene_name: str) -> None:
        if not scene_name:
            raise ValueError("primary render scene name must not be empty")
        self._connector = connector
        self._scene_name = scene_name
        self._uncertain_scene_names: set[str] = set()

    @property
    def scene_name(self) -> str:
        return self._scene_name

    def may_reference(self, scene_name: str) -> bool:
        return (
            self._scene_name == scene_name
            or scene_name in self._uncertain_scene_names
        )

    def sync_current(self) -> None:
        result = self._connector.sync_scene_render_state(self._scene_name)
        _require_success(result, f"sync render scene '{self._scene_name}'")

    def rebind(self, new_scene_name: str) -> bool:
        if not new_scene_name:
            raise ValueError("new primary render scene name must not be empty")
        old_scene_name = self._scene_name
        if new_scene_name == old_scene_name:
            return False
        if self._uncertain_scene_names:
            raise RuntimeError(
                "cannot rebind a primary render scene after an incomplete rollback"
            )

        result = self._connector.attach_scene_to_render(new_scene_name)
        _require_success(result, f"attach render scene '{new_scene_name}'")

        try:
            result = self._connector.detach_scene_from_render(
                old_scene_name,
                save_state=False,
            )
            _require_success(result, f"detach render scene '{old_scene_name}'")
        except Exception as transition_error:
            rollback_errors = self._restore_after_failed_rebind(
                old_scene_name,
                new_scene_name,
            )
            if rollback_errors:
                self._uncertain_scene_names.update(
                    (old_scene_name, new_scene_name)
                )
                details = "; ".join(str(error) for error in rollback_errors)
                raise RuntimeError(
                    "primary render scene rollback failed after transition error: "
                    f"{details}"
                ) from transition_error
            raise

        self._scene_name = new_scene_name
        return True

    def _restore_after_failed_rebind(
        self,
        old_scene_name: str,
        new_scene_name: str,
    ) -> list[Exception]:
        errors: list[Exception] = []
        try:
            result = self._connector.attach_scene_to_render(old_scene_name)
            _require_success(result, f"restore render scene '{old_scene_name}'")
        except Exception as error:
            _logger.exception(
                "Primary render binding failed to restore scene '%s'",
                old_scene_name,
            )
            errors.append(error)

        try:
            result = self._connector.detach_scene_from_render(
                new_scene_name,
                save_state=False,
            )
            _require_success(result, f"detach candidate render scene '{new_scene_name}'")
        except Exception as error:
            _logger.exception(
                "Primary render binding failed to detach candidate scene '%s'",
                new_scene_name,
            )
            errors.append(error)
        return errors


def _require_success(result, operation: str) -> None:
    if result is False:
        raise RuntimeError(f"failed to {operation}")


__all__ = ["PrimaryRenderSceneBinding"]
