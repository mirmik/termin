from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from termin_build.graphics_nuget_consumer_gate import (
    GraphicsNugetConsumerGateError,
    consumer_project_files,
    isolated_environment,
    validate_consumer_output,
)
from termin_build.graphics_nuget_product import GraphicsNugetLock, load_lock
from termin_build.versioning import public_version


REPO_ROOT = Path(__file__).resolve().parents[3]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _output_payloads(lock: GraphicsNugetLock) -> dict[str, bytes]:
    payloads = {
        "Termin.Native.dll": b"managed runtime",
        "Termin.Wpf.dll": b"managed WPF",
    }
    payloads.update(
        {name: f"native:{name}".encode("utf-8") for name in lock.required_native_libraries}
    )
    payloads.update(
        {
            f"share/termin/{relative.as_posix()}":
                f"resource:{relative.as_posix()}".encode("utf-8")
            for relative in lock.required_resources
        }
    )
    return payloads


def _manifest(lock: GraphicsNugetLock, payloads: dict[str, bytes]) -> dict[str, object]:
    archive_paths = {
        "Termin.Native.dll": f"lib/{lock.target_framework}/Termin.Native.dll",
        "Termin.Wpf.dll": f"lib/{lock.target_framework}/Termin.Wpf.dll",
    }
    archive_paths.update(
        {
            name: f"runtimes/{lock.runtime_identifier}/native/{name}"
            for name in lock.required_native_libraries
        }
    )
    archive_paths.update(
        {
            path: path
            for path in payloads
            if path.startswith("share/termin/")
        }
    )
    runtime_files = []
    wpf_files = []
    for output_path, payload in payloads.items():
        record = {
            "path": archive_paths[output_path],
            "sha256": _sha256(payload),
            "size": len(payload),
        }
        if output_path == "Termin.Wpf.dll":
            wpf_files.append(record)
        else:
            runtime_files.append(record)
    return {
        "packages": [
            {"id": lock.runtime_package, "archive_files": runtime_files},
            {"id": lock.wpf_package, "archive_files": wpf_files},
        ]
    }


def _write_output(root: Path, payloads: dict[str, bytes]) -> None:
    for relative, payload in payloads.items():
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def test_consumer_project_is_deterministic_and_package_reference_only() -> None:
    lock = load_lock(REPO_ROOT)

    first = consumer_project_files(lock, public_version())
    second = consumer_project_files(lock, public_version())

    assert first == second
    assert set(first) == {"TerminGraphicsNugetConsumer.csproj", "Program.cs"}
    project = first["TerminGraphicsNugetConsumer.csproj"]
    assert f"<TargetFramework>{lock.target_framework}</TargetFramework>" in project
    assert f"<RuntimeIdentifier>{lock.runtime_identifier}</RuntimeIdentifier>" in project
    assert "<PlatformTarget>x64</PlatformTarget>" in project
    assert "<TreatWarningsAsErrors>true</TreatWarningsAsErrors>" in project
    assert f'<PackageReference Include="{lock.wpf_package}"' in project
    assert "ProjectReference" not in project
    assert "HintPath" not in project
    assert "TerminSdkRoot" not in project
    program = first["Program.cs"]
    assert "new Chart2D(" in program
    assert "new RetainedScene2DHost" in program
    assert "sceneHost.FrameRendered" in program
    assert "sceneHost.RenderFailed" in program
    assert "BackendType.D3D11" in program
    assert "Timed out waiting for RetainedScene2DHost.FrameRendered" in program


def test_output_validation_records_exact_candidate_hashes(tmp_path: Path) -> None:
    lock = load_lock(REPO_ROOT)
    payloads = _output_payloads(lock)
    _write_output(tmp_path, payloads)

    records = validate_consumer_output(tmp_path, lock, _manifest(lock, payloads))

    by_path = {record["path"]: record for record in records}
    assert by_path["Termin.Native.dll"] == {
        "kind": "managed assembly",
        "path": "Termin.Native.dll",
        "package_path": f"lib/{lock.target_framework}/Termin.Native.dll",
        "sha256": _sha256(payloads["Termin.Native.dll"]),
        "size": len(payloads["Termin.Native.dll"]),
    }
    shader = f"share/termin/{lock.required_resources[0].as_posix()}"
    assert by_path[shader]["sha256"] == _sha256(payloads[shader])


