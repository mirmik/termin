from pathlib import Path
import re

from termin_build.versioning import public_version


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_public_version_is_canonical() -> None:
    assert public_version() == "0.5.2"


def test_distribution_metadata_uses_canonical_version_source() -> None:
    setup_files = sorted(REPO_ROOT.rglob("setup.py"))
    setup_files = [path for path in setup_files if "termin-thirdparty" not in path.parts]
    for path in setup_files:
        text = path.read_text(encoding="utf-8")
        assert 'version="0.1.0"' not in text, path
        if re.search(r"\bversion\s*=", text):
            assert "public_version()" in text or "compute_local_version()" in text, path

    for path in REPO_ROOT.rglob("pyproject.toml"):
        if "termin-thirdparty" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if 'version = "' in text:
            assert 'version = "0.5.2"' in text, path
