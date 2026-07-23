"""Toolkit-neutral state and operations for the editor Modules panel."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from termin_modules import ModuleEvent, ModuleState


_logger = logging.getLogger(__name__)


def format_cleanup_phase(name: str) -> str:
    """Convert a binding enum name such as BackendFinish to backend-finish."""
    pieces: list[str] = []
    for character in name:
        if character.isupper() and pieces:
            pieces.append("-")
        pieces.append(character.lower())
    return "".join(pieces)


def module_recovery_hint(state: ModuleState, cleanup_phase=None) -> str | None:
    """Return the explicit user action for a non-active module failure."""
    if state == ModuleState.CleanupFailed:
        if cleanup_phase is None:
            raise ValueError("cleanup-failed module requires its cleanup phase")
        return (
            "run Unload to finish "
            f"{format_cleanup_phase(cleanup_phase.name)}, then load again"
        )
    if state == ModuleState.Failed:
        return "fix the module error, then load again"
    return None


@dataclass(frozen=True, slots=True)
class ModuleRow:
    module_id: str
    status: str
    details: str


@dataclass(frozen=True, slots=True)
class ModulesSnapshot:
    rows: tuple[ModuleRow, ...]
    status: str
    selected_module: str | None
    operation_running: bool
    operation_log: tuple[str, ...]


class ModulesPanelController:
    """Own module-panel state across direct caller and worker updates."""

    def __init__(
        self,
        runtime,
        *,
        progress_callback: Callable[[], None] | None = None,
    ) -> None:
        self.runtime = runtime
        self._progress_callback = progress_callback
        self._selected_module: str | None = None
        self._operation_running = False
        self._operation_message = ""
        self._operation_log: list[str] = []
        self._changed: Callable[[ModulesSnapshot], None] | None = None
        self._publishing = False
        self.runtime.add_listener(self._on_runtime_event)

    def set_changed_handler(
        self, handler: Callable[[ModulesSnapshot], None] | None
    ) -> None:
        self._changed = handler

    def close(self) -> None:
        self.runtime.remove_listener(self._on_runtime_event)
        self._changed = None

    def select(self, module_id: str | None) -> None:
        self._selected_module = module_id
        self._publish()

    def snapshot(self) -> ModulesSnapshot:
        if self._operation_running:
            return ModulesSnapshot(
                (),
                self._operation_message,
                self._selected_module,
                True,
                tuple(self._operation_log),
            )
        records = sorted(self.runtime.records(), key=lambda record: record.id)
        dirty = self.runtime.dirty_modules()
        stale = set(self.runtime.stale_modules())
        loaded = failed = changed = 0
        rows: list[ModuleRow] = []
        for record in records:
            if record.state == ModuleState.Loaded:
                loaded += 1
            elif record.state in (ModuleState.Failed, ModuleState.CleanupFailed):
                failed += 1
            flags: list[str] = []
            recovery = (
                module_recovery_hint(record.state, record.cleanup_phase)
                if record.state == ModuleState.CleanupFailed
                else module_recovery_hint(record.state)
            )
            if recovery is not None:
                flags.append(recovery)
            if record.id in dirty:
                flags.append("dirty")
            if record.id in stale:
                flags.append("stale")
            if flags:
                changed += 1
            details = record.kind.name.lower()
            if flags:
                details += f" ({', '.join(flags)})"
            status = (
                "cleanup-failed"
                if record.state == ModuleState.CleanupFailed
                else record.state.name.lower()
            )
            rows.append(ModuleRow(record.id, status, details))
        parts = []
        if loaded:
            parts.append(f"{loaded} loaded")
        if failed:
            parts.append(f"{failed} failed")
        if changed:
            parts.append(f"{changed} changed")
        return ModulesSnapshot(
            tuple(rows),
            ", ".join(parts) if parts else "No modules",
            self._selected_module,
            False,
            tuple(self._operation_log),
        )

    def rescan(self) -> bool:
        root = self.runtime.project_root
        if root is None:
            _logger.error("Modules rescan requires a configured project root")
            return False
        return self._run(
            f"Rescanning project: {root}",
            lambda: self.runtime.prepare_module_artifacts(project_root=root),
            lambda: self.runtime.load_project(root),
        )

    def reload_changed(self) -> bool:
        return self._run(
            "Reloading changed modules...",
            self.runtime.prepare_module_artifacts,
            self.runtime.reload_dirty_modules,
        )

    def build_reload_changed(self) -> bool:
        return self._run(
            "Building and reloading changed modules...",
            self.runtime.prepare_module_artifacts,
            self.runtime.prepare_changed_modules_for_play,
        )

    def reload_selected(self) -> bool:
        module_id = self._require_selection("reload")
        if module_id is None:
            return False
        return self._run(
            f"Reloading module '{module_id}'...",
            self.runtime.prepare_module_artifacts,
            lambda: self.runtime.reload_module(module_id),
        )

    def build_selected(self) -> bool:
        return self._artifact_operation("build")

    def clean_selected(self) -> bool:
        return self._artifact_operation("clean")

    def rebuild_selected(self) -> bool:
        module_id = self._require_selection("rebuild")
        if module_id is None:
            return False
        return self._run(
            f"Rebuilding module '{module_id}'...",
            lambda: self.runtime.prepare_module_artifacts(
                operation="rebuild", module_id=module_id
            ),
            lambda: self.runtime.unload_module(module_id),
        )

    def unload_selected(self) -> bool:
        module_id = self._require_selection("unload")
        if module_id is None:
            return False
        return self._run(
            f"Unloading module '{module_id}'...",
            None,
            lambda: self.runtime.unload_module(module_id),
        )

    def _artifact_operation(self, operation: str) -> bool:
        module_id = self._require_selection(operation)
        if module_id is None:
            return False
        return self._run(
            f"{operation.title()}ing module '{module_id}'...",
            lambda: self.runtime.prepare_module_artifacts(
                operation=operation, module_id=module_id
            ),
            None,
        )

    def _require_selection(self, operation: str) -> str | None:
        if self._selected_module is None:
            _logger.error("Modules %s requires a selected module", operation)
        return self._selected_module

    def _run(self, message: str, prepare_action, followup_action) -> bool:
        if self._operation_running:
            _logger.warning("Ignoring module operation while another operation is running")
            return False
        self._operation_running = True
        self._operation_message = message
        self._operation_log = [message]
        self._publish()

        def output(module_id: str, line: str) -> None:
            self._append_log(f"[{module_id}] {line}")

        success = True
        error = ""
        self.runtime.add_build_output_listener(output)
        try:
            if prepare_action is not None:
                success = bool(prepare_action())
            if success and followup_action is not None:
                success = bool(followup_action())
            if not success:
                error = self.runtime.last_error
        except Exception as exc:
            success = False
            error = str(exc)
            _logger.exception("Module operation failed")
        finally:
            try:
                self.runtime.remove_build_output_listener(output)
            except Exception:
                _logger.exception("Failed to remove module build output listener")
        self._finish(success, error)
        return success

    def _append_log(self, message: str) -> None:
        self._operation_log.append(message)
        self._publish()

    def _finish(self, success: bool, error: str) -> None:
        self._operation_log.append("Complete." if success else f"Failed: {error}")
        self._operation_running = False
        self._operation_message = ""
        self._publish()

    def _on_runtime_event(self, event: ModuleEvent) -> None:
        _logger.info("Module %s: %s", event.kind.name.lower(), event.module_id)
        if event.message:
            _logger.info("Module %s", event.message)
        if not self._operation_running:
            self._publish()

    def _publish(self) -> None:
        if self._changed is None or self._publishing:
            return
        self._publishing = True
        try:
            self._changed(self.snapshot())
        finally:
            self._publishing = False
        if self._progress_callback is not None:
            self._progress_callback()
