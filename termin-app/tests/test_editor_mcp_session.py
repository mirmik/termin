import subprocess
import sys
from pathlib import Path

from termin.editor_core.mcp_session import (
    canonical_sdk_root,
    default_editor_mcp_session_file,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPOSITORY_ROOT / "scripts" / "termin-editor-mcp"


def test_default_editor_mcp_session_file_is_stable_per_sdk_root(tmp_path: Path):
    sdk_root = tmp_path / "checkout" / "sdk"
    first = default_editor_mcp_session_file(sdk_root=sdk_root, temp_dir=tmp_path)
    second = default_editor_mcp_session_file(sdk_root=sdk_root / ".", temp_dir=tmp_path)

    assert first == second
    assert first.parent == tmp_path
    assert first.name.startswith("termin-editor-mcp-")
    assert first.suffix == ".json"


def test_default_editor_mcp_session_file_separates_sdk_roots(tmp_path: Path):
    first = default_editor_mcp_session_file(sdk_root=tmp_path / "first" / "sdk", temp_dir=tmp_path)
    second = default_editor_mcp_session_file(sdk_root=tmp_path / "second" / "sdk", temp_dir=tmp_path)

    assert first != second


def test_canonical_sdk_root_resolves_symlinks(tmp_path: Path):
    sdk_root = tmp_path / "checkout" / "sdk"
    sdk_root.mkdir(parents=True)
    link = tmp_path / "sdk-link"
    link.symlink_to(sdk_root, target_is_directory=True)

    assert canonical_sdk_root(link) == canonical_sdk_root(sdk_root)


def test_helper_default_session_matches_checkout_sdk_root():
    completed = subprocess.run(
        [sys.executable, str(HELPER), "session-path"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    expected = default_editor_mcp_session_file(sdk_root=REPOSITORY_ROOT / "sdk")
    assert Path(completed.stdout.strip()) == expected
