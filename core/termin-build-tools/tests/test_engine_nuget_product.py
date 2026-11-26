from pathlib import Path
import shutil
import subprocess

import pytest

from termin_build.engine_nuget_product import _combine_shaders, EngineNugetError, pack
from termin_build.graphics_nuget_product import PACKAGE_OUTPUT_TARGETS, PackageDefinition, compose_package


REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("version", ["0.5.5", "../0.5.5-dev", "0.5.5-"])
def test_local_candidate_requires_prerelease_version(tmp_path, version):
    with pytest.raises(EngineNugetError, match="Invalid NuGet prerelease version"):
        pack(REPO, {}, tmp_path, prerelease_version=version)


def test_merge_refuses_different_shader_catalogs():
    linux = {"schema_version": 1, "catalog": "catalog.json", "catalog_sha256": "linux",
             "targets": ["vulkan"], "artifacts": []}
    windows = {**linux, "catalog_sha256": "windows", "targets": ["d3d11"]}
    with pytest.raises(EngineNugetError, match="different built-in shader catalogs"):
        _combine_shaders([linux, windows])


@pytest.mark.parametrize("transitive", [False, True])
def test_engine_package_reports_plot_profile_conflicts(tmp_path, transitive):
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        pytest.skip("conflict check requires the .NET SDK")

    feed = tmp_path / "feed"
    targets = (REPO / "termin-csharp/nuget/Termin.Engine.targets").read_bytes()

    def package(name, *, dependencies=(), files=None):
        compose_package(
            PackageDefinition(
                name, "Package graph test fixture", ("net8.0",), dependencies,
                {"LICENSE": b"Test fixture", "README.md": b"Test fixture", **(files or {})},
            ),
            feed, version="1.0.0", source_revision="", license_path="LICENSE",
        )

    package("Termin.Engine", files={
        "buildTransitive/net8.0/Termin.Engine.targets": targets,
        f"buildTransitive/net8.0/{PACKAGE_OUTPUT_TARGETS.name}": (REPO / PACKAGE_OUTPUT_TARGETS).read_bytes(),
    })
    package("Termin.Graphics")
    if transitive:
        package("EngineConflictFixture", dependencies=(("Termin.Graphics", "[1.0.0]"),))
    reference = "EngineConflictFixture" if transitive else "Termin.Graphics"
    project = tmp_path / "Consumer.csproj"
    project.write_text(
        '<Project Sdk="Microsoft.NET.Sdk">'
        '<PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>'
        '<ItemGroup><PackageReference Include="Termin.Engine" Version="[1.0.0]" />'
        f'<PackageReference Include="{reference}" Version="[1.0.0]" /></ItemGroup></Project>',
        encoding="utf-8",
    )

    restore = subprocess.run(
        [dotnet, "restore", project, "--source", feed, "--packages", tmp_path / "packages",
         "-p:NuGetAudit=false"],
        cwd=tmp_path, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
    )
    assert restore.returncode == 0, restore.stdout
    build = subprocess.run(
        [dotnet, "build", project, "--no-restore"], cwd=tmp_path, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
    )
    assert build.returncode != 0
    assert "error TERMIN001: Termin.Engine and Termin.Graphics" in build.stdout, build.stdout
