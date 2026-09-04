"""Validate, reconcile, and explicitly publish Termin Graphics NuGet packages."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time
from typing import Callable, Protocol
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import uuid
from xml.etree import ElementTree
import zipfile

from .graphics_nuget_consumer_gate import REPORT_KIND, REPORT_NAME, REPORT_SCHEMA
from .graphics_nuget_product import (
    PACKAGE_REPOSITORY_URL,
    PRODUCT_MANIFEST,
    GraphicsNugetProductError,
    load_lock,
    validate_candidate,
)
from .versioning import public_version


DEFAULT_SERVICE_INDEX = "https://api.nuget.org/v3/index.json"
REPOSITORY_SIGNATURE_PATH = ".signature.p7s"
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class GraphicsNugetPublishError(RuntimeError):
    """The gated candidate or remote release is unsafe to publish."""


class NugetPackageExistsError(GraphicsNugetPublishError):
    """The package source rejected a push because the version already exists."""


@dataclass(frozen=True)
class ArchiveMember:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class NugetPackageCandidate:
    package_id: str
    version: str
    path: Path
    sha256: str
    size: int
    archive_members: tuple[ArchiveMember, ...]


@dataclass(frozen=True)
class GraphicsNugetReleaseCandidate:
    root: Path
    evidence_root: Path
    version: str
    source_revision: str
    packages: tuple[NugetPackageCandidate, ...]


@dataclass(frozen=True)
class RemotePackageEvidence:
    archive_sha256: str
    archive_size: int
    repository_signature: bool


class NugetClient(Protocol):
    def download_package(self, package_id: str, version: str) -> bytes | None: ...

    def push_package(self, package: Path, api_key: str) -> None: ...


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GraphicsNugetPublishError(f"{context} must be an object")
    return value


def _require_array(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise GraphicsNugetPublishError(f"{context} must be an array")
    return value


def _require_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise GraphicsNugetPublishError(f"{context} must be a non-empty string")
    return value


def _require_sha256(value: object, context: str) -> str:
    digest = _require_string(value, context)
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise GraphicsNugetPublishError(f"{context} must be a lowercase SHA-256")
    return digest


def _require_size(value: object, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise GraphicsNugetPublishError(f"{context} must be a non-negative integer")
    return value


def _read_json_object(path: Path, context: str) -> dict[str, object]:
    try:
        return _require_object(json.loads(path.read_text(encoding="utf-8")), context)
    except FileNotFoundError as error:
        raise GraphicsNugetPublishError(f"{context} does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise GraphicsNugetPublishError(f"invalid {context} {path}: {error}") from error


def _archive_members(raw_members: object, package_id: str) -> tuple[ArchiveMember, ...]:
    members: list[ArchiveMember] = []
    seen: set[str] = set()
    for index, raw_member in enumerate(_require_array(raw_members, f"{package_id} archive_files")):
        member = _require_object(raw_member, f"{package_id} archive_files[{index}]")
        path = _require_string(member.get("path"), f"{package_id} member path")
        archive_path = PurePosixPath(path)
        if (
            "\\" in path
            or archive_path.is_absolute()
            or any(part in {"", ".", ".."} for part in archive_path.parts)
            or path in seen
        ):
            raise GraphicsNugetPublishError(
                f"{package_id} has an unsafe or duplicate archive member: {path!r}"
            )
        seen.add(path)
        members.append(
            ArchiveMember(
                path=path,
                sha256=_require_sha256(
                    member.get("sha256"), f"{package_id} member {path} SHA-256"
                ),
                size=_require_size(member.get("size"), f"{package_id} member {path} size"),
            )
        )
    if not members:
        raise GraphicsNugetPublishError(f"{package_id} archive manifest is empty")
    return tuple(sorted(members, key=lambda item: item.path))


def _validate_package_provenance(
    package: Path,
    package_id: str,
    source_revision: str,
) -> None:
    try:
        with zipfile.ZipFile(package) as archive:
            root = ElementTree.fromstring(archive.read(f"{package_id}.nuspec"))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise GraphicsNugetPublishError(
            f"cannot read repository provenance from {package.name}: {error}"
        ) from error
    namespace = {"n": root.tag.partition("}")[0].removeprefix("{")}
    repository = root.find("n:metadata/n:repository", namespace)
    actual = None if repository is None else {
        "type": repository.get("type"),
        "url": repository.get("url"),
        "commit": repository.get("commit"),
    }
    expected = {
        "type": "git",
        "url": PACKAGE_REPOSITORY_URL,
        "commit": source_revision,
    }
    if actual != expected:
        raise GraphicsNugetPublishError(
            f"{package.name} repository provenance differs from its candidate manifest: "
            f"expected={expected}, actual={actual}"
        )


def _validate_gate_report(
    evidence_root: Path,
    candidate_manifest_path: Path,
    manifest: dict[str, object],
) -> None:
    evidence_manifest_path = evidence_root / "candidate-manifest.json"
    try:
        candidate_manifest_bytes = candidate_manifest_path.read_bytes()
        evidence_manifest_bytes = evidence_manifest_path.read_bytes()
    except OSError as error:
        raise GraphicsNugetPublishError(
            f"cannot read candidate/evidence manifest: {error}"
        ) from error
    if evidence_manifest_bytes != candidate_manifest_bytes:
        raise GraphicsNugetPublishError(
            "passed gate evidence is bound to a different candidate manifest"
        )
    report = _read_json_object(evidence_root / REPORT_NAME, "consumer gate report")
    expected_header = {
        "schema": REPORT_SCHEMA,
        "report_kind": REPORT_KIND,
        "status": "passed",
        "product": manifest.get("product"),
        "version": manifest.get("version"),
        "platform": manifest.get("platform"),
        "runtime_identifier": manifest.get("runtime_identifier"),
        "target_framework": manifest.get("target_framework"),
        "failure": None,
    }
    actual_header = {key: report.get(key) for key in expected_header}
    if actual_header != expected_header:
        raise GraphicsNugetPublishError(
            "consumer gate report did not pass for this product: "
            f"expected={expected_header}, actual={actual_header}"
        )
    report_manifest = _require_object(
        report.get("candidate_manifest"), "consumer gate candidate_manifest"
    )
    expected_manifest_digest = _sha256_bytes(evidence_manifest_bytes)
    if report_manifest != {
        "filename": "candidate-manifest.json",
        "sha256": expected_manifest_digest,
    }:
        raise GraphicsNugetPublishError(
            "consumer gate report candidate manifest digest does not match evidence"
        )
    smoke = _require_object(report.get("smoke"), "consumer gate smoke")
    if (
        smoke.get("status") != "passed"
        or smoke.get("backend") != "D3D11"
        or smoke.get("wpf") is not True
    ):
        raise GraphicsNugetPublishError(
            f"consumer gate has no passed WPF/D3D11 smoke: {smoke!r}"
        )
    if not _require_array(report.get("consumer_output"), "consumer gate output"):
        raise GraphicsNugetPublishError("consumer gate recorded no validated output files")
    expected_packages = [
        {
            "id": package["id"],
            "filename": package["filename"],
            "sha256": package["sha256"],
            "size": package["size"],
        }
        for package in _require_array(manifest.get("packages"), "candidate packages")
        if isinstance(package, dict)
    ]
    if report.get("packages") != expected_packages:
        raise GraphicsNugetPublishError(
            "consumer gate package identities/hashes do not match the candidate"
        )


def validate_release_candidate(
    repo_root: Path,
    candidate_root: Path,
    evidence_root: Path,
) -> GraphicsNugetReleaseCandidate:
    repo_root = repo_root.resolve()
    candidate_root = candidate_root.resolve()
    evidence_root = evidence_root.resolve()
    try:
        manifest = validate_candidate(repo_root, candidate_root)
    except GraphicsNugetProductError as error:
        raise GraphicsNugetPublishError(str(error)) from error
    version = public_version()
    if manifest.get("version") != version:
        raise GraphicsNugetPublishError(
            f"candidate version {manifest.get('version')!r} does not match {version}"
        )
    source = _require_object(manifest.get("source"), "candidate source")
    revision = _require_string(source.get("revision"), "candidate source revision")
    if source.get("repository") != PACKAGE_REPOSITORY_URL:
        raise GraphicsNugetPublishError(
            f"candidate source repository is not {PACKAGE_REPOSITORY_URL}"
        )
    if source.get("dirty") is not False:
        raise GraphicsNugetPublishError("candidate source must be clean")
    if _REVISION_RE.fullmatch(revision) is None:
        raise GraphicsNugetPublishError(
            "candidate source revision must be a full lowercase Git commit"
        )

    manifest_path = candidate_root / PRODUCT_MANIFEST
    _validate_gate_report(evidence_root, manifest_path, manifest)
    lock = load_lock(repo_root)
    package_order = (lock.runtime_package, lock.wpf_package)
    raw_packages = {
        _require_string(package.get("id"), "candidate package id"): package
        for package in (
            _require_object(raw, "candidate package")
            for raw in _require_array(manifest.get("packages"), "candidate packages")
        )
    }
    packages: list[NugetPackageCandidate] = []
    for package_id in package_order:
        package = raw_packages[package_id]
        filename = _require_string(package.get("filename"), f"{package_id} filename")
        path = candidate_root / filename
        digest = _require_sha256(package.get("sha256"), f"{package_id} SHA-256")
        size = _require_size(package.get("size"), f"{package_id} size")
        if path.stat().st_size != size:
            raise GraphicsNugetPublishError(
                f"NuGet package size mismatch for {filename}: expected {size}, "
                f"got {path.stat().st_size}"
            )
        _validate_package_provenance(path, package_id, revision)
        packages.append(
            NugetPackageCandidate(
                package_id=package_id,
                version=version,
                path=path,
                sha256=digest,
                size=size,
                archive_members=_archive_members(package.get("archive_files"), package_id),
            )
        )
    return GraphicsNugetReleaseCandidate(
        root=candidate_root,
        evidence_root=evidence_root,
        version=version,
        source_revision=revision,
        packages=tuple(packages),
    )


class NugetV3Client:
    def __init__(
        self,
        service_index_url: str,
        *,
        open_url: Callable[..., object] = urllib_request.urlopen,
    ) -> None:
        self.service_index_url = service_index_url
        self._open_url = open_url
        self._resources: dict[str, str] | None = None

    def _request_bytes(self, request: urllib_request.Request) -> bytes:
        try:
            with self._open_url(request, timeout=60) as response:  # type: ignore[attr-defined]
                return response.read()
        except urllib_error.HTTPError as error:
            raise GraphicsNugetPublishError(
                f"NuGet request failed for {request.full_url}: HTTP {error.code}"
            ) from error
        except (urllib_error.URLError, TimeoutError, OSError) as error:
            raise GraphicsNugetPublishError(
                f"NuGet request failed for {request.full_url}: {error}"
            ) from error

    def _load_resources(self) -> dict[str, str]:
        if self._resources is not None:
            return self._resources
        request = urllib_request.Request(
            self.service_index_url,
            headers={"User-Agent": "termin-graphics-nuget-publisher/0.5"},
        )
        try:
            payload = json.loads(self._request_bytes(request))
        except json.JSONDecodeError as error:
            raise GraphicsNugetPublishError(
                f"invalid NuGet service index {self.service_index_url}: {error}"
            ) from error
        root = _require_object(payload, "NuGet service index")
        resources: dict[str, str] = {}
        for raw_resource in _require_array(root.get("resources"), "NuGet resources"):
            resource = _require_object(raw_resource, "NuGet resource")
            resource_url = resource.get("@id")
            resource_types = resource.get("@type")
            if isinstance(resource_types, str):
                resource_types = [resource_types]
            if not isinstance(resource_url, str) or not isinstance(resource_types, list):
                continue
            for resource_type in resource_types:
                if isinstance(resource_type, str):
                    resources[resource_type] = resource_url
        self._resources = resources
        return resources

    def _resource(self, resource_type: str) -> str:
        value = self._load_resources().get(resource_type)
        if value is None:
            raise GraphicsNugetPublishError(
                f"NuGet service index has no {resource_type} resource"
            )
        return value

    def download_package(self, package_id: str, version: str) -> bytes | None:
        package_base = self._resource("PackageBaseAddress/3.0.0").rstrip("/")
        lower_id = package_id.lower()
        lower_version = version.lower()
        url = "/".join(
            (
                package_base,
                urllib_parse.quote(lower_id, safe=""),
                urllib_parse.quote(lower_version, safe=""),
                urllib_parse.quote(f"{lower_id}.{lower_version}.nupkg", safe=""),
            )
        )
        request = urllib_request.Request(
            url,
            headers={"User-Agent": "termin-graphics-nuget-publisher/0.5"},
        )
        try:
            with self._open_url(request, timeout=60) as response:  # type: ignore[attr-defined]
                return response.read()
        except urllib_error.HTTPError as error:
            if error.code == 404:
                return None
            raise GraphicsNugetPublishError(
                f"NuGet package lookup failed for {package_id} {version}: "
                f"HTTP {error.code}"
            ) from error
        except (urllib_error.URLError, TimeoutError, OSError) as error:
            raise GraphicsNugetPublishError(
                f"NuGet package lookup failed for {package_id} {version}: {error}"
            ) from error

    def push_package(self, package: Path, api_key: str) -> None:
        publish_url = self._resource("PackagePublish/2.0.0")
        boundary = f"termin-{uuid.uuid4().hex}"
        prefix = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="package"; filename="{package.name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("ascii")
        body = prefix + package.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
        request = urllib_request.Request(
            publish_url,
            data=body,
            method="PUT",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
                "User-Agent": "termin-graphics-nuget-publisher/0.5",
                "X-NuGet-ApiKey": api_key,
            },
        )
        try:
            with self._open_url(request, timeout=300) as response:  # type: ignore[attr-defined]
                status = response.getcode()
                if status not in {201, 202}:
                    raise GraphicsNugetPublishError(
                        f"NuGet push returned unexpected HTTP {status} for {package.name}"
                    )
        except urllib_error.HTTPError as error:
            if error.code == 409:
                raise NugetPackageExistsError(
                    f"NuGet package version already exists: {package.name}"
                ) from error
            raise GraphicsNugetPublishError(
                f"NuGet push failed for {package.name}: HTTP {error.code}"
            ) from error
        except (urllib_error.URLError, TimeoutError, OSError) as error:
            raise GraphicsNugetPublishError(
                f"NuGet push failed for {package.name}: {error}"
            ) from error


def verify_remote_package(
    package: NugetPackageCandidate,
    payload: bytes,
) -> RemotePackageEvidence:
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise GraphicsNugetPublishError(
                    f"remote {package.package_id} package has duplicate ZIP entries"
                )
            actual = {
                name: ArchiveMember(
                    path=name,
                    sha256=_sha256_bytes(archive.read(name)),
                    size=archive.getinfo(name).file_size,
                )
                for name in names
            }
    except zipfile.BadZipFile as error:
        raise GraphicsNugetPublishError(
            f"remote {package.package_id} package is not a valid NuGet archive"
        ) from error
    expected = {member.path: member for member in package.archive_members}
    extra = set(actual) - set(expected)
    missing = set(expected) - set(actual)
    if extra - {REPOSITORY_SIGNATURE_PATH} or missing:
        raise GraphicsNugetPublishError(
            f"remote {package.package_id} archive member set differs from the candidate; "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    mismatched = sorted(
        path
        for path in expected
        if actual[path].sha256 != expected[path].sha256
        or actual[path].size != expected[path].size
    )
    if mismatched:
        raise GraphicsNugetPublishError(
            f"remote {package.package_id} content differs from the gated candidate: "
            + ", ".join(mismatched)
        )
    return RemotePackageEvidence(
        archive_sha256=_sha256_bytes(payload),
        archive_size=len(payload),
        repository_signature=REPOSITORY_SIGNATURE_PATH in actual,
    )


def _remote_evidence(
    client: NugetClient,
    package: NugetPackageCandidate,
) -> RemotePackageEvidence | None:
    payload = client.download_package(package.package_id, package.version)
    if payload is None:
        return None
    return verify_remote_package(package, payload)


def publish_release(
    candidate: GraphicsNugetReleaseCandidate,
    *,
    client: NugetClient,
    upload: bool,
    api_key: str | None = None,
    visibility_attempts: int = 20,
    visibility_delay: float = 15.0,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    if visibility_attempts < 1 or visibility_delay < 0:
        raise GraphicsNugetPublishError("invalid remote visibility retry configuration")
    if upload and not api_key:
        raise GraphicsNugetPublishError(
            "--upload requires NUGET_API_KEY in the process environment"
        )

    print(
        f"Validated gated Termin Graphics NuGet {candidate.version} candidate "
        f"from {candidate.source_revision}."
    )
    for package in candidate.packages:
        evidence = _remote_evidence(client, package)
        remote_state = "matching" if evidence is not None else "absent"
        action = "skip" if evidence is not None else ("upload" if upload else "would upload")
        print(
            f"{package.package_id} {package.version}: sha256={package.sha256}, "
            f"size={package.size}, remote={remote_state}, action={action}"
        )
    if not upload:
        print("Dry run complete; no NuGet package was uploaded.")
        return

    for package in candidate.packages:
        current = _remote_evidence(client, package)
        if current is not None:
            print(f"Remote {package.package_id} {package.version} already matches; skipping.")
            continue
        print(f"Uploading {package.path.name} to NuGet...", flush=True)
        push_error: GraphicsNugetPublishError | None = None
        try:
            client.push_package(package.path, api_key or "")
        except NugetPackageExistsError:
            print(
                f"NuGet reported an existing {package.package_id} {package.version}; "
                "reconciling content before continuing.",
                file=sys.stderr,
                flush=True,
            )
        except GraphicsNugetPublishError as error:
            push_error = error
            print(
                f"NuGet push result for {package.path.name} was uncertain; "
                "reconciling remote content before failing.",
                file=sys.stderr,
                flush=True,
            )
        for attempt in range(visibility_attempts):
            current = _remote_evidence(client, package)
            if current is not None:
                print(
                    f"Remote {package.package_id} {package.version} matches every "
                    "candidate member."
                )
                break
            if attempt + 1 < visibility_attempts:
                sleep(visibility_delay)
        else:
            detail = f": {push_error}" if push_error is not None else ""
            raise GraphicsNugetPublishError(
                f"NuGet did not expose matching {package.package_id} {package.version} "
                f"after upload{detail}"
            )
    print("Publication complete; both remote packages match the gated candidate.")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="task publish:graphics:nuget --",
        description=__doc__,
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--service-index", default=DEFAULT_SERVICE_INDEX)
    parser.add_argument(
        "--upload",
        action="store_true",
        help="perform the irreversible, ordered NuGet uploads",
    )
    parser.add_argument(
        "--confirm-version",
        help="must exactly match the canonical version when --upload is used",
    )
    parser.add_argument("--visibility-attempts", type=int, default=20)
    parser.add_argument("--visibility-delay", type=float, default=15.0)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    candidate_dir = args.candidate_dir or repo_root / "dist" / "graphics-nuget"
    evidence_dir = (
        args.evidence_dir or repo_root / "build" / "graphics-nuget-consumer-gate"
    )
    try:
        candidate = validate_release_candidate(repo_root, candidate_dir, evidence_dir)
        if args.upload and args.confirm_version != candidate.version:
            raise GraphicsNugetPublishError(
                f"--upload requires --confirm-version {candidate.version}"
            )
        publish_release(
            candidate,
            client=NugetV3Client(args.service_index),
            upload=args.upload,
            api_key=os.environ.get("NUGET_API_KEY"),
            visibility_attempts=args.visibility_attempts,
            visibility_delay=args.visibility_delay,
        )
        return 0
    except (GraphicsNugetPublishError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: Graphics NuGet publication failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
