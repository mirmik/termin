from types import SimpleNamespace

from termin.editor_core import modules_panel_model as model_module
from termin.editor_core.modules_panel_model import ModulesPanelController
from termin_modules import ModuleCleanupPhase, ModuleKind, ModuleState


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


class _ImmediateThread:
    def __init__(self, *, target, name, daemon) -> None:
        assert name == "EditorModulesOperation"
        assert not daemon
        self.target = target

    def start(self) -> None:
        self.target()


def test_modules_panel_snapshot_and_async_reload_are_toolkit_neutral(monkeypatch) -> None:
    monkeypatch.setattr(model_module.threading, "Thread", _ImmediateThread)
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
