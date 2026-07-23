import sys
import threading
import time
from types import SimpleNamespace

import termin.project_modules.runtime as project_modules_runtime
from termin.editor_tcgui.dialogs import module_operation_dialog
from termin.editor_tcgui import modules_panel as modules_panel_module
from termin.editor_tcgui.modules_panel import ModulesPanel
from termin.editor_tcgui.editor_window import EditorWindowTcgui
from termin_modules import CppModuleBackend, ModuleEnvironment, ModuleKind, ModuleRuntime, ModuleState


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
        self.artifact_calls: list[tuple[str, str | None]] = []
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

    def prepare_module_artifacts(
        self,
        *,
        operation: str = "warmup",
        module_id: str | None = None,
        project_root=None,
    ) -> bool:
        del project_root
        self.artifact_calls.append((operation, module_id))
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

    def fake_dialog(
        ui,
        runtime_arg,
        *,
        title,
        start_message,
        prepare_action=None,
        followup_action=None,
        on_complete,
    ) -> None:
        dialog_calls.append((ui, runtime_arg, title, start_message))
        assert panel._operation_running
        assert all(not button.enabled for button in panel._operation_buttons)
        success = prepare_action() if prepare_action is not None else True
        if success and followup_action is not None:
            success = followup_action()
        on_complete(success)

    monkeypatch.setattr(modules_panel_module, "show_module_operation_dialog", fake_dialog)

    panel._on_build_clicked()

    assert runtime.build_calls == []
    assert runtime.artifact_calls == [("build", "native_core")]
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

    class FakeUi:
        pass

    def action() -> bool:
        for listener in list(runtime._build_output_listeners):
            listener("native_core", "building")
        return True

    runtime._build_output_listeners = []
    runtime.add_build_output_listener = runtime._build_output_listeners.append
    runtime.remove_build_output_listener = runtime._build_output_listeners.remove
    monkeypatch.setattr(module_operation_dialog, "Dialog", FakeDialog)

    module_operation_dialog.show_module_operation_dialog(
        FakeUi(),
        runtime,
        title="Build Module",
        start_message="Building...",
        prepare_action=action,
        on_complete=completed.append,
    )

    assert shown == [False]
    assert closed == [True]
    assert completed == [True]
    assert runtime._build_output_listeners == []


def test_module_operation_dialog_runs_prepare_and_followup_on_calling_thread(monkeypatch) -> None:
    runtime = FakeModulesRuntime()
    runtime._build_output_listeners = []
    runtime.add_build_output_listener = runtime._build_output_listeners.append
    runtime.remove_build_output_listener = runtime._build_output_listeners.remove
    calling_thread = threading.get_ident()
    prepare_threads: list[int] = []
    followup_threads: list[int] = []
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
            del ui, windowed

        def close(self) -> None:
            pass

    class FakeUi:
        pass

    ui = FakeUi()
    monkeypatch.setattr(module_operation_dialog, "Dialog", FakeDialog)

    def prepare() -> bool:
        prepare_threads.append(threading.get_ident())
        return True

    module_operation_dialog.show_module_operation_dialog(
        ui,
        runtime,
        title="Synchronous operation",
        start_message="Building...",
        prepare_action=prepare,
        followup_action=lambda: followup_threads.append(threading.get_ident()) is None,
        on_complete=completed.append,
    )

    assert completed == [True]
    assert prepare_threads == [calling_thread]
    assert followup_threads == [calling_thread]


def test_native_module_build_releases_gil_while_waiting_for_command(tmp_path) -> None:
    build_script = tmp_path / "slow_build.py"
    build_script.write_text("import time\ntime.sleep(0.4)\n", encoding="utf-8")

    descriptor = tmp_path / "slow.module"
    command = f"{sys.executable} {build_script}"
    descriptor.write_text(
        "name: slow\n"
        "build:\n"
        f"  command: {command}\n"
        "  output: unused.so\n",
        encoding="utf-8",
    )

    runtime = ModuleRuntime()
    runtime.set_environment(ModuleEnvironment())
    runtime.register_cpp_backend(CppModuleBackend())
    runtime.discover(tmp_path)

    ticks = 0
    stop = False

    def ticker() -> None:
        nonlocal ticks
        while not stop:
            ticks += 1
            time.sleep(0.01)

    thread = threading.Thread(target=ticker)
    thread.start()
    try:
        ticks = 0
        assert runtime.build_module("slow")
    finally:
        stop = True
        thread.join(timeout=1.0)

    assert ticks > 5


def test_play_gate_prebuilds_changed_modules_before_toggle(monkeypatch) -> None:
    calls: list[str] = []

    class FakeGameModeModel:
        is_game_mode = False

        def toggle_game_mode(self) -> None:
            calls.append("toggle")

    class FakeRuntime:
        last_error = ""

        def changed_modules(self) -> list[str]:
            return ["native_core"]

        def prepare_module_artifacts(self) -> bool:
            calls.append("build")
            return True

    runtime = FakeRuntime()
    monkeypatch.setattr(project_modules_runtime, "get_project_modules_runtime", lambda: runtime)

    from termin.editor_tcgui.dialogs import module_operation_dialog

    def fake_dialog(
        ui,
        runtime_arg,
        *,
        prepare_action,
        followup_action,
        on_complete,
        **_kwargs,
    ) -> None:
        del ui
        assert runtime_arg is runtime
        success = prepare_action()
        if success:
            calls.append("followup")
            success = followup_action()
        on_complete(success)

    monkeypatch.setattr(module_operation_dialog, "show_module_operation_dialog", fake_dialog)

    editor = EditorWindowTcgui.__new__(EditorWindowTcgui)
    editor._game_mode_model = FakeGameModeModel()
    editor._play_prepare_running = False
    editor._ui = object()

    editor._toggle_game_mode()

    assert calls == ["build", "followup", "toggle"]
    assert not editor._play_prepare_running
