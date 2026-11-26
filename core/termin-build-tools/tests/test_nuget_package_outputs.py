from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

from termin_build.graphics_nuget_product import (
    PACKAGE_OUTPUT_TARGETS,
    PackageDefinition,
    _targets_payload,
    compose_package,
    load_lock,
)


REPO = Path(__file__).resolve().parents[3]
OLD_VERSION = "1.0.0"
NEW_VERSION = "1.0.1"
DLL_FIXTURES = ("Termin.Native", "Termin.Wpf")


def _run(workspace: Path, environment: dict[str, str], *command: str) -> None:
    result = subprocess.run(
        ["dotnet", *command], cwd=workspace, env=environment,
        capture_output=True, text=True, timeout=90, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="module")
def managed_dlls(tmp_path_factory: pytest.TempPathFactory) -> dict[str, tuple[bytes, bytes]]:
    workspace = tmp_path_factory.mktemp("nuget-output-fixtures")
    _configure_sdk(workspace)
    environment = _dotnet_environment(workspace)
    dlls = {}
    for assembly in DLL_FIXTURES:
        project = workspace / assembly
        project.mkdir()
        (project / f"{assembly}.csproj").write_text(
            "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup>"
            "<TargetFramework>net8.0</TargetFramework>"
            "</PropertyGroup></Project>",
            encoding="utf-8",
        )
        versions = []
        for value in ("A", "B"):
            (project / "Probe.cs").write_text(
                f'namespace {assembly}.Fixture; public class Probe {{ public string Value() => "{value}"; }}',
                encoding="utf-8",
            )
            _run(workspace, environment, "build", str(project), "--output", str(project / value))
            versions.append((project / value / f"{assembly}.dll").read_bytes())
        old, new = versions
        assert len(old) == len(new) and old != new
        dlls[assembly] = (old, new)
    return dlls


def _configure_sdk(workspace: Path) -> None:
    (workspace / "global.json").write_text(
        json.dumps({"sdk": {"version": "8.0.100", "rollForward": "major", "allowPrerelease": False}}),
        encoding="utf-8",
    )


def _dotnet_environment(workspace: Path) -> dict[str, str]:
    return {
        **os.environ,
        "DOTNET_CLI_HOME": str(workspace / "dotnet-home"),
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_NOLOGO": "1",
        "NUGET_PACKAGES": str(workspace / "packages"),
    }


@pytest.mark.skipif(os.name != "nt" or shutil.which("dotnet") is None, reason="requires the Windows .NET SDK")
@pytest.mark.parametrize("package_id,use_wpf", [
    ("Termin.Graphics", True),
    ("Termin.Graphics", False),
    ("Termin.Engine", False),
])
def test_incremental_build_and_publish_refresh_package_outputs(
    tmp_path: Path, managed_dlls: dict[str, tuple[bytes, bytes]], package_id: str, use_wpf: bool,
) -> None:
    _configure_sdk(tmp_path)
    environment = _dotnet_environment(tmp_path)
    feed = tmp_path / "feed"
    graphics = package_id == "Termin.Graphics"
    if graphics:
        lock = load_lock(REPO)
        framework = lock.runtime_framework
        targets = _targets_payload(lock)
        managed_path = "lib/netstandard2.1/Termin.Native.dll"
    else:
        framework = "net8.0"
        targets = (REPO / "termin-csharp/nuget/Termin.Engine.targets").read_bytes()
        managed_path = "runtimes/win-x64/lib/net8.0/Termin.Native.dll"

    prefix = f"buildTransitive/{framework}"
    wpf_path = "wpf/net8.0-windows7.0/Termin.Wpf.dll"
    native_path = "runtimes/win-x64/native/termin_fixture.dll"
    resource_path = "share/termin/output-test.txt"
    for index, version in enumerate((OLD_VERSION, NEW_VERSION)):
        native = (b"native-A", b"native-B")[index]
        resource = (b"resource-A", b"resource-B")[index]
        native_dll = managed_dlls["Termin.Native"][index]
        payloads = {
            "LICENSE": b"Test package",
            "README.md": b"Test package",
            managed_path: native_dll,
            native_path: native,
            resource_path: resource,
            f"{prefix}/{package_id}.targets": targets,
            f"{prefix}/{PACKAGE_OUTPUT_TARGETS.name}": (REPO / PACKAGE_OUTPUT_TARGETS).read_bytes(),
        }
        if graphics:
            payloads[wpf_path] = managed_dlls["Termin.Wpf"][index]
        else:
            payloads[f"ref/{framework}/Termin.Native.dll"] = native_dll
        if version == OLD_VERSION:
            del payloads[f"{prefix}/{PACKAGE_OUTPUT_TARGETS.name}"]
            payloads[f"{prefix}/{package_id}.targets"] = b"".join(
                line for line in targets.splitlines(keepends=True)
                if b'<Import Project="Termin.PackageOutputs.targets"' not in line
            )
            if graphics:
                payloads[f"{prefix}/{package_id}.targets"] = payloads[f"{prefix}/{package_id}.targets"].replace(
                    b'<Reference Include="$(MSBuildThisFileDirectory)',
                    b'<Reference Include="Termin.Wpf" HintPath="$(MSBuildThisFileDirectory)',
                )
        compose_package(
            PackageDefinition(
                package_id, "Copy test fixture", (framework,), (), payloads,
            ),
            feed, version=version, source_revision="", license_path="LICENSE",
        )

    project = tmp_path / "Consumer.csproj"
    runtime = "" if graphics else "<RuntimeIdentifier>win-x64</RuntimeIdentifier>"
    project.write_text(
        f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0-windows</TargetFramework>
    <UseWPF>{str(use_wpf).lower()}</UseWPF>
    <SelfContained>false</SelfContained>
    <UseAppHost>false</UseAppHost>
    {runtime}
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="{package_id}" Version="[$(FixtureVersion)]" />
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )
    (tmp_path / "Consumer.cs").write_text(
        "using Termin.Native.Fixture;\n"
        "public class Consumer { public static void Main() => System.Console.WriteLine(new Probe().Value()); }\n",
        encoding="utf-8",
    )

    build_output = tmp_path / "build"
    publish_output = tmp_path / "publish"
    for version in (OLD_VERSION, NEW_VERSION):
        version_arg = f"-p:FixtureVersion={version}"
        _run(tmp_path, environment, "restore", str(project), "--source", str(feed), version_arg)
        _run(tmp_path, environment, "build", str(project), "--no-restore", "--output", str(build_output), version_arg)
        _run(tmp_path, environment, "publish", str(project), "--no-restore", "--output", str(publish_output), version_arg)
        with zipfile.ZipFile(feed / f"{package_id}.{version}.nupkg") as archive:
            for output in (build_output, publish_output):
                paths = {
                    managed_path: output / "Termin.Native.dll",
                    native_path: output / (native_path if graphics else "termin_fixture.dll"),
                    resource_path: output / resource_path,
                }
                if use_wpf:
                    paths[wpf_path] = output / "Termin.Wpf.dll"
                else:
                    assert not (output / "Termin.Wpf.dll").exists()
                for member, file in paths.items():
                    assert hashlib.sha256(file.read_bytes()).digest() == hashlib.sha256(archive.read(member)).digest(), file
