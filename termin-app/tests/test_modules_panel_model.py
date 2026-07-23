from types import SimpleNamespace

from termin.editor_core.modules_panel_model import ModulesPanelController
from termin_modules import (
    ModuleCleanupPhase,
    ModuleEventKind,
    ModuleKind,
    ModuleState,
)


class _Runtime:
    def __init__(self) -> None:
        self.project_root = "/project"
        self.last_error = ""
        self.listeners = []
        self.output_listeners = []
        self.calls = []

    def add_listener(self, callback) -> None:
        self.listeners.append(callback)

    def remove_listener(self, callback) -> None:
        self.listeners.remove(callback)

    def add_build_output_listener(self, callback) -> None:
        self.output_listeners.append(callback)

    def remove_build_output_listener(self, callback) -> None:
        self.output_listeners.remove(callback)

    def records(self):
        return [SimpleNamespace(id="core", kind=ModuleKind.Cpp, state=ModuleState.Loaded)]

    def dirty_modules(self):
        return {"core": ("source",)}

    def stale_modules(self):
        return []

    def prepare_module_artifacts(self, **kwargs) -> bool:
        self.calls.append(("prepare", kwargs))
        for callback in tuple(self.output_listeners):
            callback("core", "built")
        return True

    def reload_module(self, module_id: str) -> bool:
        self.calls.append(("reload", module_id))
        return True


def test_modules_panel_snapshot_and_synchronous_reload_are_toolkit_neutral() -> None:
    runtime = _Runtime()
    snapshots = []
    controller = ModulesPanelController(runtime)
    controller.set_changed_handler(snapshots.append)

    snapshot = controller.snapshot()
    assert snapshot.status == "1 loaded, 1 changed"
    assert snapshot.rows[0].details == "cpp (dirty)"

    controller.select("core")
    assert controller.reload_selected()

    assert runtime.calls == [("prepare", {}), ("reload", "core")]
    assert not controller.snapshot().operation_running
    assert controller.snapshot().operation_log[-1] == "Complete."
    assert snapshots
    controller.close()
    assert runtime.listeners == []


def test_modules_panel_discovery_snapshot_suppresses_reentrant_failure() -> None:
    runtime = _Runtime()
    stale_calls = 0

    def stale_modules():
        nonlocal stale_calls
        stale_calls += 1
        event = SimpleNamespace(
            kind=ModuleEventKind.Failed,
            module_id="core",
            message="descriptor snapshot rejected",
        )
        for listener in tuple(runtime.listeners):
            listener(event)
        return []

    runtime.stale_modules = stale_modules
    snapshots = []
    controller = ModulesPanelController(runtime)
    controller.set_changed_handler(snapshots.append)

    discovered = SimpleNamespace(
        kind=ModuleEventKind.Discovered,
        module_id="core",
        message="",
    )
    runtime.listeners[0](discovered)

    assert stale_calls == 1
    assert len(snapshots) == 1
    assert snapshots[0].selected_module is None
    controller.close()


def test_modules_panel_rejects_selection_operation_without_selection() -> None:
    runtime = _Runtime()
    controller = ModulesPanelController(runtime)

    assert not controller.build_selected()
    assert runtime.calls == []

    controller.close()


def test_modules_panel_exposes_retryable_cleanup_phase() -> None:
    runtime = _Runtime()
    runtime.records = lambda: [
        SimpleNamespace(
            id="core",
            kind=ModuleKind.Cpp,
            state=ModuleState.CleanupFailed,
            cleanup_phase=ModuleCleanupPhase.RevokeContributions,
        )
    ]
    controller = ModulesPanelController(runtime)

    snapshot = controller.snapshot()

    assert snapshot.status == "1 failed, 1 changed"
    assert snapshot.rows[0].status == "cleanup-failed"
    assert snapshot.rows[0].details == (
        "cpp (run Unload to finish revoke-contributions, then load again, dirty)"
    )
    controller.close()


def test_modules_panel_exposes_failed_reload_recovery_action() -> None:
    runtime = _Runtime()
    runtime.records = lambda: [
        SimpleNamespace(
            id="core",
            kind=ModuleKind.Cpp,
            state=ModuleState.Failed,
            cleanup_phase=ModuleCleanupPhase.None_,
        )
    ]
    runtime.dirty_modules = lambda: set()
    controller = ModulesPanelController(runtime)

    snapshot = controller.snapshot()

    assert snapshot.rows[0].status == "failed"
    assert snapshot.rows[0].details == "cpp (fix the module error, then load again)"
    controller.close()