def test_output_validation_accepts_nested_native_layout(tmp_path: Path) -> None:
    lock = load_lock(REPO_ROOT)
    payloads = _output_payloads(lock)
    _write_output(tmp_path, payloads)
    nested = tmp_path / "runtimes" / lock.runtime_identifier / "native"
    nested.mkdir(parents=True)
    library = "termin_graphics2.dll"
    (tmp_path / library).replace(nested / library)

    records = validate_consumer_output(tmp_path, lock, _manifest(lock, payloads))

    by_package_path = {record["package_path"]: record for record in records}
    package_path = f"runtimes/{lock.runtime_identifier}/native/{library}"
    assert by_package_path[package_path]["path"] == package_path


def test_output_validation_names_missing_native_library(tmp_path: Path) -> None:
    lock = load_lock(REPO_ROOT)
    payloads = _output_payloads(lock)
    missing = "termin_graphics2.dll"
    payloads.pop(missing)
    _write_output(tmp_path, payloads)
    complete_payloads = _output_payloads(lock)

    with pytest.raises(
        GraphicsNugetConsumerGateError,
        match=r"missing required native library: termin_graphics2\.dll",
    ):
        validate_consumer_output(
            tmp_path,
            lock,
            _manifest(lock, complete_payloads),
        )


def test_output_validation_names_missing_shader_resource(tmp_path: Path) -> None:
    lock = load_lock(REPO_ROOT)
    payloads = _output_payloads(lock)
    missing = f"share/termin/{lock.required_resources[-1].as_posix()}"
    payloads.pop(missing)
    _write_output(tmp_path, payloads)
    complete_payloads = _output_payloads(lock)

    with pytest.raises(
        GraphicsNugetConsumerGateError,
        match=f"missing required shader resource: {missing}",
    ):
        validate_consumer_output(
            tmp_path,
            lock,
            _manifest(lock, complete_payloads),
        )


def test_output_validation_rejects_payload_different_from_package(
    tmp_path: Path,
) -> None:
    lock = load_lock(REPO_ROOT)
    payloads = _output_payloads(lock)
    manifest = _manifest(lock, payloads)
    payloads["Termin.Wpf.dll"] = b"mutated after package extraction"
    _write_output(tmp_path, payloads)

    with pytest.raises(
        GraphicsNugetConsumerGateError,
        match="consumer output hash mismatch for managed assembly Termin.Wpf.dll",
    ):
        validate_consumer_output(tmp_path, lock, manifest)


def test_output_validation_rejects_undeclared_product_payload(tmp_path: Path) -> None:
    lock = load_lock(REPO_ROOT)
    payloads = _output_payloads(lock)
    _write_output(tmp_path, payloads)
    (tmp_path / "termin_unexpected.dll").write_bytes(b"unexpected native")

    with pytest.raises(
        GraphicsNugetConsumerGateError,
        match="native libraries absent from the candidate: termin_unexpected.dll",
    ):
        validate_consumer_output(tmp_path, lock, _manifest(lock, payloads))


def test_isolated_environment_scrubs_termin_and_checkout_paths(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    workspace = tmp_path / "external" / "consumer"
    clean_bin = tmp_path / "tools"
    base = {
        "PATH": os.pathsep.join([str(checkout / "sdk" / "bin"), str(clean_bin)]),
        "TERMIN_SDK_ROOT": str(checkout / "sdk"),
        "TERMIN_SHADER_ARTIFACT_ROOT": str(checkout / "sdk" / "share"),
        "CMAKE_PREFIX_PATH": str(checkout / "sdk"),
        "UNRELATED": "kept",
    }

    result = isolated_environment(
        base,
        workspace=workspace,
        prohibited_roots=(checkout,),
    )

    assert result["PATH"] == str(clean_bin)
    assert result["UNRELATED"] == "kept"
    assert "TERMIN_SDK_ROOT" not in result
    assert "TERMIN_SHADER_ARTIFACT_ROOT" not in result
    assert "CMAKE_PREFIX_PATH" not in result
    assert result["NUGET_PACKAGES"] == str(workspace / "packages")
    assert result["NUGET_PLUGINS_CACHE_PATH"] == str(
        workspace / "nuget-plugins-cache"
    )
