from pathlib import Path
from typing import Set

from termin_assets import project_file_watcher as watcher_module
from termin_assets.project_file_watcher import FilePreLoader, ProjectFileWatcher


class RecordingRemovalPreLoader(FilePreLoader):
    def __init__(self, fail_on: set[str] | None = None) -> None:
        super().__init__(resource_manager=None)
        self.fail_on = fail_on or set()
        self.removed: list[str] = []

    @property
    def extensions(self) -> Set[str]:
        return {".asset"}

    @property
    def resource_type(self) -> str:
        return "asset"

    def on_file_removed(self, path: str) -> None:
        self.removed.append(path)
        if Path(path).name in self.fail_on:
            raise RuntimeError(f"failed to remove {path}")


def _queue_change(watcher: ProjectFileWatcher, path: Path, kind: str) -> None:
    with watcher._lock:
        watcher._pending_changes[str(path)] = kind


def test_poll_logs_failed_remove_and_processes_later_deletions(tmp_path: Path, monkeypatch) -> None:
    first_path = tmp_path / "first.asset"
    second_path = tmp_path / "second.asset"
    log_messages: list[str] = []

    monkeypatch.setattr(watcher_module.log, "exception", log_messages.append)

    processor = RecordingRemovalPreLoader(fail_on={"first.asset"})
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)
    watcher._watched_files.update({str(first_path), str(second_path)})
    _queue_change(watcher, first_path, "deleted")
    _queue_change(watcher, second_path, "deleted")

    watcher.poll()

    assert processor.removed == [str(first_path), str(second_path)]
    assert watcher.watched_files == set()
    assert log_messages == [f"[ProjectFileWatcher] Error removing {first_path}"]


def test_rescan_logs_failed_remove_and_processes_later_removed_files(tmp_path: Path, monkeypatch) -> None:
    first_path = tmp_path / "first.asset"
    second_path = tmp_path / "second.asset"
    log_messages: list[str] = []

    monkeypatch.setattr(watcher_module.log, "exception", log_messages.append)

    processor = RecordingRemovalPreLoader(fail_on={"first.asset"})
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)
    watcher._project_path = str(tmp_path)
    watcher._watched_files.update({str(first_path), str(second_path)})

    watcher.rescan()

    assert processor.removed == [str(first_path), str(second_path)]
    assert watcher.watched_files == set()
    assert log_messages == [f"[ProjectFileWatcher] Error removing {first_path}"]
