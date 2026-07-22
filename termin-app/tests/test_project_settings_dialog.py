from pathlib import Path

from termin.project.settings import ProjectPlayerWindowSettings, ProjectSettings, ProjectSettingsManager
from termin.editor_tcgui.dialogs import project_settings_dialog as dialog_module


class _FakeWidget:
    def __init__(self) -> None:
        self.children = []
        self.text = ""
        self.tooltip = ""
        self.spacing = 0
        self.preferred_width = 0
        self.preferred_height = 0
        self.word_wrap = True
        self.placeholder = ""
        self.stretch = False

    def add_child(self, child) -> None:
        self.children.append(child)


class _FakeComboBox(_FakeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.items = []
        self.selected_index = 0
        self.on_changed = None


class _FakeCheckbox(_FakeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.checked = False
        self.on_changed = None


class _FakeSpinBox(_FakeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.value = 0
        self.min_value = 0
        self.max_value = 0
        self.step = 0
        self.decimals = 0
        self.on_changed = None


class _FakeTextInput(_FakeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.on_submit = None


class _FakeTextArea(_FakeWidget):
    pass


class _FakeDialog(_FakeWidget):
    last = None

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.content = None
        self.buttons = []
        self.default_button = ""
        self.cancel_button = ""
        self.on_result = None
        self.min_width = 0

    def show(self, ui, windowed: bool = False) -> None:
        self.ui = ui
        self.windowed = windowed
        _FakeDialog.last = self


def _walk(widget):
    yield widget
    for child in getattr(widget, "children", []):
        yield from _walk(child)


def _find_widget(root, cls, *, text: str):
    for widget in _walk(root):
        if isinstance(widget, cls) and getattr(widget, "text", None) == text:
            return widget
    raise AssertionError(f"widget not found: {cls.__name__} text={text!r}")


def _install_fake_widgets(monkeypatch) -> None:
    monkeypatch.setattr(dialog_module, "Dialog", _FakeDialog)
    monkeypatch.setattr(dialog_module, "VStack", _FakeWidget)
    monkeypatch.setattr(dialog_module, "HStack", _FakeWidget)
    monkeypatch.setattr(dialog_module, "Label", _FakeWidget)
    monkeypatch.setattr(dialog_module, "ComboBox", _FakeComboBox)
    monkeypatch.setattr(dialog_module, "Checkbox", _FakeCheckbox)
    monkeypatch.setattr(dialog_module, "SpinBox", _FakeSpinBox)
    monkeypatch.setattr(dialog_module, "TextInput", _FakeTextInput)
    monkeypatch.setattr(dialog_module, "TextArea", _FakeTextArea)
    monkeypatch.setattr(dialog_module, "px", lambda value: value)


def _install_settings_manager(monkeypatch, tmp_path: Path) -> ProjectSettingsManager:
    manager = ProjectSettingsManager()
    manager.set_project_path(tmp_path)
    manager._settings = ProjectSettings(
        player_window=ProjectPlayerWindowSettings(
            width=1600,
            height=900,
            fullscreen=True,
            vsync=True,
        ),
    )
    monkeypatch.setattr(ProjectSettingsManager, "_instance", manager)
    return manager


def test_project_settings_dialog_player_window_does_not_rescan_resources(monkeypatch, tmp_path: Path) -> None:
    _install_fake_widgets(monkeypatch)
    manager = _install_settings_manager(monkeypatch, tmp_path)
    resource_callbacks = []
    render_callbacks = []

    dialog_module.show_project_settings_dialog(
        object(),
        on_resource_settings_changed=lambda: resource_callbacks.append("resource"),
        on_render_settings_changed=lambda: render_callbacks.append("render"),
    )

    dialog = _FakeDialog.last
    assert dialog is not None
    fullscreen = _find_widget(dialog.content, _FakeCheckbox, text="Fullscreen")
    vsync = _find_widget(dialog.content, _FakeCheckbox, text="VSync")

    fullscreen.checked = False
    fullscreen.on_changed(False)
    vsync.checked = False
    vsync.on_changed(False)
    dialog.on_result("Close")

    assert manager.settings.player_window == ProjectPlayerWindowSettings(
        width=1600,
        height=900,
        fullscreen=False,
        vsync=False,
    )
    assert resource_callbacks == []
    assert render_callbacks == []
