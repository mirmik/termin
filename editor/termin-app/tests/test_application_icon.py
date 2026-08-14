from pathlib import Path

from termin.editor_core.application_icon import apply_editor_window_icon, editor_icon_path


class _RecordingWindow:
    def __init__(self) -> None:
        self.icon_path: str | None = None

    def set_icon_bmp(self, path: str) -> None:
        self.icon_path = path


def test_editor_icon_is_packaged_and_applied() -> None:
    window = _RecordingWindow()

    assert apply_editor_window_icon(window)
    assert window.icon_path == str(editor_icon_path())
    assert Path(window.icon_path).is_file()
    assert Path(window.icon_path).suffix == ".bmp"
