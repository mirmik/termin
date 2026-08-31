from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "install_slang_toolchain.py"
SPEC = importlib.util.spec_from_file_location("install_slang_toolchain", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def test_platform_key_accepts_windows_x86_64(monkeypatch) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Windows")
    monkeypatch.setattr(installer.platform, "machine", lambda: "AMD64")

    assert installer.platform_key() == "windows-x86_64"


def test_install_extracts_pinned_windows_zip_idempotently(
    tmp_path: Path, monkeypatch
) -> None:
    archive_source = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_source, "w") as bundle:
        bundle.writestr("bin/slangc.exe", b"compiler")
        bundle.writestr("bin/slang.dll", b"runtime")
    digest = hashlib.sha256(archive_source.read_bytes()).hexdigest()
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps(
            {
                "version": "test-version",
                "platforms": {
                    "windows-x86_64": {
                        "archive": "slang.zip",
                        "url": archive_source.as_uri(),
                        "sha256": digest,
                        "executable": "bin/slangc.exe",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(installer, "platform_key", lambda: "windows-x86_64")
    verified = []
    monkeypatch.setattr(
        installer,
        "verify_version",
        lambda executable, version: verified.append((executable, version)),
    )
    root = tmp_path / "toolchains"

    executable, version = installer.install(lock, root, require_installed=False)
    repeated, repeated_version = installer.install(lock, root, require_installed=True)

    assert executable == root / "slang-test-version" / "bin" / "slangc.exe"
    assert repeated == executable
    assert version == repeated_version == "test-version"
    assert (executable.parent / "slang.dll").read_bytes() == b"runtime"
    assert len(verified) == 2
    assert verified[0][0].name == verified[1][0].name == "slangc.exe"
    assert [entry[1] for entry in verified] == ["test-version", "test-version"]


def test_install_runs_post_extract_script_before_validation(
    tmp_path: Path, monkeypatch
) -> None:
    archive_source = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_source, "w") as bundle:
        bundle.writestr("bin/slangc.exe", b"compiler")
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps(
            {
                "version": "test-version",
                "platforms": {
                    "windows-x86_64": {
                        "archive": "slang.zip",
                        "url": archive_source.as_uri(),
                        "sha256": hashlib.sha256(archive_source.read_bytes()).hexdigest(),
                        "executable": "bin/slangc.exe",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    patch_script = tmp_path / "patch.py"
    patch_script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path(sys.argv[1], 'patched').write_text('yes', encoding='utf-8')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(installer, "platform_key", lambda: "windows-x86_64")

    def verify(executable: Path, _version: str) -> None:
        assert (executable.parents[1] / "patched").read_text(encoding="utf-8") == "yes"

    monkeypatch.setattr(installer, "verify_version", verify)

    installer.install(
        lock,
        tmp_path / "toolchains",
        require_installed=False,
        post_extract_script=patch_script,
    )


def test_zip_path_escape_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.exe", b"bad")

    try:
        installer.extract_archive(archive, tmp_path / "output")
    except RuntimeError as error:
        assert "outside its root" in str(error)
    else:
        raise AssertionError("path traversal archive was accepted")


def test_windows_install_publish_retries_transient_file_lock(monkeypatch) -> None:
    class LockedStaging:
        def __init__(self) -> None:
            self.attempts = 0

        def replace(self, destination: Path) -> None:
            del destination
            self.attempts += 1
            if self.attempts < 3:
                raise PermissionError("scanner still holds slangc.exe")

    staging = LockedStaging()
    delays = []
    monkeypatch.setattr(installer.platform, "system", lambda: "Windows")
    monkeypatch.setattr(installer.time, "sleep", delays.append)

    installer.replace_install_directory(staging, Path("slang-test-version"))

    assert staging.attempts == 3
    assert delays == [0.25, 0.5]
