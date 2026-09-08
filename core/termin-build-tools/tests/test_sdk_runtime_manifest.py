import base64
import hashlib
import json
from pathlib import Path


from termin_build import (
    artifact_manifest,
    sdk,
    sdk_profiles,
    sdk_runtime_metadata,
)
from termin_build.package_manifest import PackageEntry


REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_test_distribution(
    site_packages: Path,
    name: str,
    version: str,
    module_name: str,
) -> Path:
    module_path = site_packages / f"{module_name}.py"
    module_path.write_text("VALUE = 1\n", encoding="utf-8")
    digest = base64.urlsafe_b64encode(hashlib.sha256(module_path.read_bytes()).digest())
    encoded = digest.rstrip(b"=").decode("ascii")
    metadata = site_packages / f"{name.replace('-', '_')}-{version}.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        f"Name: {name}\nVersion: {version}\n",
        encoding="utf-8",
    )
    (metadata / "RECORD").write_text(
        f"{module_path.name},sha256={encoded},{module_path.stat().st_size}\n{metadata.name}/RECORD,,\n",
        encoding="utf-8",
    )
    return module_path


def _write_empty_artifact_manifest(sdk_prefix: Path) -> None:
    artifacts: list[dict[str, object]] = []
    python_abi = artifact_manifest.PythonAbiIdentity.current()
    (sdk_prefix / artifact_manifest.SDK_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema": artifact_manifest.SCHEMA_VERSION,
                "manifest_kind": artifact_manifest.SDK_MANIFEST_KIND,
                "python_abi": python_abi.to_dict(),
                "native_build_id": artifact_manifest.compute_native_build_id(
                    artifacts,
                    python_abi,
                ),
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )
    profiles = sdk.load_sdk_profiles(REPO_ROOT)
    sdk_profiles.write_installed_sdk_product(
        sdk_prefix,
        profiles.profile(profiles.default_profile),
    )


def test_runtime_manifest_records_declared_distributions_and_verifies_hashes(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    site_packages = sdk_prefix / "lib" / "python3.10" / "site-packages"
    site_packages.mkdir(parents=True)
    _write_empty_artifact_manifest(sdk_prefix)
    lock_path = repo_root / sdk.RUNTIME_LOCK_RELATIVE
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("numpy==2.2.6\n", encoding="utf-8")
    _write_test_distribution(site_packages, "numpy", "2.2.6", "numpy_stub")
    _write_test_distribution(
        site_packages,
        "termin-example",
        "0.1.0",
        "termin_example",
    )
    monkeypatch.setattr(
        sdk_runtime_metadata,
        "load_manifest",
        lambda _root: [PackageEntry("example", "termin-example", (), ())],
    )
    monkeypatch.setattr(
        sdk_runtime_metadata,
        "_python_version_and_paths",
        lambda _python: {
            **artifact_manifest.PythonAbiIdentity.current().to_dict(),
        },
    )
    monkeypatch.setattr(sdk_runtime_metadata, "_python_executable", lambda: "python")

    output = sdk_runtime_metadata.write_python_runtime_manifest(
        repo_root,
        sdk_prefix,
        site_packages,
        runtime_python_abi=artifact_manifest.PythonAbiIdentity.current(),
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["python_abi"] == artifact_manifest.PythonAbiIdentity.current().to_dict()
    assert [entry["kind"] for entry in data["distributions"]] == [
        "runtime",
        "termin",
    ]
    assert sdk.verify_python_runtime_manifest(sdk_prefix) == 0


def test_runtime_manifest_records_distributions_from_composed_sdk_inputs(
    tmp_path,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    site_packages = sdk_prefix / "lib" / "python3.10" / "site-packages"
    site_packages.mkdir(parents=True)
    _write_empty_artifact_manifest(sdk_prefix)
    lock_path = repo_root / sdk.RUNTIME_LOCK_RELATIVE
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("numpy==2.2.6\n", encoding="utf-8")
    _write_test_distribution(site_packages, "numpy", "2.2.6", "numpy_stub")
    _write_test_distribution(site_packages, "termin-base", "0.1.0", "termin.base")

    output = sdk_runtime_metadata.write_python_runtime_manifest(
        repo_root,
        sdk_prefix,
        site_packages,
        runtime_python_abi=artifact_manifest.PythonAbiIdentity.current(),
        packages=(),
        additional_local_distributions=("termin-base",),
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    assert [(entry["name"], entry["kind"]) for entry in data["distributions"]] == [
        ("numpy", "runtime"),
        ("termin-base", "termin"),
    ]


def test_runtime_manifest_rejects_undeclared_and_modified_distributions(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    site_packages = sdk_prefix / "lib" / "python3.10" / "site-packages"
    site_packages.mkdir(parents=True)
    _write_empty_artifact_manifest(sdk_prefix)
    lock_path = repo_root / sdk.RUNTIME_LOCK_RELATIVE
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("numpy==2.2.6\n", encoding="utf-8")
    payload = _write_test_distribution(site_packages, "numpy", "2.2.6", "numpy_stub")
    monkeypatch.setattr(sdk_runtime_metadata, "load_manifest", lambda _root: [])
    monkeypatch.setattr(
        sdk_runtime_metadata,
        "_python_version_and_paths",
        lambda _python: {
            **artifact_manifest.PythonAbiIdentity.current().to_dict(),
        },
    )
    monkeypatch.setattr(sdk_runtime_metadata, "_python_executable", lambda: "python")
    sdk_runtime_metadata.write_python_runtime_manifest(
        repo_root,
        sdk_prefix,
        site_packages,
        runtime_python_abi=artifact_manifest.PythonAbiIdentity.current(),
    )

    payload.write_text("VALUE = 2\n", encoding="utf-8")
    _write_test_distribution(site_packages, "unexpected", "1.0", "unexpected")

    assert sdk.verify_python_runtime_manifest(sdk_prefix) == 1


def test_runtime_manifest_rejects_tampered_installed_product_recipe(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    site_packages = sdk_prefix / "lib" / "python3.10" / "site-packages"
    site_packages.mkdir(parents=True)
    _write_empty_artifact_manifest(sdk_prefix)
    lock_path = repo_root / sdk.RUNTIME_LOCK_RELATIVE
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("numpy==2.2.6\n", encoding="utf-8")
    _write_test_distribution(site_packages, "numpy", "2.2.6", "numpy_stub")
    monkeypatch.setattr(sdk_runtime_metadata, "load_manifest", lambda _root: [])

    sdk_runtime_metadata.write_python_runtime_manifest(
        repo_root,
        sdk_prefix,
        site_packages,
        runtime_python_abi=artifact_manifest.PythonAbiIdentity.current(),
    )
    (sdk_prefix / "sdk-product.json").write_text("{}\n", encoding="utf-8")

    assert sdk.verify_python_runtime_manifest(sdk_prefix) == 1
