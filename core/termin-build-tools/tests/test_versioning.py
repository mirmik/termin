from pathlib import Path
import re

from termin_build.versioning import public_version
from termin_build.package_manifest import load_manifest


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_public_version_is_canonical() -> None:
    assert public_version() == "0.5.2"


def test_distribution_metadata_uses_canonical_version_source() -> None:
    package_dirs = [REPO_ROOT / package.path for package in load_manifest(REPO_ROOT)]
    setup_files = [path for directory in package_dirs for path in directory.glob("setup.py")]
    assert setup_files
    for path in setup_files:
        text = path.read_text(encoding="utf-8")
        assert 'version="0.1.0"' not in text, path
        if re.search(r"\bversion\s*=", text):
            assert "public_version()" in text or "compute_local_version()" in text, path

    pyproject_files = [path for directory in package_dirs for path in directory.glob("pyproject.toml")]
    pyproject_files.extend((REPO_ROOT / "examples").glob("*/pyproject.toml"))
    for path in pyproject_files:
        text = path.read_text(encoding="utf-8")
        if 'version = "' in text:
            assert 'version = "0.5.2"' in text, path
