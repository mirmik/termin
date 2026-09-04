from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import zipfile

import pytest

from termin_build.graphics_nuget_consumer_gate import REPORT_KIND, REPORT_NAME, REPORT_SCHEMA
from termin_build.graphics_nuget_product import PRODUCT_MANIFEST, build_product, load_lock
from termin_build.graphics_nuget_publish import (
    GraphicsNugetPublishError,
    GraphicsNugetReleaseCandidate,
    NugetV3Client,
    publish_release,
    validate_release_candidate,
    verify_remote_package,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
REVISION = "2" * 40


def _write_file(root: Path, relative: Path | str, payload: bytes = b"payload") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _synthetic_sdk(tmp_path: Path) -> Path:
    root = tmp_path / "sdk-graphics"
    lock = load_lock(REPO_ROOT)
    _write_file(root, lock.runtime_assembly, b"managed-runtime")
    _write_file(root, lock.wpf_assembly, b"managed-wpf")
    for name in lock.required_native_libraries:
        _write_file(root, lock.native_runtime_root / name, name.encode("ascii"))
    for relative in lock.required_resources:
        _write_file(root, lock.resource_root / relative, relative.as_posix().encode())
    return root


def _write_evidence(candidate: Path, evidence: Path) -> None:
    evidence.mkdir()
    manifest_path = candidate / PRODUCT_MANIFEST
    shutil.copy2(manifest_path, evidence / "candidate-manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = {
        "schema": REPORT_SCHEMA,
        "report_kind": REPORT_KIND,
        "status": "passed",
        "product": manifest["product"],
        "version": manifest["version"],
        "platform": manifest["platform"],
        "runtime_identifier": manifest["runtime_identifier"],
        "target_framework": manifest["target_framework"],
        "candidate_manifest": {
            "filename": "candidate-manifest.json",
            "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
        "packages": [
            {
                "id": package["id"],
                "filename": package["filename"],
                "sha256": package["sha256"],
                "size": package["size"],
            }
            for package in manifest["packages"]
        ],
        "consumer_output": [{"path": "Termin.Native.dll"}],
        "smoke": {"status": "passed", "backend": "D3D11", "wpf": True},
        "logs": ["build.log", "restore.log", "run.log"],
        "failure": None,
    }
    (evidence / REPORT_NAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _candidate(tmp_path: Path) -> tuple[Path, Path]:
    candidate = tmp_path / "candidate"
    build_product(
        REPO_ROOT,
        _synthetic_sdk(tmp_path),
        candidate,
        source_revision=REVISION,
        source_dirty=False,
    )
    evidence = tmp_path / "evidence"
    _write_evidence(candidate, evidence)
    return candidate, evidence


def _signed_package(payload: bytes) -> bytes:
    source = zipfile.ZipFile(BytesIO(payload))
    result = BytesIO()
    with source, zipfile.ZipFile(result, "w") as destination:
        for info in source.infolist():
            destination.writestr(info, source.read(info.filename))
        destination.writestr(".signature.p7s", b"repository-signature")
    return result.getvalue()


def _mutate_first_member(payload: bytes) -> bytes:
    source = zipfile.ZipFile(BytesIO(payload))
    result = BytesIO()
    with source, zipfile.ZipFile(result, "w") as destination:
        first = True
        for info in source.infolist():
            member = source.read(info.filename)
            if first:
                member += b"tampered"
                first = False
            destination.writestr(info, member)
    return result.getvalue()


class FakeNugetClient:
    def __init__(
        self,
        candidate: GraphicsNugetReleaseCandidate,
        remote: dict[str, bytes] | None = None,
    ) -> None:
        self.remote = dict(remote or {})
        self.by_filename = {
            package.path.name: package.package_id for package in candidate.packages
        }
        self.pushes: list[str] = []

    def download_package(self, package_id: str, version: str) -> bytes | None:
        assert version
        return self.remote.get(package_id)

    def push_package(self, package: Path, api_key: str) -> None:
        assert api_key == "secret"
        package_id = self.by_filename[package.name]
        self.pushes.append(package_id)
        self.remote[package_id] = _signed_package(package.read_bytes())


class FakeHttpResponse:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self) -> FakeHttpResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload

    def getcode(self) -> int:
        return self.status


def test_validates_candidate_bound_to_passed_gate(tmp_path: Path) -> None:
    candidate, evidence = _candidate(tmp_path)

    release = validate_release_candidate(REPO_ROOT, candidate, evidence)

    assert release.version == "0.5.2"
    assert release.source_revision == REVISION
    assert [package.package_id for package in release.packages] == [
        "Termin.Graphics",
        "Termin.Graphics.Wpf",
    ]


def test_rejects_failed_gate(tmp_path: Path) -> None:
    candidate, evidence = _candidate(tmp_path)
    report_path = evidence / REPORT_NAME
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["status"] = "failed"
    report["failure"] = "render failed"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(GraphicsNugetPublishError, match="did not pass"):
        validate_release_candidate(REPO_ROOT, candidate, evidence)


def test_rejects_evidence_for_a_different_candidate(tmp_path: Path) -> None:
    candidate, evidence = _candidate(tmp_path)
    evidence_manifest = evidence / "candidate-manifest.json"
    evidence_manifest.write_bytes(evidence_manifest.read_bytes() + b" ")

    with pytest.raises(GraphicsNugetPublishError, match="different candidate manifest"):
        validate_release_candidate(REPO_ROOT, candidate, evidence)


def test_rejects_dirty_candidate_provenance(tmp_path: Path) -> None:
    candidate, evidence = _candidate(tmp_path)
    manifest_path = candidate / PRODUCT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source"]["dirty"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    shutil.copy2(manifest_path, evidence / "candidate-manifest.json")

    with pytest.raises(GraphicsNugetPublishError, match="source must be clean"):
        validate_release_candidate(REPO_ROOT, candidate, evidence)


def test_rejects_manifest_provenance_different_from_package(tmp_path: Path) -> None:
    candidate, evidence = _candidate(tmp_path)
    manifest_path = candidate / PRODUCT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source"]["revision"] = "3" * 40
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    shutil.copy2(manifest_path, evidence / "candidate-manifest.json")
    report_path = evidence / REPORT_NAME
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["candidate_manifest"]["sha256"] = hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(GraphicsNugetPublishError, match="repository provenance differs"):
        validate_release_candidate(REPO_ROOT, candidate, evidence)


def test_remote_repository_signature_is_the_only_allowed_extra_member(
    tmp_path: Path,
) -> None:
    candidate, evidence = _candidate(tmp_path)
    release = validate_release_candidate(REPO_ROOT, candidate, evidence)
    package = release.packages[0]

    remote = verify_remote_package(package, _signed_package(package.path.read_bytes()))

    assert remote.repository_signature is True


def test_v3_push_uses_discovered_endpoint_and_secret_header(tmp_path: Path) -> None:
    package = tmp_path / "Termin.Graphics.0.5.2.nupkg"
    package.write_bytes(b"package-bytes")
    requests = []

    def open_url(request, *, timeout: int):
        assert timeout > 0
        requests.append(request)
        if request.full_url.endswith("/v3/index.json"):
            return FakeHttpResponse(
                json.dumps(
                    {
                        "resources": [
                            {
                                "@id": "https://upload.example.test/api/v2/package",
                                "@type": "PackagePublish/2.0.0",
                            },
                            {
                                "@id": "https://content.example.test/v3-flatcontainer/",
                                "@type": "PackageBaseAddress/3.0.0",
                            },
                        ]
                    }
                ).encode("utf-8")
            )
        return FakeHttpResponse(b"", status=201)

    client = NugetV3Client(
        "https://api.example.test/v3/index.json",
        open_url=open_url,
    )

    client.push_package(package, "scoped-secret")

    push_request = requests[-1]
    assert push_request.full_url == "https://upload.example.test/api/v2/package"
    assert push_request.get_method() == "PUT"
    assert push_request.get_header("X-nuget-apikey") == "scoped-secret"
    assert b"package-bytes" in push_request.data


def test_dry_run_prints_ordered_plan_without_push(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate, evidence = _candidate(tmp_path)
    release = validate_release_candidate(REPO_ROOT, candidate, evidence)
    client = FakeNugetClient(release)

    publish_release(release, client=client, upload=False)

    output = capsys.readouterr().out
    assert output.index("Termin.Graphics 0.5.2") < output.index(
        "Termin.Graphics.Wpf 0.5.2"
    )
    assert "action=would upload" in output
    assert client.pushes == []


def test_publish_uploads_base_then_wpf_and_reconciles(tmp_path: Path) -> None:
    candidate, evidence = _candidate(tmp_path)
    release = validate_release_candidate(REPO_ROOT, candidate, evidence)
    client = FakeNugetClient(release)

    publish_release(
        release,
        client=client,
        upload=True,
        api_key="secret",
        visibility_delay=0,
        sleep=lambda _seconds: None,
    )

    assert client.pushes == ["Termin.Graphics", "Termin.Graphics.Wpf"]


def test_partial_publication_resumes_with_only_wpf(tmp_path: Path) -> None:
    candidate, evidence = _candidate(tmp_path)
    release = validate_release_candidate(REPO_ROOT, candidate, evidence)
    runtime = release.packages[0]
    client = FakeNugetClient(
        release,
        {runtime.package_id: _signed_package(runtime.path.read_bytes())},
    )

    publish_release(
        release,
        client=client,
        upload=True,
        api_key="secret",
        visibility_delay=0,
        sleep=lambda _seconds: None,
    )

    assert client.pushes == ["Termin.Graphics.Wpf"]


def test_preflight_remote_conflict_blocks_all_uploads(tmp_path: Path) -> None:
    candidate, evidence = _candidate(tmp_path)
    release = validate_release_candidate(REPO_ROOT, candidate, evidence)
    wpf = release.packages[1]
    client = FakeNugetClient(
        release,
        {wpf.package_id: _mutate_first_member(wpf.path.read_bytes())},
    )

    with pytest.raises(GraphicsNugetPublishError, match="content differs"):
        publish_release(
            release,
            client=client,
            upload=True,
            api_key="secret",
            visibility_delay=0,
            sleep=lambda _seconds: None,
        )

    assert client.pushes == []
