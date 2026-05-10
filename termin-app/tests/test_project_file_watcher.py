from pathlib import Path
from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, ProjectFileWatcher


class RecordingPreLoader(FilePreLoader):
    def __init__(self) -> None:
        super().__init__(resource_manager=None)
        self.changed: list[str] = []

    @property
    def extensions(self) -> Set[str]:
        return {".shader"}

    @property
    def resource_type(self) -> str:
        return "shader"

    def on_file_changed(self, path: str) -> None:
        self.changed.append(path)


def test_project_file_watcher_poll_processes_pending_changes(tmp_path: Path) -> None:
    shader_path = tmp_path / "HotReload.shader"
    shader_path.write_text("@program HotReload\n", encoding="utf-8")

    processor = RecordingPreLoader()
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)

    with watcher._lock:
        watcher._pending_changes[str(shader_path)] = "modified"

    watcher.poll()

    assert processor.changed == [str(shader_path)]
