from types import SimpleNamespace

from termin.editor_tcgui.dialogs import module_operation_dialog
from termin.editor_tcgui import modules_panel as modules_panel_module
from termin.editor_tcgui.modules_panel import ModulesPanel
from termin_modules import ModuleKind, ModuleState


class FakeUi:
    def __init__(self) -> None:
        self.layout_requests = 0

    def request_layout(self) -> None:
        self.layout_requests += 1


class FakeModulesRuntime:
    def __init__(self) -> None:
        self.project_root = None
        self.last_error = ""
        self.listeners = []
        self.build_calls: list[str] = []
        self.records_read_count = 0

    def add_listener(self, listener) -> None:
        self.listeners.append(listener)

    def records(self) -> list[object]:
        self.records_read_count += 1
        return [
            SimpleNamespace(
                id="native_core",
                kind=ModuleKind.Cpp,
                state=ModuleState.Loaded,
            )
        ]

    def dirty_modules(self) -> dict[str, tuple[str, ...]]:
        return {}

    def stale_modules(self) -> list[str]:
        return []

    def build_module(self, module_id: str) -> bool:
        self.build_calls.append(module_id)
        return True


class RuntimeThatFailsWhenRead(FakeModulesRuntime):
    def records(self) -> list[object]:
        raise AssertionError("runtime records must not be read while an operation is running")


def test_modules_panel_build_module_uses_progress_dialog(monkeypatch) -> None:
    runtime = FakeModulesRuntime()
    monkeypatch.setattr(modules_panel_module, "get_project_modules_runtime", lambda: runtime)

    panel = ModulesPanel()
    panel._ui = FakeUi()
    panel._selected_module = "native_core"
    dialog_calls = []

    def fake_dialog(ui, runtime_arg, *, title, start_message, action, on_complete) -> None:
        dialog_calls.append((ui, runtime_arg, title, start_message))
        assert panel._operation_running
        assert all(not button.enabled for button in panel._operation_buttons)
        on_complete(action())

    monkeypatch.setattr(modules_panel_module, "show_module_operation_dialog", fake_dialog)

    panel._on_build_clicked()

    assert runtime.build_calls == ["native_core"]
    assert dialog_calls == [
        (
            panel._ui,
            runtime,
            "Build Module: native_core",
            "Building module 'native_core'...",
        )
    ]
    assert not panel._operation_running
    assert all(button.enabled for button in panel._operation_buttons)
    assert panel._status_label.text == "1 loaded"


def test_modules_panel_update_display_skips_runtime_read_while_busy(monkeypatch) -> None:
    runtime = RuntimeThatFailsWhenRead()
    monkeypatch.setattr(modules_panel_module, "get_project_modules_runtime", lambda: runtime)

    panel = ModulesPanel()
    panel._operation_running = True
    panel._operation_message = "Building module 'native_core'..."

    panel.update_display()

    assert panel._status_label.text == "Building module 'native_core'..."


def test_module_operation_dialog_uses_overlay_and_closes_on_completion(monkeypatch) -> None:
    runtime = FakeModulesRuntime()
    shown: list[bool] = []
    closed: list[bool] = []
    completed: list[bool] = []

    class FakeDialog:
        def __init__(self) -> None:
            self.title = ""
            self.content = None
            self.buttons = []
            self.default_button = None
            self.cancel_button = None
            self.min_width = 0

        def show(self, ui, windowed: bool = False) -> None:
            shown.append(windowed)

        def close(self) -> None:
            closed.append(True)

    class FakeThread:
        def __init__(self, *, target, name: str, daemon: bool) -> None:
            self._target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            self._target()

    class FakeDeferredUi:
        def defer(self, callback) -> None:
            callback()

    def action() -> bool:
        for listener in list(runtime._build_output_listeners):
            listener("native_core", "building")
        return True

    runtime._build_output_listeners = []
    runtime.add_build_output_listener = runtime._build_output_listeners.append
    runtime.remove_build_output_listener = runtime._build_output_listeners.remove
    monkeypatch.setattr(module_operation_dialog, "Dialog", FakeDialog)
    monkeypatch.setattr(module_operation_dialog.threading, "Thread", FakeThread)

    module_operation_dialog.show_module_operation_dialog(
        FakeDeferredUi(),
        runtime,
        title="Build Module",
        start_message="Building...",
        action=action,
        on_complete=completed.append,
    )

    assert shown == [False]
    assert closed == [True]
    assert completed == [True]
    assert runtime._build_output_listeners == []
