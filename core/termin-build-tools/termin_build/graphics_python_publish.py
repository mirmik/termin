"""Validate and explicitly upload a complete Termin Graphics PyPI candidate."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email.parser import Parser
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from typing import Callable
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import zipfile

from .graphics_python_manylinux import MANYLINUX_PRODUCT_SCHEMA
from .graphics_python_product import (
    PRODUCT_DISTRIBUTION,
    PRODUCT_MANIFEST,
    PRODUCT_MANIFEST_KIND,
    SUPPORTED_PYTHON_ABIS,
)
from .versioning import public_version
from .wheelhouse import WheelArtifact, WheelhouseError, inspect_wheel


EXPECTED_PLATFORM = "manylinux_2_28_x86_64"
EXPECTED_WHEEL_COUNT = 2
EXPECTED_EXTERNAL_REQUIREMENTS = frozenset({"numpy", "pyyaml"})
_DISTRIBUTION_NORMALIZE_RE = re.compile(r"[-_.]+")
_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


class GraphicsPythonPublishError(RuntimeError):
    """The candidate is incomplete, inconsistent, or unsafe to upload."""


class TwineCommandError(GraphicsPythonPublishError):
    """Twine failed and exposed output suitable for retry classification."""

    def __init__(self, command: list[str], returncode: int, output: str) -> None:
        self.command = command
        self.returncode = returncode
        self.output = output
        super().__init__(
            f"command failed with exit code {returncode}: {shlex.join(command)}"
        )


class PyPIRateLimitError(GraphicsPythonPublishError):
    """PyPI metadata access was rate-limited."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(message)


@dataclass(frozen=True)
class GraphicsPythonReleaseCandidate:
    root: Path
    version: str
    distributions: tuple[str, ...]
    wheels: tuple[Path, ...]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_distributions(repo_root: Path) -> frozenset[str]:
    del repo_root
    return frozenset({PRODUCT_DISTRIBUTION})


def _normalized_distribution(name: str) -> str:
    return _DISTRIBUTION_NORMALIZE_RE.sub("-", name).lower()


def _validate_public_metadata(wheel: Path) -> None:
    try:
        with zipfile.ZipFile(wheel) as archive:
            metadata_names = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise GraphicsPythonPublishError(
                    f"wheel {wheel.name} has {len(metadata_names)} METADATA files"
                )
            metadata = Parser().parsestr(
                archive.read(metadata_names[0]).decode("utf-8")
            )
            dist_info = metadata_names[0].rsplit("/", 1)[0]
            license_root = f"{dist_info}/licenses/"
            archived_license_files = {
                name.removeprefix(license_root)
                for name in archive.namelist()
                if name.startswith(license_root) and not name.endswith("/")
            }
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as error:
        raise GraphicsPythonPublishError(
            f"cannot inspect public metadata in {wheel.name}: {error}"
        ) from error
    requirement_names: set[str] = set()
    for requirement in metadata.get_all("Requires-Dist", []):
        match = _REQUIREMENT_NAME_RE.match(requirement)
        if match is None:
            raise GraphicsPythonPublishError(
                f"cannot parse Requires-Dist in {wheel.name}: {requirement!r}"
            )
        requirement_names.add(_normalized_distribution(match.group(1)))
    if requirement_names != EXPECTED_EXTERNAL_REQUIREMENTS:
        raise GraphicsPythonPublishError(
            f"public wheel {wheel.name} has invalid external requirements: "
            f"{sorted(requirement_names)}"
        )
    declared_license_files = metadata.get_all("License-File", [])
    invalid_license_files = [
        name
        for name in declared_license_files
        if (
            not name
            or name.startswith("/")
            or "\\" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))
        )
    ]
    if invalid_license_files:
        raise GraphicsPythonPublishError(
            f"public wheel {wheel.name} has unsafe License-File paths: "
            f"{sorted(invalid_license_files)}"
        )
    duplicate_license_files = sorted(
        name
        for name in set(declared_license_files)
        if declared_license_files.count(name) > 1
    )
    if duplicate_license_files:
        raise GraphicsPythonPublishError(
            f"public wheel {wheel.name} has duplicate License-File entries: "
            f"{duplicate_license_files}"
        )
    declared_license_set = set(declared_license_files)
    missing_license_files = sorted(declared_license_set - archived_license_files)
    undeclared_license_files = sorted(archived_license_files - declared_license_set)
    if missing_license_files or undeclared_license_files:
        raise GraphicsPythonPublishError(
            f"public wheel {wheel.name} license metadata does not match archive payloads; "
            f"missing={missing_license_files}, undeclared={undeclared_license_files}"
        )
    if not declared_license_files or metadata.get("License-Expression") != "Apache-2.0":
        raise GraphicsPythonPublishError(
            f"public wheel {wheel.name} has incomplete license metadata"
        )
    if metadata.get("Description-Content-Type") != "text/markdown":
        raise GraphicsPythonPublishError(
            f"public wheel {wheel.name} has no Markdown project description"
        )


