from termin.editor_tcgui.project_browser import ProjectBrowserTcgui, _get_file_subtitle


class _DummyUi:
    def __init__(self) -> None:
        self.clipboard_text = ""

    def set_clipboard_text(self, text: str) -> None:
        self.clipboard_text = text


class _DummyWidget:
    def __init__(self, ui) -> None:
        self._ui = ui


def test_project_browser_copy_absolute_path_uses_ui_clipboard(tmp_path):
    target = tmp_path / "assets" / "scene.scene"
    ui = _DummyUi()
    browser = ProjectBrowserTcgui.__new__(ProjectBrowserTcgui)
    browser._file_list = _DummyWidget(ui)
    browser._dir_tree = _DummyWidget(None)

    browser._copy_absolute_path(target)

    assert ui.clipboard_text == str(target.resolve(strict=False))


def test_project_browser_labels_stl_as_mesh(tmp_path):
    assert _get_file_subtitle(tmp_path / "piece.stl") == "Mesh"
