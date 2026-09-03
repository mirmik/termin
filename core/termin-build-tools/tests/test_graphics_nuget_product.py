from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from xml.etree import ElementTree
import zipfile

import pytest

from termin_build.graphics_nuget_product import (
    GraphicsNugetProductError,
    PRODUCT_MANIFEST,
    build_product,
    load_lock,
    validate_candidate,
)
from termin_build.versioning import public_version


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_REVISION = "1" * 40
VERSION = public_version()


def _write_file(root: Path, relative: Path | str, payload: bytes = b"payload") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _synthetic_sdk(tmp_path: Path) -> Path:
    sdk_prefix = tmp_path / "sdk-graphics"
    lock = load_lock(REPO_ROOT)
    _write_file(sdk_prefix, lock.runtime_assembly, b"managed-runtime")
    _write_file(sdk_prefix, lock.wpf_assembly, b"managed-wpf")
    for name in lock.required_native_libraries:
        _write_file(sdk_prefix, lock.native_runtime_root / name, name.encode("ascii"))
    _write_file(
        sdk_prefix,
        lock.native_runtime_root / "vcruntime140.dll",
        b"Microsoft runtime",
    )
    for relative in lock.required_resources:
        _write_file(sdk_prefix, lock.resource_root / relative, relative.as_posix().encode())
    _write_file(
        sdk_prefix,
        lock.resource_root / "shaders/d3d11/extra.ps.cso",
        b"extra shader",
    )
    return sdk_prefix


def _build(tmp_path: Path, name: str = "candidate") -> Path:
    sdk_prefix = _synthetic_sdk(tmp_path)
    return build_product(
        REPO_ROOT,
        sdk_prefix,
        tmp_path / name,
        source_revision=SOURCE_REVISION,
        source_dirty=False,
    )


def test_builds_two_package_candidate_with_exact_metadata(tmp_path: Path) -> None:
    candidate = _build(tmp_path)
    manifest = validate_candidate(REPO_ROOT, candidate)

    assert manifest["version"] == VERSION
    assert manifest["platform"] == "windows-x64"
    assert manifest["runtime_identifier"] == "win-x64"
    assert manifest["target_framework"] == "net8.0-windows7.0"
    assert manifest["csharp_profile"] == "plot-d3d11"
    assert manifest["source"] == {
        "repository": "https://github.com/mirmik/termin.git",
        "revision": SOURCE_REVISION,
        "dirty": False,
    }
    packages = {package["id"]: package for package in manifest["packages"]}
    assert set(packages) == {"Termin.Graphics", "Termin.Graphics.Wpf"}
    assert packages["Termin.Graphics"]["dependencies"] == []
    assert packages["Termin.Graphics.Wpf"]["dependencies"] == [
        {"id": "Termin.Graphics", "version": f"[{VERSION}]"}
    ]

    runtime_package = candidate / packages["Termin.Graphics"]["filename"]
    with zipfile.ZipFile(runtime_package) as archive:
        names = set(archive.namelist())
        assert "lib/net8.0-windows7.0/Termin.Native.dll" in names
        assert "runtimes/win-x64/native/termin.dll" in names
        assert "runtimes/win-x64/native/termin_graphics2.dll" in names
        assert "share/termin/builtin_shaders/engine-shader-catalog.json" in names
        assert "licenses/Termin/LICENSE" in names
        assert "licenses/Clipper2/LICENSE" in names
        assert "README.md" in names
        targets_name = (
            "buildTransitive/net8.0-windows7.0/Termin.Graphics.targets"
        )
        targets = archive.read(targets_name).decode("utf-8")
        ElementTree.fromstring(targets)
        assert "TerminGraphicsCopyShaderResources" in targets
        assert "$(OutDir)share\\termin" in targets
        nuspec = archive.read("Termin.Graphics.nuspec").decode("utf-8")
        assert "<id>Termin.Graphics</id>" in nuspec
        assert f"<version>{VERSION}</version>" in nuspec
        assert '<license type="file">licenses/Termin/LICENSE</license>' in nuspec
        assert "<readme>README.md</readme>" in nuspec
        assert f'commit="{SOURCE_REVISION}"' in nuspec
        assert "{{TERMIN_VERSION}}" not in archive.read("README.md").decode("utf-8")

    wpf_package = candidate / packages["Termin.Graphics.Wpf"]["filename"]
    with zipfile.ZipFile(wpf_package) as archive:
        names = set(archive.namelist())
        assert "lib/net8.0-windows7.0/Termin.Wpf.dll" in names
        assert not any(name.startswith("runtimes/") for name in names)
        nuspec = archive.read("Termin.Graphics.Wpf.nuspec").decode("utf-8")
        assert f'id="Termin.Graphics" version="[{VERSION}]"' in nuspec
        assert 'targetFramework="net8.0-windows7.0"' in nuspec


