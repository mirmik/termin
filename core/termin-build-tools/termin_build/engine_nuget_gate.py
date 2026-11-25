"""Verify the exact Termin.Engine package through a clean .NET consumer."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid
from xml.etree import ElementTree as ET
import zipfile

from .engine_nuget_product import (
    BACKENDS, FRAMEWORK, MANAGED, PACKAGE_ID, PACKAGE_MANIFEST, SHARE,
    EngineNugetError, digest, json_bytes,
)
from .graphics_nuget_publish import (
    ArchiveMember, GraphicsNugetReleaseCandidate, NugetPackageCandidate,
    DEFAULT_SERVICE_INDEX, NugetV3Client, publish_release,
)
from .versioning import public_version

SMOKE_MARKER = "AVALONIA_POSITIONER_SMOKE_OK"
PROJECT = "AvaloniaPositioner.csproj"
REPORT_KIND = "termin-engine-nuget-consumer"
FRAMEWORK_DEPENDENT = (
    "-p:SelfContained=false", "-p:UseAppHost=false",
    "-p:EnableRuntimePackDownload=false", "-p:EnableAppHostPackDownload=false",
)


def _manifest(package: Path) -> tuple[dict, str]:
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read(PACKAGE_MANIFEST))
        if manifest["kind"] != "termin-engine-nuget" or manifest["version"] != public_version():
            raise EngineNugetError(f"Unexpected product or version in {package}")
        if {stage["rid"]: stage["backend"] for stage in manifest["inputs"]} != BACKENDS:
            raise EngineNugetError(f"{package} is missing one of the supported native runtimes")
        for name, sha256 in manifest["files"].items():
            if digest(archive.read(name)) != sha256:
                raise EngineNugetError(f"{package} contains modified payload {name}")
    return manifest, digest(package.read_bytes())


def _consumer_project(repo: Path, directory: Path, version: str) -> None:
    sample = repo / "termin-csharp/examples/AvaloniaPositioner"
    for file in sample.glob("*.cs"):
        shutil.copy2(file, directory / file.name)
    project = ET.parse(sample / PROJECT)
    root = project.getroot()
    for group in root.findall("PropertyGroup"):
        for property_node in group.findall("TerminSdkRoot"):
            group.remove(property_node)
    group = next(group for group in root.findall("ItemGroup") if group.find("Reference") is not None)
    group.remove(group.find("Reference"))
    ET.SubElement(group, "PackageReference", Include=PACKAGE_ID, Version=f"[{version}]")
    project.write(directory / PROJECT, encoding="utf-8", xml_declaration=True)


def _nuget_config(path: Path, dependency_source: str, candidate: Path) -> None:
    config = ET.Element("configuration")
    sources = ET.SubElement(config, "packageSources")
    ET.SubElement(sources, "clear")
    ET.SubElement(sources, "add", key="candidate", value=str(candidate))
    ET.SubElement(sources, "add", key="deps", value=dependency_source)
    mappings = ET.SubElement(config, "packageSourceMapping")
    for key, pattern in (("candidate", PACKAGE_ID), ("deps", "*")):
        source = ET.SubElement(mappings, "packageSource", key=key)
        ET.SubElement(source, "package", pattern=pattern)
    ET.ElementTree(config).write(path, encoding="utf-8", xml_declaration=True)


def _output_files(manifest: dict, rid: str, output: Path) -> dict[str, str]:
    prefix = f"runtimes/{rid}/native/"
    managed = f"runtimes/{rid}/lib/{FRAMEWORK}/{MANAGED}"
    expected = {
        name.removeprefix(prefix): sha256
        for name, sha256 in manifest["files"].items()
        if name.startswith(prefix) or name.startswith(SHARE)
    }
    expected[MANAGED] = manifest["files"][managed]
    for name, sha256 in expected.items():
        file = output / name
        if not file.is_file() or digest(file.read_bytes()) != sha256:
            raise EngineNugetError(f"Publish output is missing or altered: {file}")
    other_rid = next(candidate for candidate in BACKENDS if candidate != rid)
    other_binding = "termin.dll" if other_rid == "win-x64" else "termin.so"
    if (output / other_binding).exists():
        raise EngineNugetError(f"Publish output contains the unselected native binding {other_binding}")
    return expected


def _isolated_environment(repo: Path) -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith("TERMIN_") and key not in {"LD_LIBRARY_PATH", "LD_PRELOAD"}
    }
    env["PATH"] = os.pathsep.join(
        path for path in env.get("PATH", "").split(os.pathsep)
        if path and not Path(path).resolve().is_relative_to(repo)
    )
    return env


def smoke_candidate(repo: Path, package: Path, work: Path, rid: str,
                    dependency_source: str, *, build_only: bool, run_only: bool) -> None:
    manifest, package_hash = _manifest(package)
    work.mkdir(parents=True, exist_ok=True)
    locator = work / "build.json"
    report = work / "report.json"
    report.unlink(missing_ok=True)
    env = _isolated_environment(repo)
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    if not run_only:
        # Use an isolated project and package cache so an identically versioned
        # package in the user's cache cannot mask a missing/faulty candidate.
        if os.name == "nt":
            # Inherit the user's TEMP ACL so an SSH build with an elevated
            # token can be tested later in the same user's desktop session.
            cache_root = Path(tempfile.gettempdir()) / f"termin-engine-consumer-{uuid.uuid4().hex}"
            cache_root.mkdir()
        else:
            cache_root = Path(tempfile.mkdtemp(prefix="termin-engine-consumer-"))
        consumer = cache_root / "src"
        consumer.mkdir()
        _consumer_project(repo, consumer, manifest["version"])
        feed = cache_root / "candidate"
        feed.mkdir()
        shutil.copy2(package, feed / package.name)
        config = cache_root / "NuGet.Config"
        _nuget_config(config, dependency_source, feed)
        command = ["dotnet", "restore", PROJECT, "-r", rid, "--packages", cache_root / "packages",
                   "--configfile", config, "-p:NuGetAudit=false", *FRAMEWORK_DEPENDENT]
        subprocess.run(command, cwd=consumer, env=env, check=True)
        output = cache_root / "publish"
        subprocess.run(
            ["dotnet", "publish", PROJECT, "-c", "Release", "-r", rid, "--no-restore",
             *FRAMEWORK_DEPENDENT, "-o", output],
            cwd=consumer, env=env, check=True,
        )
        _output_files(manifest, rid, output)
        locator.write_bytes(json_bytes({"package_sha256": package_hash, "rid": rid, "output": str(output)}))
        if build_only:
            return
    else:
        build = json.loads(locator.read_bytes())
        if build["package_sha256"] != package_hash or build["rid"] != rid:
            raise EngineNugetError("Built consumer does not match the selected package and RID")
        output = Path(build["output"])

    expected = _output_files(manifest, rid, output)
    with tempfile.TemporaryDirectory(prefix="termin-engine-run-") as unrelated:
        result = subprocess.run(
            ["dotnet", output / "AvaloniaPositioner.dll", "--smoke"],
            cwd=unrelated, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=120, check=False,
        )
    (work / "smoke.log").write_text(result.stdout, encoding="utf-8")
    print(result.stdout, end="")
    backend = f"AVALONIA_POSITIONER_BACKEND {'D3D11' if rid == 'win-x64' else 'Vulkan'}"
    if result.returncode != 0 or SMOKE_MARKER not in result.stdout or backend not in result.stdout:
        raise EngineNugetError(f"{rid} Avalonia consumer failed, exit code {result.returncode}")
    report.write_bytes(json_bytes({
        "kind": REPORT_KIND, "version": manifest["version"], "rid": rid,
        "backend": BACKENDS[rid], "package_sha256": package_hash, "passed": True,
        "publish_files": expected,
    }))


def publish_candidate(package: Path, reports: dict[str, Path], *, upload: bool) -> None:
    manifest, package_hash = _manifest(package)
    for rid, backend in BACKENDS.items():
        report = json.loads(reports[rid].read_bytes())
        confirmation = (report["kind"], report["version"], report["rid"], report["backend"],
                        report["package_sha256"], report["passed"])
        if confirmation != (REPORT_KIND, manifest["version"], rid, backend, package_hash, True):
            raise EngineNugetError(f"{rid} consumer report does not pass for this exact candidate")

    with zipfile.ZipFile(package) as archive:
        members = tuple(
            ArchiveMember(item.filename, digest(archive.read(item)), item.file_size)
            for item in archive.infolist()
        )
    source = manifest["inputs"][0]["revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise EngineNugetError("Release input provenance has an invalid Git revision")
    candidate = GraphicsNugetReleaseCandidate(
        root=package.parent, evidence_root=reports["linux-x64"].parent,
        version=manifest["version"], source_revision=source,
        packages=(NugetPackageCandidate(PACKAGE_ID, manifest["version"], package, package_hash,
                                       package.stat().st_size, members),),
    )
    publish_release(candidate, client=NugetV3Client(DEFAULT_SERVICE_INDEX),
                    upload=upload, api_key=os.environ.get("NUGET_API_KEY"))
