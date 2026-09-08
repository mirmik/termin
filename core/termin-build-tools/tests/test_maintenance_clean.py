from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
INVENTORY_SCRIPT = REPO_ROOT / "scripts" / "maintenance" / "clean_inventory.py"


def _load_inventory_module():
    spec = importlib.util.spec_from_file_location("termin_clean_inventory", INVENTORY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _touch(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_clean_inventory_discovers_current_project_classes_and_sdk_profiles(tmp_path: Path) -> None:
    inventory = _load_inventory_module()
    _touch(
        tmp_path / "build-system" / "sdk-profiles.json",
        '{"profiles":[{"id":"core","sdk_prefix":"sdk-core"},'
        '{"id":"graphics","sdk_prefix":"sdk-graphics"}]}',
    )
    _touch(tmp_path / "graphics" / "package" / "pyproject.toml")
    _touch(tmp_path / "termin-csharp" / "Termin.Wpf" / "Termin.Wpf.csproj")

    expected = {
        tmp_path / "build",
        tmp_path / "dist",
        tmp_path / "graphics" / "package" / "build_win",
        tmp_path / "graphics" / "package" / "install_win",
        tmp_path / "graphics" / "package" / "module.egg-info",
        tmp_path / "graphics" / "package" / "source" / "__pycache__",
        tmp_path / "termin-csharp" / "Termin.Wpf" / "bin",
        tmp_path / "termin-csharp" / "Termin.Wpf" / "obj",
        tmp_path / "sdk",
        tmp_path / "sdk-core",
        tmp_path / "sdk-graphics",
    }
    for directory in expected:
        directory.mkdir(parents=True, exist_ok=True)
    ignored = tmp_path / "termin-thirdparty" / "vendor" / "__pycache__"
    ignored.mkdir(parents=True)

    targets_without_sdk = set(inventory.collect_clean_targets(tmp_path, include_sdk=False))
    targets_with_sdk = set(inventory.collect_clean_targets(tmp_path, include_sdk=True))

    sdk_targets = {tmp_path / "sdk", tmp_path / "sdk-core", tmp_path / "sdk-graphics"}
    assert targets_without_sdk == expected - sdk_targets
    assert targets_with_sdk == expected
    assert ignored not in targets_with_sdk


def test_clean_inventory_dry_run_and_delete_are_confined_to_generated_targets(tmp_path: Path) -> None:
    build_file = tmp_path / "build" / "generated.txt"
    cache_file = tmp_path / "package" / "__pycache__" / "module.pyc"
    user_file = tmp_path / "user-data" / "keep.txt"
    _touch(build_file, "generated")
    _touch(cache_file, "cache")
    _touch(user_file, "keep")

    dry_run = subprocess.run(
        [sys.executable, str(INVENTORY_SCRIPT), "--root", str(tmp_path), "--dry-run"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
    assert "Dry run complete. Nothing was deleted." in dry_run.stdout
    assert build_file.is_file()
    assert cache_file.is_file()
    assert user_file.read_text(encoding="utf-8") == "keep"

    cleaned = subprocess.run(
        [sys.executable, str(INVENTORY_SCRIPT), "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert cleaned.returncode == 0, cleaned.stdout + cleaned.stderr
    assert not build_file.exists()
    assert not cache_file.exists()
    assert user_file.read_text(encoding="utf-8") == "keep"


def test_clean_launchers_delegate_to_the_same_inventory_and_preserve_cli_contract() -> None:
    shell = (REPO_ROOT / "scripts" / "maintenance" / "clean.sh").read_text(encoding="utf-8")
    powershell = (REPO_ROOT / "scripts" / "maintenance" / "clean.ps1").read_text(encoding="utf-8")

    assert "clean_inventory.py" in shell
    assert "clean_inventory.py" in powershell
    assert '"$@"' in shell
    assert '"--dry-run"' in powershell
    assert '"--include-sdk"' in powershell
    assert "[-DryRun] [-IncludeSdk]" in powershell