def _require_object(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GraphicsPythonPublishError(f"{description} must be an object")
    return value


def _require_string_list(value: object, description: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise GraphicsPythonPublishError(f"{description} must be a string array")
    return value


def _validate_record(
    root: Path,
    raw_record: object,
    *,
    expected_version: str,
) -> tuple[str, WheelArtifact, frozenset[str]]:
    record = _require_object(raw_record, "wheel record")
    filename = record.get("filename")
    if (
        not isinstance(filename, str)
        or not filename.endswith(".whl")
        or Path(filename).name != filename
    ):
        raise GraphicsPythonPublishError(f"unsafe wheel filename in manifest: {filename!r}")
    digest = record.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise GraphicsPythonPublishError(f"invalid SHA-256 for {filename}")
    wheel = root / filename
    if not wheel.is_file():
        raise GraphicsPythonPublishError(f"manifest-declared wheel is missing: {filename}")
    actual_digest = _sha256_file(wheel)
    if actual_digest != digest:
        raise GraphicsPythonPublishError(
            f"wheel SHA-256 mismatch for {filename}: expected {digest}, got {actual_digest}"
        )
    try:
        artifact = inspect_wheel(wheel)
    except WheelhouseError as error:
        raise GraphicsPythonPublishError(str(error)) from error
    if artifact.version != expected_version:
        raise GraphicsPythonPublishError(
            f"wheel {filename} has version {artifact.version}, expected {expected_version}"
        )
    if artifact.name != PRODUCT_DISTRIBUTION:
        raise GraphicsPythonPublishError(
            f"wheel {filename} is {artifact.name}, expected {PRODUCT_DISTRIBUTION}"
        )
    _validate_public_metadata(wheel)
    python_abis = frozenset(
        _require_string_list(record.get("python_abis"), f"python_abis for {filename}")
    )
    if not python_abis or not python_abis <= set(SUPPORTED_PYTHON_ABIS):
        raise GraphicsPythonPublishError(
            f"wheel {filename} has invalid Python ABI ownership: {sorted(python_abis)}"
        )
    native_abis = artifact.abi_tags - {"none"}
    platforms = {tag.rsplit("-", 1)[-1] for tag in artifact.tags}
    auditwheel = record.get("auditwheel")
    if native_abis:
        if len(native_abis) != 1 or python_abis != native_abis:
            raise GraphicsPythonPublishError(
                f"native wheel {filename} ABI metadata disagrees with its manifest record"
            )
        if platforms != {EXPECTED_PLATFORM} or not isinstance(auditwheel, dict):
            raise GraphicsPythonPublishError(
                f"native wheel {filename} is not an audited {EXPECTED_PLATFORM} artifact"
            )
    elif (
        python_abis != set(SUPPORTED_PYTHON_ABIS)
        or platforms != {"any"}
        or auditwheel is not None
    ):
        raise GraphicsPythonPublishError(
            f"pure wheel {filename} has invalid shared-ABI or audit metadata"
        )
    return filename, artifact, python_abis


def validate_candidate(
    repo_root: Path,
    candidate_root: Path,
) -> GraphicsPythonReleaseCandidate:
    repo_root = repo_root.resolve()
    candidate_root = candidate_root.resolve()
    manifest_path = candidate_root / PRODUCT_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GraphicsPythonPublishError(
            f"cannot read release manifest {manifest_path}: {error}"
        ) from error
    manifest = _require_object(manifest, "release manifest")
    version = public_version()
    expected_header = {
        "schema": MANYLINUX_PRODUCT_SCHEMA,
        "manifest_kind": PRODUCT_MANIFEST_KIND,
        "product": PRODUCT_DISTRIBUTION,
        "version": version,
        "profile": "graphics",
        "platform": EXPECTED_PLATFORM,
        "python_abi_variants": list(SUPPORTED_PYTHON_ABIS),
        "wheel_count": EXPECTED_WHEEL_COUNT,
    }
    for key, expected in expected_header.items():
        if manifest.get(key) != expected:
            raise GraphicsPythonPublishError(
                f"release manifest {key!r} is {manifest.get(key)!r}, expected {expected!r}"
            )

    raw_records = manifest.get("wheels")
    if not isinstance(raw_records, list) or len(raw_records) != EXPECTED_WHEEL_COUNT:
        raise GraphicsPythonPublishError(
            f"release manifest must contain exactly {EXPECTED_WHEEL_COUNT} wheel records"
        )
    artifacts: dict[str, WheelArtifact] = {}
    abi_ownership: dict[str, frozenset[str]] = {}
    for raw_record in raw_records:
        filename, artifact, python_abis = _validate_record(
            candidate_root,
            raw_record,
            expected_version=version,
        )
        if filename in artifacts:
            raise GraphicsPythonPublishError(f"duplicate wheel record: {filename}")
        artifacts[filename] = artifact
        abi_ownership[filename] = python_abis

    actual_wheels = {path.name for path in candidate_root.glob("*.whl")}
    declared_wheels = set(artifacts)
    if actual_wheels != declared_wheels:
        missing = sorted(declared_wheels - actual_wheels)
        extra = sorted(actual_wheels - declared_wheels)
        raise GraphicsPythonPublishError(
            f"candidate wheel set differs from manifest; missing={missing}, extra={extra}"
        )

    expected_distributions = _expected_distributions(repo_root)
    actual_distributions = {artifact.name for artifact in artifacts.values()}
    if actual_distributions != expected_distributions:
        raise GraphicsPythonPublishError(
            "candidate distribution set differs from the declarative Graphics profile; "
            f"missing={sorted(expected_distributions - actual_distributions)}, "
            f"extra={sorted(actual_distributions - expected_distributions)}"
        )

    variants = manifest.get("variants")
    if not isinstance(variants, list) or len(variants) != len(SUPPORTED_PYTHON_ABIS):
        raise GraphicsPythonPublishError("release manifest must contain both ABI variants")
    seen_variants: set[str] = set()
    for raw_variant in variants:
        variant = _require_object(raw_variant, "ABI variant")
        abi = variant.get("id")
        if abi not in SUPPORTED_PYTHON_ABIS or abi in seen_variants:
            raise GraphicsPythonPublishError(f"invalid or duplicate ABI variant: {abi!r}")
        seen_variants.add(abi)
        if variant.get("version") != version or variant.get("wheel_count") != 1:
            raise GraphicsPythonPublishError(f"ABI variant {abi} has invalid version or count")
        variant_wheel = variant.get("wheel")
        expected_variant_wheels = {
            filename for filename, owners in abi_ownership.items() if abi in owners
        }
        if (
            not isinstance(variant_wheel, str)
            or expected_variant_wheels != {variant_wheel}
        ):
            raise GraphicsPythonPublishError(
                f"ABI variant {abi} does not own exactly one public wheel"
            )

    shared_wheels = set(
        _require_string_list(manifest.get("shared_wheels"), "shared_wheels")
    )
    if shared_wheels:
        raise GraphicsPythonPublishError(
            "monolithic Graphics candidate must not contain shared wheels"
        )
    return GraphicsPythonReleaseCandidate(
        root=candidate_root,
        version=version,
        distributions=tuple(sorted(actual_distributions)),
        wheels=tuple(candidate_root / name for name in sorted(artifacts)),
    )


def _run_twine(command: list[str], *, cwd: Path) -> None:
    print("+ " + shlex.join(command), flush=True)
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
    if result.returncode != 0:
        raise TwineCommandError(command, result.returncode, result.stdout or "")


def _default_json_base_url(repository: str) -> str | None:
    return {
        "pypi": "https://pypi.org/pypi",
        "testpypi": "https://test.pypi.org/pypi",
    }.get(repository)


def _retry_after_seconds(headers: object) -> float | None:
    value = headers.get("Retry-After") if hasattr(headers, "get") else None
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _fetch_release_files(
    json_base_url: str,
    distribution: str,
    version: str,
) -> dict[str, str]:
    url = "/".join(
        (
            json_base_url.rstrip("/"),
            urllib_parse.quote(distribution, safe=""),
            urllib_parse.quote(version, safe=""),
            "json",
        )
    )
    request = urllib_request.Request(
        url,
        headers={"User-Agent": "termin-release-publisher/0.5"},
    )
    try:
        with urllib_request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib_error.HTTPError as error:
        if error.code == 404:
            return {}
        if error.code == 429:
            raise PyPIRateLimitError(
                f"PyPI metadata request was rate-limited for {distribution}=={version}",
                retry_after=_retry_after_seconds(error.headers),
            ) from error
        raise GraphicsPythonPublishError(
            f"PyPI metadata request failed for {distribution}=={version}: HTTP {error.code}"
        ) from error
    except (urllib_error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise GraphicsPythonPublishError(
            f"cannot read PyPI metadata for {distribution}=={version}: {error}"
        ) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("urls"), list):
        raise GraphicsPythonPublishError(
            f"invalid PyPI metadata response for {distribution}=={version}"
        )
    files: dict[str, str] = {}
    for raw_file in payload["urls"]:
        if not isinstance(raw_file, dict):
            raise GraphicsPythonPublishError(
                f"invalid PyPI file record for {distribution}=={version}"
            )
        filename = raw_file.get("filename")
        digests = raw_file.get("digests")
        digest = digests.get("sha256") if isinstance(digests, dict) else None
        if not isinstance(filename, str) or not isinstance(digest, str):
            raise GraphicsPythonPublishError(
                f"invalid PyPI filename or digest for {distribution}=={version}"
            )
        if filename in files and files[filename] != digest:
            raise GraphicsPythonPublishError(
                f"PyPI returned conflicting digests for {filename}"
            )
        files[filename] = digest
    return files


def _candidate_wheels_by_distribution(
    candidate: GraphicsPythonReleaseCandidate,
) -> dict[str, tuple[Path, ...]]:
    grouped: dict[str, list[Path]] = {}
    for wheel in candidate.wheels:
        try:
            distribution = inspect_wheel(wheel).name
        except WheelhouseError as error:
            raise GraphicsPythonPublishError(str(error)) from error
        grouped.setdefault(distribution, []).append(wheel)
    return {
        distribution: tuple(sorted(wheels))
        for distribution, wheels in sorted(grouped.items())
    }


def _is_rate_limit_failure(error: TwineCommandError) -> bool:
    output = error.output.lower()
    return "429" in output or "too many requests" in output


def _remote_pending_wheels(
    *,
    distribution: str,
    wheels: tuple[Path, ...],
    version: str,
    json_base_url: str,
    fetch_release: Callable[[str, str, str], dict[str, str]],
) -> tuple[Path, ...]:
    local = {wheel.name: _sha256_file(wheel) for wheel in wheels}
    remote = fetch_release(json_base_url, distribution, version)
    unexpected = sorted(set(remote) - set(local))
    if unexpected:
        raise GraphicsPythonPublishError(
            f"PyPI release {distribution}=={version} contains files outside this candidate: "
            f"{unexpected}"
        )
    for filename, remote_digest in remote.items():
        if remote_digest != local[filename]:
            raise GraphicsPythonPublishError(
                f"PyPI digest conflict for {filename}: remote {remote_digest}, "
                f"candidate {local[filename]}"
            )
    return tuple(wheel for wheel in wheels if wheel.name not in remote)


def _read_remote_with_backoff(
    operation: Callable[[], tuple[Path, ...]],
    *,
    max_retries: int,
    retry_base_delay: float,
    sleep: Callable[[float], None],
) -> tuple[Path, ...]:
    attempt = 0
    while True:
        try:
            return operation()
        except PyPIRateLimitError as error:
            if attempt >= max_retries:
                raise
            delay = error.retry_after or retry_base_delay * (2**attempt)
            print(
                f"PyPI metadata rate limit; retrying in {delay:.1f}s "
                f"({attempt + 1}/{max_retries})",
                file=sys.stderr,
                flush=True,
            )
            sleep(delay)
            attempt += 1


def publish_candidate(
    candidate: GraphicsPythonReleaseCandidate,
    *,
    repository: str,
    upload: bool,
    check: bool,
    remote_status: bool = False,
    json_base_url: str | None = None,
    upload_delay: float = 15.0,
    retry_base_delay: float = 60.0,
    max_retries: int = 6,
    run: Callable[..., None] = _run_twine,
    fetch_release: Callable[[str, str, str], dict[str, str]] = _fetch_release_files,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    wheel_args = [str(path) for path in candidate.wheels]
    if check or upload:
        run([sys.executable, "-m", "twine", "check", *wheel_args], cwd=candidate.root)
    upload_prefix = [
        sys.executable,
        "-m",
        "twine",
        "upload",
        "--verbose",
        "--repository",
        repository,
    ]
    upload_command = [
        *upload_prefix,
        *wheel_args,
    ]
    if not upload and not remote_status:
        print("Validated upload command (not executed):")
        print(shlex.join(upload_command))
        return
    if json_base_url is None:
        raise GraphicsPythonPublishError(
            f"repository {repository!r} has no known JSON metadata endpoint; "
            "pass --repository-json-base-url"
        )
    grouped = _candidate_wheels_by_distribution(candidate)

    def pending_for(distribution: str) -> tuple[Path, ...]:
        return _read_remote_with_backoff(
            lambda: _remote_pending_wheels(
                distribution=distribution,
                wheels=grouped[distribution],
                version=candidate.version,
                json_base_url=json_base_url,
                fetch_release=fetch_release,
            ),
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            sleep=sleep,
        )

    pending_by_distribution = {
        distribution: pending_for(distribution) for distribution in grouped
    }
    pending_count = sum(len(wheels) for wheels in pending_by_distribution.values())
    published_count = len(candidate.wheels) - pending_count
    print(
        f"Remote release state: {published_count} matching wheel(s) published, "
        f"{pending_count} pending"
    )
    if not upload:
        if pending_count:
            pending_distributions = [
                distribution
                for distribution, wheels in pending_by_distribution.items()
                if wheels
            ]
            print(
                "Pending distributions: " + ", ".join(pending_distributions)
            )
            print(
                "Resume with the guarded --upload command and "
                f"--confirm-version {candidate.version}."
            )
        return
    if not pending_count:
        print("PyPI already contains the complete manifest-declared candidate.")
        return
    print(
        "WARNING: PyPI uploads are non-transactional. Exact remote hashes are "
        "reconciled before every distribution; matching files are not resent.",
        file=sys.stderr,
        flush=True,
    )
    distributions = [
        distribution
        for distribution, wheels in pending_by_distribution.items()
        if wheels
    ]
    for index, distribution in enumerate(distributions):
        pending = pending_for(distribution)
        if not pending:
            print(f"Already published with matching hashes: {distribution}")
            continue
        attempt = 0
        while pending:
            command = [*upload_prefix, *(str(wheel) for wheel in pending)]
            try:
                run(command, cwd=candidate.root)
            except TwineCommandError as error:
                remaining = pending_for(distribution)
                if not remaining:
                    print(
                        f"Twine failed after PyPI accepted all files for {distribution}; "
                        "remote hashes match, continuing."
                    )
                    pending = ()
                    break
                made_progress = len(remaining) < len(pending)
                if not _is_rate_limit_failure(error) and not made_progress:
                    raise
                if attempt >= max_retries:
                    raise GraphicsPythonPublishError(
                        f"PyPI upload retry limit reached for {distribution}; "
                        f"{len(remaining)} wheel(s) still pending"
                    ) from error
                delay = retry_base_delay * (2**attempt)
                reason = "HTTP 429" if _is_rate_limit_failure(error) else "partial upload"
                print(
                    f"{reason} for {distribution}; retrying {len(remaining)} pending "
                    f"wheel(s) in {delay:.1f}s ({attempt + 1}/{max_retries})",
                    file=sys.stderr,
                    flush=True,
                )
                sleep(delay)
                pending = remaining
                attempt += 1
                continue
            visibility_attempt = 0
            while True:
                pending = pending_for(distribution)
                if not pending:
                    break
                if visibility_attempt >= max_retries:
                    raise GraphicsPythonPublishError(
                        f"Twine reported success but PyPI still lacks {len(pending)} "
                        f"wheel(s) for {distribution}"
                    )
                delay = retry_base_delay * (2**visibility_attempt)
                print(
                    f"Waiting {delay:.1f}s for PyPI metadata to expose {distribution}",
                    file=sys.stderr,
                    flush=True,
                )
                sleep(delay)
                visibility_attempt += 1
        if index + 1 < len(distributions) and upload_delay:
            print(f"Pacing next distribution upload by {upload_delay:.1f}s", flush=True)
            sleep(upload_delay)
    print(
        f"Upload complete: all {len(candidate.wheels)} manifest-declared wheels "
        "match the remote release."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--repository", default="pypi")
    parser.add_argument(
        "--repository-json-base-url",
        help="JSON metadata base URL; inferred for pypi and testpypi",
    )
    parser.add_argument("--check", action="store_true", help="run twine check")
    parser.add_argument(
        "--remote-status",
        action="store_true",
        help="compare the candidate with the remote release without uploading",
    )
    parser.add_argument("--upload", action="store_true", help="perform the irreversible upload")
    parser.add_argument(
        "--upload-delay",
        type=float,
        default=15.0,
        help="seconds to wait between distribution uploads (default: 15)",
    )
    parser.add_argument(
        "--retry-base-delay",
        type=float,
        default=60.0,
        help="initial 429/partial-upload retry delay in seconds (default: 60)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=6,
        help="maximum retries per metadata or distribution operation (default: 6)",
    )
    parser.add_argument(
        "--confirm-version",
        help="must exactly match the canonical version when --upload is used",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    candidate_dir = args.candidate_dir or repo_root / "dist" / "graphics-python-manylinux"
    try:
        candidate = validate_candidate(repo_root, candidate_dir)
        if args.upload_delay < 0 or args.retry_base_delay <= 0 or args.max_retries < 0:
            raise GraphicsPythonPublishError("invalid upload delay or retry configuration")
        if args.upload and args.confirm_version != candidate.version:
            raise GraphicsPythonPublishError(
                f"--upload requires --confirm-version {candidate.version}"
            )
        print(
            f"Validated Termin Graphics {candidate.version}: "
            f"{len(candidate.distributions)} distributions, {len(candidate.wheels)} wheels"
        )
        publish_candidate(
            candidate,
            repository=args.repository,
            upload=args.upload,
            check=args.check,
            remote_status=args.remote_status,
            json_base_url=(
                args.repository_json_base_url
                or _default_json_base_url(args.repository)
            ),
            upload_delay=args.upload_delay,
            retry_base_delay=args.retry_base_delay,
            max_retries=args.max_retries,
        )
        return 0
    except (GraphicsPythonPublishError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: Graphics publication preparation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
