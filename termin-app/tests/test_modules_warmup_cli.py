from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import termin.module_warmup as warmup


@dataclass
class _State:
    name: str


@dataclass
class _Kind:
    name: str


@dataclass
class _Record:
    id: str
    state: _State
    kind: _Kind
    descriptor_path: str
    error_message: str = ""
    diagnostics: str = ""


class _FakeRuntime:
    def __init__(self, records: list[_Record] | None = None) -> None:
        self.last_error = ""
        self.loaded_project: Path | None = None
        self.discovered_project: Path | None = None
        self.loaded_modules: list[str] = []
        self.load_project_result = True
        self.discover_project_result = True
        self.load_module_results: dict[str, bool] = {}
        self.sync_live_scenes = True
        self.sync_live_scenes_updates: list[bool] = []
        self._records = records if records is not None else []

    def records(self) -> list[_Record]:
        return list(self._records)

    def load_project(self, project_root: Path) -> bool:
        self.loaded_project = project_root
        return self.load_project_result

    def discover_project(self, project_root: Path) -> bool:
        self.discovered_project = project_root
        return self.discover_project_result

    def find(self, module_id: str) -> _Record | None:
        for record in self._records:
            if record.id == module_id:
                return record
        return None

    def load_module(self, module_id: str) -> bool:
        self.loaded_modules.append(module_id)
        return self.load_module_results.get(module_id, True)

    def set_sync_live_scenes(self, enabled: bool) -> None:
        self.sync_live_scenes = enabled
        self.sync_live_scenes_updates.append(enabled)


def _write_project(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "Game.terminproj").write_text("{}", encoding="utf-8")


def _record(module_id: str, state: str = "Loaded") -> _Record:
    return _Record(
        id=module_id,
        state=_State(state),
        kind=_Kind("Python"),
        descriptor_path=f"{module_id}.pymodule",
    )


def test_resolve_project_root_accepts_nested_path(tmp_path: Path) -> None:
    _write_project(tmp_path)
    nested = tmp_path / "scripts" / "gameplay"
    nested.mkdir(parents=True)

    assert warmup.resolve_project_root(nested) == tmp_path


def test_warmup_project_modules_loads_whole_project(tmp_path: Path) -> None:
    _write_project(tmp_path)
    runtime = _FakeRuntime([_record("gameplay")])

    result = warmup.warmup_project_modules(tmp_path, runtime=runtime)

    assert result.success
    assert runtime.loaded_project == tmp_path
    assert runtime.loaded_modules == []


def test_warmup_project_modules_loads_selected_modules(tmp_path: Path) -> None:
    _write_project(tmp_path)
    runtime = _FakeRuntime([_record("gameplay"), _record("ui")])

    result = warmup.warmup_project_modules(
        tmp_path,
        module_ids=("gameplay",),
        runtime=runtime,
    )

    assert result.success
    assert runtime.discovered_project == tmp_path
    assert runtime.loaded_project is None
    assert runtime.loaded_modules == ["gameplay"]


def test_warmup_project_modules_fails_on_failed_record(tmp_path: Path) -> None:
    _write_project(tmp_path)
    runtime = _FakeRuntime([_record("gameplay", "Failed")])

    result = warmup.warmup_project_modules(tmp_path, runtime=runtime)

    assert not result.success
    assert result.failed_modules == ("gameplay",)


def test_warmup_project_modules_disables_live_scene_sync(monkeypatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    runtime = _FakeRuntime([_record("gameplay")])

    def runtime_provider() -> _FakeRuntime:
        return runtime

    monkeypatch.setattr(warmup, "_project_modules_runtime", runtime_provider)

    result = warmup.warmup_project_modules(tmp_path)

    assert result.success
    assert runtime.sync_live_scenes
    assert runtime.sync_live_scenes_updates == [False, True]


def test_main_accepts_default_warmup_command(monkeypatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    runtime = _FakeRuntime([_record("gameplay")])
    monkeypatch.setattr(warmup, "_project_modules_runtime", lambda: runtime)

    assert warmup.main(["--project", str(tmp_path), "--quiet"]) == 0
    assert runtime.loaded_project == tmp_path


def test_main_returns_error_for_unknown_selected_module(monkeypatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    runtime = _FakeRuntime([_record("gameplay")])
    monkeypatch.setattr(warmup, "_project_modules_runtime", lambda: runtime)

    assert warmup.main(["warmup", str(tmp_path), "--module", "missing", "--quiet"]) == 1
    assert runtime.loaded_modules == []
