from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from termin_build.graphics_python_product import PRODUCT_DISTRIBUTION, PRODUCT_MANIFEST
from termin_build.graphics_python_publish import (
    GraphicsPythonPublishError,
    TwineCommandError,
    publish_candidate,
    validate_candidate,
)
from termin_build.wheelhouse import inspect_wheel


REPO_ROOT = Path(__file__).resolve().parents[3]
VERSION = "0.5.0"
ABIS = ("cp314", "cp314t")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_wheel(
    root: Path,
    distribution: str,
    abi: str | None,
    *,
    license_file: str,
) -> Path:
    stem = distribution.replace("-", "_")
    if abi is None:
        filename = f"{stem}-{VERSION}-py3-none-any.whl"
        tag = "py3-none-any"
    else:
        wheel_abi = "cp314t" if abi == "cp314t" else "cp314"
        filename = (
            f"{stem}-{VERSION}-cp314-{wheel_abi}-manylinux_2_28_x86_64.whl"
        )
        tag = f"cp314-{wheel_abi}-manylinux_2_28_x86_64"
    path = root / filename
    dist_info = f"{stem}-{VERSION}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.4\nName: {distribution}\nVersion: {VERSION}\n"
            "License-Expression: Apache-2.0\n"
            "Description-Content-Type: text/markdown\n"
            "Requires-Dist: numpy>=2\nRequires-Dist: PyYAML>=6\n"
            f"License-File: {license_file}\n",
        )
        archive.writestr(f"{dist_info}/licenses/Termin/LICENSE.txt", b"license")
        archive.writestr(
            f"{dist_info}/WHEEL",
            f"Wheel-Version: 1.0\nGenerator: termin-test\nRoot-Is-Purelib: false\nTag: {tag}\n",
        )
    return path


def _candidate(tmp_path: Path, *, license_file: str = "Termin/LICENSE.txt") -> Path:
    root = tmp_path / "candidate"
    root.mkdir()
    records: list[dict[str, object]] = []
    wheels_by_abi: dict[str, str] = {}
    for abi in ABIS:
        wheel = _write_wheel(
            root,
            PRODUCT_DISTRIBUTION,
            abi,
            license_file=license_file,
        )
        records.append(
            {
                "filename": wheel.name,
                "sha256": _sha256(wheel),
                "python_abis": [abi],
                "auditwheel": {"show_after_sha256": "0" * 64},
            }
        )
        wheels_by_abi[abi] = wheel.name
    manifest = {
        "schema": 4,
        "manifest_kind": "termin-graphics-python-product",
        "product": PRODUCT_DISTRIBUTION,
        "version": VERSION,
        "profile": "graphics",
        "platform": "manylinux_2_28_x86_64",
        "python_abi_variants": list(ABIS),
        "variants": [
            {
                "id": abi,
                "version": VERSION,
                "wheel": wheels_by_abi[abi],
                "wheel_count": 1,
            }
            for abi in ABIS
        ],
        "shared_wheels": [],
        "wheels": sorted(records, key=lambda item: str(item["filename"])),
        "wheel_count": len(records),
    }
    (root / PRODUCT_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    assert len(records) == 2
    return root


def test_validate_complete_candidate(tmp_path: Path) -> None:
    candidate = validate_candidate(REPO_ROOT, _candidate(tmp_path))

    assert candidate.version == VERSION
    assert len(candidate.distributions) == 1
    assert len(candidate.wheels) == 2


def test_rejects_license_file_with_embedded_wheel_license_root(tmp_path: Path) -> None:
    root = _candidate(tmp_path, license_file="licenses/Termin/LICENSE.txt")

    with pytest.raises(
        GraphicsPythonPublishError,
        match="license metadata does not match archive payloads",
    ):
        validate_candidate(REPO_ROOT, root)


def test_rejects_undeclared_wheel(tmp_path: Path) -> None:
    root = _candidate(tmp_path)
    (root / "extra-0.5.0-py3-none-any.whl").write_bytes(b"not a wheel")

    with pytest.raises(GraphicsPythonPublishError, match="differs from manifest"):
        validate_candidate(REPO_ROOT, root)


def test_rejects_legacy_forty_wheel_shape(tmp_path: Path) -> None:
    root = _candidate(tmp_path)
    path = root / PRODUCT_MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["wheel_count"] = 40
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GraphicsPythonPublishError, match="wheel_count.*expected 2"):
        validate_candidate(REPO_ROOT, root)