def test_candidate_bytes_are_deterministic(tmp_path: Path) -> None:
    sdk_prefix = _synthetic_sdk(tmp_path)
    first = build_product(
        REPO_ROOT,
        sdk_prefix,
        tmp_path / "first",
        source_revision=SOURCE_REVISION,
        source_dirty=False,
    )
    second = build_product(
        REPO_ROOT,
        sdk_prefix,
        tmp_path / "second",
        source_revision=SOURCE_REVISION,
        source_dirty=False,
    )

    first_files = {path.name: path.read_bytes() for path in first.iterdir()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir()}
    assert first_files == second_files


@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet is not installed")
def test_dotnet_can_restore_wpf_package_and_runtime_dependency(tmp_path: Path) -> None:
    candidate = _build(tmp_path)
    project = tmp_path / "consumer" / "Consumer.csproj"
    project.parent.mkdir()
    project.write_text(
        f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0-windows7.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Termin.Graphics.Wpf" Version="{VERSION}" />
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )
    packages = tmp_path / "packages"
    environment = {
        **os.environ,
        "DOTNET_CLI_HOME": str(tmp_path / "dotnet-home"),
        "DOTNET_NOLOGO": "1",
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "NUGET_PACKAGES": str(packages),
    }

    result = subprocess.run(
        [
            "dotnet",
            "restore",
            str(project),
            "--source",
            str(candidate),
            "--packages",
            str(packages),
            "--no-cache",
        ],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assets = json.loads(
        (project.parent / "obj/project.assets.json").read_text(encoding="utf-8")
    )
    assert f"Termin.Graphics/{VERSION}" in assets["libraries"]
    assert f"Termin.Graphics.Wpf/{VERSION}" in assets["libraries"]
    installed = packages / "termin.graphics" / VERSION
    assert (
        installed
        / "buildTransitive/net8.0-windows7.0/Termin.Graphics.targets"
    ).is_file()
    assert (installed / "runtimes/win-x64/native/termin_graphics2.dll").is_file()
    assert (
        packages
        / "termin.graphics.wpf"
        / VERSION
        / "lib/net8.0-windows7.0/Termin.Wpf.dll"
    ).is_file()


def test_rejects_missing_required_native_library(tmp_path: Path) -> None:
    sdk_prefix = _synthetic_sdk(tmp_path)
    lock = load_lock(REPO_ROOT)
    (sdk_prefix / lock.native_runtime_root / "termin_graphics2.dll").unlink()

    with pytest.raises(
        GraphicsNugetProductError,
        match="missing required libraries: termin_graphics2.dll",
    ):
        build_product(
            REPO_ROOT,
            sdk_prefix,
            tmp_path / "candidate",
            source_revision=SOURCE_REVISION,
            source_dirty=False,
        )


def test_rejects_full_profile_native_library(tmp_path: Path) -> None:
    sdk_prefix = _synthetic_sdk(tmp_path)
    lock = load_lock(REPO_ROOT)
    _write_file(
        sdk_prefix,
        lock.native_runtime_root / "termin_engine.dll",
        b"forbidden full profile",
    )

    with pytest.raises(
        GraphicsNugetProductError,
        match="libraries from the full C# profile: termin_engine.dll",
    ):
        build_product(
            REPO_ROOT,
            sdk_prefix,
            tmp_path / "candidate",
            source_revision=SOURCE_REVISION,
            source_dirty=False,
        )


def test_rejects_resource_symlink(tmp_path: Path) -> None:
    sdk_prefix = _synthetic_sdk(tmp_path)
    lock = load_lock(REPO_ROOT)
    target = _write_file(tmp_path, "external-shader.cso", b"outside")
    link = sdk_prefix / lock.resource_root / "shaders/d3d11/symlink.cso"
    link.symlink_to(target)

    with pytest.raises(GraphicsNugetProductError, match="contains a symlink"):
        build_product(
            REPO_ROOT,
            sdk_prefix,
            tmp_path / "candidate",
            source_revision=SOURCE_REVISION,
            source_dirty=False,
        )


def test_candidate_validation_rejects_archive_mutation(tmp_path: Path) -> None:
    candidate = _build(tmp_path)
    manifest = json.loads((candidate / PRODUCT_MANIFEST).read_text(encoding="utf-8"))
    package = candidate / manifest["packages"][0]["filename"]
    with package.open("ab") as stream:
        stream.write(b"mutation")

    with pytest.raises(GraphicsNugetProductError, match="package hash mismatch"):
        validate_candidate(REPO_ROOT, candidate)


def test_candidate_validation_rejects_manifest_contract_mutation(
    tmp_path: Path,
) -> None:
    candidate = _build(tmp_path)
    manifest_path = candidate / PRODUCT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["packages"][0]["id"] = "Termin.NotGraphics"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(GraphicsNugetProductError, match="package identity set mismatch"):
        validate_candidate(REPO_ROOT, candidate)
