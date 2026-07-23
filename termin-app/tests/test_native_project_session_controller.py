from pathlib import Path
import threading

from termin.editor_native import project_session_controller as native_session
from termin.gui_native import Document, Rect


class _Widget:
    def __init__(self) -> None:
        self.widget = self
        self.handle = object()
        self.text = ""
        self.stable_id = ""
        self.preferred_size = None
        self.word_wrap = True
        self.placeholder = ""

    def add_fixed_child(self, *_args) -> None:
        pass

    def add_stretch_child(self, *_args) -> None:
        pass

    def set_layout_padding(self, *_args) -> None:
        pass

    def set_layout_spacing(self, *_args) -> None:
        pass


class _Progress(_Widget):
    def __init__(self, value: float) -> None:
        super().__init__()
        self.value = value


class _Dialog(_Widget):
    def __init__(self) -> None:
        super().__init__()
        self.actions = None
        self.content = None
        self.open = False

    def set_content(self, content) -> None:
        self.content = content

    def show(self, _viewport) -> bool:
        self.open = True
        return True

    def close(self) -> None:
        self.open = False


class _Document:
    def __init__(self) -> None:
        self.dialog = _Dialog()
        self.destroyed = []

    def create_vstack(self, _name):
        return _Widget()

    def create_label(self, text, _name):
        label = _Widget()
        label.text = text
        return label

    def create_progress_bar(self, value):
        return _Progress(value)

    def create_rich_text_view(self, _model):
        return _Widget()

    def create_dialog(self, _title):
        return self.dialog

    def ref(self, handle):
        return handle

    def is_alive(self, handle) -> bool:
        return handle is self.dialog.handle

    def destroy_widget_recursive(self, handle) -> bool:
        self.destroyed.append(handle)
        return True


class _RichTextModel:
    def __init__(self) -> None:
        self.text = ""

    def set_text(self, text: str) -> None:
        self.text = text


class _Runtime:
    last_error = ""

    def __init__(self) -> None:
        self.output_listeners = []

    def add_build_output_listener(self, callback) -> None:
        self.output_listeners.append(callback)

    def remove_build_output_listener(self, callback) -> None:
        self.output_listeners.remove(callback)


def test_native_module_operation_runs_synchronously_and_refreshes_progress(monkeypatch):
    monkeypatch.setattr(native_session, "RichTextModel", _RichTextModel)
    document = _Document()
    renders = []
    completions = []
    action_threads = []
    caller_thread = threading.get_ident()

    def complete(success: bool) -> None:
        assert document.destroyed == [document.dialog.handle]
        completions.append(success)

    operation = native_session.NativeModuleOperationDialog(
        document,
        viewport=lambda: object(),
        refresh_ui=lambda: renders.append(True),
        runtime=_Runtime(),
        title="Load Project Modules",
        start_message="Loading project modules: test-project",
        prepare_action=lambda: action_threads.append(threading.get_ident()) or True,
        followup_action=lambda: action_threads.append(threading.get_ident()) or True,
        on_complete=complete,
    )

    operation.start()

    assert action_threads == [caller_thread, caller_thread]
    assert completions == [True]
    assert operation.log_model.text == "Complete."
    assert document.destroyed == [document.dialog.handle]
    assert renders


def test_native_module_operation_updates_real_native_label_binding():
    document = Document()
    operation = native_session.NativeModuleOperationDialog(
        document,
        viewport=lambda: Rect(0.0, 0.0, 640.0, 480.0),
        refresh_ui=lambda: None,
        runtime=_Runtime(),
        title="Load Project Modules",
        start_message="Loading project modules: test-project",
        prepare_action=None,
        followup_action=lambda: True,
        on_complete=lambda _success: None,
    )

    operation._append_log("[module] Preparing build")

    assert operation.current_line.text == "[module] Preparing build"
    assert operation.log_model.text == "[module] Preparing build"
    operation.close()


def test_native_project_session_controller_configures_startup_operation(monkeypatch, tmp_path):
    captured = {}

    class _Operation:
        def __init__(self, _document, **kwargs) -> None:
            captured.update(kwargs)

        def start(self) -> None:
            captured["on_complete"](True)

        def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(native_session, "NativeModuleOperationDialog", _Operation)
    controller = native_session.NativeProjectSessionController(
        document=object(),
        viewport=lambda: object(),
        refresh_ui=lambda: None,
        set_project_state=lambda *_args: None,
        log_to_console=lambda _message: None,
        rescan_file_resources=lambda: None,
        set_project_browser_root=lambda _path: None,
        get_init_script_editor=lambda: None,
        resolve_termin_shaderc=lambda: None,
        resolve_slangc=lambda: None,
        get_render_engine=lambda: object(),
    )
    runtime = _Runtime()
    runtime.prepare_module_artifacts = lambda *, project_root: project_root == tmp_path
    runtime.load_project = lambda project_root: project_root == tmp_path
    completions = []

    controller._run_module_operation(runtime, Path(tmp_path), completions.append)

    assert captured["title"] == "Load Project Modules"
    assert captured["start_message"] == f"Loading project modules: {tmp_path.name}"
    assert captured["prepare_action"]()
    assert captured["followup_action"]()
    assert completions == [True]
    assert controller.active_module_operation is None