def test_rejects_tampered_wheel(tmp_path: Path) -> None:
    root = _candidate(tmp_path)
    wheel = next(root.glob("*.whl"))
    with wheel.open("ab") as stream:
        stream.write(b"tampered")

    with pytest.raises(GraphicsPythonPublishError, match="SHA-256 mismatch"):
        validate_candidate(REPO_ROOT, root)


def test_rejects_stale_release_version(tmp_path: Path) -> None:
    root = _candidate(tmp_path)
    path = root / PRODUCT_MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["version"] = "0.1.0"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GraphicsPythonPublishError, match="expected '0.5.0'"):
        validate_candidate(REPO_ROOT, root)


def test_twine_receives_exact_manifest_paths(tmp_path: Path) -> None:
    candidate = validate_candidate(REPO_ROOT, _candidate(tmp_path))
    calls: list[tuple[list[str], Path]] = []
    remote: dict[str, dict[str, str]] = {}

    def record(command: list[str], *, cwd: Path) -> None:
        calls.append((command, cwd))
        if command[2:4] == ["twine", "upload"]:
            for raw_path in _uploaded_paths(command):
                path = Path(raw_path)
                distribution = inspect_wheel(path).name
                remote.setdefault(distribution, {})[path.name] = _sha256(path)

    def fetch(_base_url: str, distribution: str, _version: str) -> dict[str, str]:
        return dict(remote.get(distribution, {}))

    publish_candidate(
        candidate,
        repository="testpypi",
        upload=True,
        check=False,
        json_base_url="https://example.invalid/pypi",
        upload_delay=0,
        run=record,
        fetch_release=fetch,
        sleep=lambda _seconds: None,
    )

    assert len(calls) == 1 + len(candidate.distributions)
    assert calls[0][0][2:4] == ["twine", "check"]
    assert calls[1][0][2:7] == [
        "twine",
        "upload",
        "--verbose",
        "--repository",
        "testpypi",
    ]
    assert calls[0][0][4:] == [str(path) for path in candidate.wheels]
    uploaded = [
        raw_path for command, _cwd in calls[1:] for raw_path in _uploaded_paths(command)
    ]
    assert uploaded == [str(path) for path in candidate.wheels]
    assert all(cwd == candidate.root for _command, cwd in calls)


def _published_candidate(candidate) -> dict[str, dict[str, str]]:
    published: dict[str, dict[str, str]] = {}
    for wheel in candidate.wheels:
        distribution = inspect_wheel(wheel).name
        published.setdefault(distribution, {})[wheel.name] = _sha256(wheel)
    return published


def _uploaded_paths(command: list[str]) -> list[str]:
    repository_index = command.index("--repository")
    return command[repository_index + 2 :]


def test_resume_uploads_only_missing_remote_file(tmp_path: Path) -> None:
    candidate = validate_candidate(REPO_ROOT, _candidate(tmp_path))
    remote = _published_candidate(candidate)
    missing = candidate.wheels[-1]
    distribution = inspect_wheel(missing).name
    del remote[distribution][missing.name]
    uploads: list[list[str]] = []

    def record(command: list[str], *, cwd: Path) -> None:
        if command[2:4] == ["twine", "upload"]:
            uploads.append(command)
            for raw_path in _uploaded_paths(command):
                path = Path(raw_path)
                remote[distribution][path.name] = _sha256(path)

    publish_candidate(
        candidate,
        repository="pypi",
        upload=True,
        check=False,
        json_base_url="https://example.invalid/pypi",
        upload_delay=0,
        run=record,
        fetch_release=lambda _base, name, _version: dict(remote.get(name, {})),
        sleep=lambda _seconds: None,
    )

    assert len(uploads) == 1
    assert _uploaded_paths(uploads[0]) == [str(missing)]


