"""Canonical Termin distribution version handling."""

from pathlib import Path
import os
import re


_VERSION_FILE = Path("build-system") / "version.toml"


def _repository_root() -> Path:
    starts = (Path.cwd().resolve(), Path(__file__).resolve())
    for start in starts:
        for parent in (start, *start.parents):
            if (parent / _VERSION_FILE).is_file():
                return parent
    raise RuntimeError(f"cannot locate canonical version file {_VERSION_FILE}")


def public_version() -> str:
    """Return the single public version shared by all Termin distributions."""
    path = _repository_root() / _VERSION_FILE
    # Build entry points intentionally work with the host Python used to
    # bootstrap the pinned runtime, including Python 3.10 where tomllib is not
    # available.  The repository-owned file has one deliberately small field.
    match = re.fullmatch(
        r'\s*version\s*=\s*"(?P<version>[A-Za-z0-9][A-Za-z0-9.+!-]*)"\s*',
        path.read_text(encoding="utf-8"),
    )
    if match is None:
        raise RuntimeError(f"invalid canonical version in {path}")
    return match.group("version")


def package_version(*, sdk_build_id: str | None = None) -> str:
    """Return release version, adding the local SDK identity when requested."""
    release_version = os.environ.get("TERMIN_PYTHON_PACKAGE_VERSION")
    if release_version:
        return release_version
    if sdk_build_id:
        return f"{public_version()}+sdk{sdk_build_id}"
    return public_version()
