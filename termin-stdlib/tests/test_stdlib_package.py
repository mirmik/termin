from pathlib import Path

from termin.stdlib import iter_stdlib_files, stdlib_root, sync_stdlib


def test_stdlib_root_contains_standard_resources() -> None:
    root = stdlib_root()

    assert (root / "materials" / "BlinnPhong.material").is_file()
    assert (root / "shaders" / "BlinnPhong.shader").is_file()
    assert (root / "uiscript" / "editor_camera_ui.uiscript").is_file()
    assert root / "materials" / "BlinnPhong.material" in iter_stdlib_files()


def test_sync_stdlib_copies_resources_and_reports_noop(tmp_path: Path) -> None:
    first = sync_stdlib(tmp_path)

    assert first.copied > 0
    assert first.removed == 0
    assert (tmp_path / "stdlib" / "materials" / "BlinnPhong.material").is_file()
    assert (tmp_path / "stdlib" / "uiscript" / "editor_camera_ui.uiscript").is_file()

    second = sync_stdlib(tmp_path)

    assert second.copied == 0
    assert second.removed == 0


def test_sync_stdlib_clean_removes_stale_files(tmp_path: Path) -> None:
    sync_stdlib(tmp_path)
    stale_path = tmp_path / "stdlib" / "obsolete" / "old.material"
    stale_path.parent.mkdir(parents=True)
    stale_path.write_text("{}", encoding="utf-8")

    result = sync_stdlib(tmp_path, clean=True)

    assert result.removed == 1
    assert not stale_path.exists()


def test_sync_stdlib_dry_run_does_not_mutate_files(tmp_path: Path) -> None:
    result = sync_stdlib(tmp_path, dry_run=True)

    assert result.copied > 0
    assert not (tmp_path / "stdlib").exists()