def test_resume_rejects_remote_digest_conflict(tmp_path: Path) -> None:
    candidate = validate_candidate(REPO_ROOT, _candidate(tmp_path))
    remote = _published_candidate(candidate)
    wheel = candidate.wheels[0]
    distribution = inspect_wheel(wheel).name
    remote[distribution][wheel.name] = "f" * 64

    with pytest.raises(GraphicsPythonPublishError, match="digest conflict"):
        publish_candidate(
            candidate,
            repository="pypi",
            upload=False,
            check=False,
            remote_status=True,
            json_base_url="https://example.invalid/pypi",
            fetch_release=lambda _base, name, _version: dict(remote.get(name, {})),
        )


def test_resume_retries_http_429_with_backoff(tmp_path: Path) -> None:
    candidate = validate_candidate(REPO_ROOT, _candidate(tmp_path))
    remote = _published_candidate(candidate)
    target = candidate.distributions[0]
    target_wheels = tuple(
        wheel for wheel in candidate.wheels if inspect_wheel(wheel).name == target
    )
    remote[target] = {}
    upload_attempts = 0
    delays: list[float] = []

    def record(command: list[str], *, cwd: Path) -> None:
        nonlocal upload_attempts
        if command[2:4] != ["twine", "upload"]:
            return
        upload_attempts += 1
        if upload_attempts == 1:
            raise TwineCommandError(command, 1, "HTTPError: 429 Too Many Requests")
        for raw_path in _uploaded_paths(command):
            path = Path(raw_path)
            remote[target][path.name] = _sha256(path)

    publish_candidate(
        candidate,
        repository="pypi",
        upload=True,
        check=False,
        json_base_url="https://example.invalid/pypi",
        upload_delay=0,
        retry_base_delay=30,
        run=record,
        fetch_release=lambda _base, name, _version: dict(remote.get(name, {})),
        sleep=delays.append,
    )

    assert upload_attempts == 2
    assert delays == [30]
    assert set(remote[target]) == {wheel.name for wheel in target_wheels}


def test_resume_recovers_from_partial_distribution_upload(tmp_path: Path) -> None:
    candidate = validate_candidate(REPO_ROOT, _candidate(tmp_path))
    remote = _published_candidate(candidate)
    target = next(
        distribution
        for distribution in candidate.distributions
        if sum(inspect_wheel(wheel).name == distribution for wheel in candidate.wheels) == 2
    )
    target_wheels = tuple(
        wheel for wheel in candidate.wheels if inspect_wheel(wheel).name == target
    )
    remote[target] = {}
    uploads: list[list[str]] = []

    def record(command: list[str], *, cwd: Path) -> None:
        if command[2:4] != ["twine", "upload"]:
            return
        uploads.append(command)
        paths = [Path(raw_path) for raw_path in _uploaded_paths(command)]
        if len(uploads) == 1:
            first = paths[0]
            remote[target][first.name] = _sha256(first)
            raise TwineCommandError(command, 1, "connection reset after response")
        for path in paths:
            remote[target][path.name] = _sha256(path)

    publish_candidate(
        candidate,
        repository="pypi",
        upload=True,
        check=False,
        json_base_url="https://example.invalid/pypi",
        upload_delay=0,
        retry_base_delay=1,
        run=record,
        fetch_release=lambda _base, name, _version: dict(remote.get(name, {})),
        sleep=lambda _seconds: None,
    )

    assert len(uploads) == 2
    assert _uploaded_paths(uploads[0]) == [str(wheel) for wheel in target_wheels]
    assert _uploaded_paths(uploads[1]) == [str(target_wheels[1])]
