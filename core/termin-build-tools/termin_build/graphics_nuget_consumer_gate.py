"""Exercise a Termin Graphics NuGet candidate from an isolated WPF consumer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import uuid
from xml.sax.saxutils import quoteattr

from .graphics_nuget_product import (
    GraphicsNugetLock,
    PRODUCT_MANIFEST,
    load_lock,
    validate_candidate,
)


REPORT_NAME = "termin-graphics-nuget-consumer-report.json"
REPORT_KIND = "termin-graphics-nuget-consumer-gate"
REPORT_SCHEMA = 1
SMOKE_MARKER = "TERMIN_GRAPHICS_NUGET_SMOKE="


class GraphicsNugetConsumerGateError(RuntimeError):
    """The isolated PackageReference consumer did not pass its contract."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def consumer_project_files(lock: GraphicsNugetLock, version: str) -> dict[str, str]:
    """Return the deterministic sources for the clean consumer project."""
    project = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>{lock.target_framework}</TargetFramework>
    <RuntimeIdentifier>{lock.runtime_identifier}</RuntimeIdentifier>
    <SelfContained>false</SelfContained>
    <PlatformTarget>x64</PlatformTarget>
    <UseWPF>true</UseWPF>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <Deterministic>true</Deterministic>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="{lock.wpf_package}" Version="{version}" />
  </ItemGroup>
</Project>
"""
    program = f'''using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Windows;
using System.Windows.Threading;
using Termin.Native;
using Termin.Wpf;

internal static class Program
{{
    private const string Marker = "{SMOKE_MARKER}";

    [STAThread]
    private static int Main()
    {{
        string output = AppContext.BaseDirectory;
        RequireFile(Path.Combine(output, "Termin.Native.dll"));
        RequireFile(Path.Combine(output, "Termin.Wpf.dll"));
        RequireFile(Path.Combine(
            output, "share", "termin", "builtin_shaders",
            "engine-shader-catalog.json"));
        RequireFile(Path.Combine(
            output, "share", "termin", "shaders", "d3d11",
            "termin-engine-tcplot-3d.vs.cso"));
        RequireFile(Path.Combine(
            output, "share", "termin", "shaders", "d3d11",
            "termin-engine-text3d.vs.cso"));

        string font = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Fonts),
            "segoeui.ttf");
        RequireFile(font);

        int exitCode = 1;
        string? failure = null;
        GpuHost? gpuHost = null;
        Chart2D? chart = null;
        RetainedScene2DHost? sceneHost = null;
        var app = new Application {{ ShutdownMode = ShutdownMode.OnExplicitShutdown }};
        var window = new Window
        {{
            Title = "Termin Graphics NuGet consumer smoke",
            Width = 640,
            Height = 400,
            ShowInTaskbar = false,
            WindowStartupLocation = WindowStartupLocation.CenterScreen,
        }};
        var timeout = new DispatcherTimer {{ Interval = TimeSpan.FromSeconds(20) }};

        try
        {{
            gpuHost = Tgfx2Host.Acquire(font, BackendType.D3D11);
            chart = new Chart2D(
                gpuHost,
                640,
                400,
                new PlotRange2D(0, 4, -1.2, 1.2));
            chart.TitleText = "NuGet retained chart";
            ChartLineSeries2D line = chart.AddLineSeries(
                "signal",
                new[] {{ 0.0, 1.0, 2.0, 3.0, 4.0 }},
                new[] {{ 0.0, 0.8, -0.4, 1.0, 0.0 }});
            if (!line.IsValid || line.Item.Snapshot.PointCount != 5)
                throw new InvalidOperationException(
                    "Retained chart series did not reach the native scene.");

            sceneHost = new RetainedScene2DHost {{ ContinuousRendering = false }};
            sceneHost.FramebufferChanged += (_, e) =>
                chart.Resize(e.Width, e.Height, e.PixelScale);
            sceneHost.RenderFailed += (_, e) =>
            {{
                failure = "WPF retained render failed: " + e.Error;
                app.Dispatcher.BeginInvoke(app.Shutdown);
            }};
            sceneHost.FrameRendered += (_, e) =>
            {{
                exitCode = 0;
                string nativeModule = Process.GetCurrentProcess().Modules
                    .Cast<ProcessModule>()
                    .Single(module => string.Equals(
                        module.ModuleName,
                        "termin_graphics2.dll",
                        StringComparison.OrdinalIgnoreCase))
                    .FileName;
                Console.WriteLine(Marker + JsonSerializer.Serialize(new
                {{
                    status = "passed",
                    backend = "D3D11",
                    wpf = true,
                    retainedSceneId = chart.Scene.Id,
                    retainedItemCount = checked((ulong)chart.Scene.Count),
                    pointCount = checked((ulong)line.Item.Snapshot.PointCount),
                    nativeTotalMilliseconds = e.Native.TotalMilliseconds,
                    presentMilliseconds = e.PresentMilliseconds,
                    appContextBaseDirectory = output,
                    managedAssemblyRoot = Path.GetDirectoryName(
                        typeof(GpuHost).Assembly.Location),
                    wpfAssemblyRoot = Path.GetDirectoryName(
                        typeof(RetainedScene2DHost).Assembly.Location),
                    nativeModuleRoot = Path.GetDirectoryName(nativeModule),
                    resourceRoot = Path.Combine(output, "share", "termin"),
                }}));
                app.Dispatcher.BeginInvoke(app.Shutdown);
            }};
            sceneHost.Attach(gpuHost, chart.Scene);
            window.Content = sceneHost;
            timeout.Tick += (_, _) =>
            {{
                failure = "Timed out waiting for RetainedScene2DHost.FrameRendered.";
                app.Shutdown();
            }};
            timeout.Start();
            window.Show();
            app.Run();
        }}
        catch (Exception error)
        {{
            failure = error.ToString();
        }}
        finally
        {{
            timeout.Stop();
            window.Close();
            sceneHost?.Dispose();
            chart?.Dispose();
            if (gpuHost is not null)
                Tgfx2Host.Release();
        }}

        if (failure is not null)
            Console.Error.WriteLine(failure);
        return exitCode;
    }}

    private static void RequireFile(string path)
    {{
        if (!File.Exists(path))
            throw new FileNotFoundException(
                "NuGet consumer runtime payload is missing.", path);
    }}
}}
'''
    return {
        "TerminGraphicsNugetConsumer.csproj": project,
        "Program.cs": program,
    }


def _write_consumer_project(
    project_root: Path,
    lock: GraphicsNugetLock,
    version: str,
) -> Path:
    project_root.mkdir(parents=True)
    for relative, payload in consumer_project_files(lock, version).items():
        (project_root / relative).write_text(payload, encoding="utf-8", newline="\n")
    return project_root / "TerminGraphicsNugetConsumer.csproj"


def _nuget_config(feed: Path) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<configuration>\n"
        "  <packageSources>\n"
        "    <clear />\n"
        f"    <add key=\"isolated-candidate\" value={quoteattr(str(feed))} />\n"
        "  </packageSources>\n"
        "  <disabledPackageSources>\n"
        "    <clear />\n"
        "  </disabledPackageSources>\n"
        "</configuration>\n"
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _path_tokens(path: Path) -> tuple[str, ...]:
    resolved = str(path.resolve())
    variants = {resolved, resolved.replace("\\", "/")}
    return tuple(sorted((item.casefold() for item in variants), key=len, reverse=True))


def _contains_path(value: str, roots: tuple[Path, ...]) -> bool:
    folded = value.casefold()
    slash_folded = value.replace("\\", "/").casefold()
    return any(
        token in folded or token in slash_folded
        for root in roots
        for token in _path_tokens(root)
    )


def isolated_environment(
    base: dict[str, str],
    *,
    workspace: Path,
    prohibited_roots: tuple[Path, ...],
) -> dict[str, str]:
    """Remove repository/SDK configuration and install isolated .NET homes."""
    result: dict[str, str] = {}
    for name, value in base.items():
        folded_name = name.casefold()
        if folded_name.startswith("termin") or folded_name.startswith("nuget_"):
            continue
        if folded_name in {"cmake_prefix_path", "cmake_install_prefix"}:
            continue
        if _contains_path(value, prohibited_roots):
            if folded_name == "path":
                clean_entries = [
                    entry
                    for entry in value.split(os.pathsep)
                    if entry and not _contains_path(entry, prohibited_roots)
                ]
                result[name] = os.pathsep.join(clean_entries)
            continue
        result[name] = value
    result.update(
        {
            "DOTNET_CLI_HOME": str(workspace / "dotnet-home"),
            "DOTNET_NOLOGO": "1",
            "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "NUGET_PACKAGES": str(workspace / "packages"),
            "NUGET_HTTP_CACHE_PATH": str(workspace / "nuget-http-cache"),
            "NUGET_PLUGINS_CACHE_PATH": str(workspace / "nuget-plugins-cache"),
        }
    )
    return result


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    log: Path,
    timeout_seconds: int,
) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
        output = result.stdout
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        log.write_text(output, encoding="utf-8", newline="\n")
        raise GraphicsNugetConsumerGateError(
            f"command timed out after {timeout_seconds}s; see {log.name}"
        ) from error
    log.write_text(output, encoding="utf-8", newline="\n")
    if result.returncode != 0:
        output_tail = "\n".join(output.splitlines()[-40:]).strip()
        detail = f"\ncommand output tail:\n{output_tail}" if output_tail else ""
        raise GraphicsNugetConsumerGateError(
            f"command failed with exit code {result.returncode}; see {log.name}{detail}"
        )
    return output


def validate_consumer_output(
    output_root: Path,
    lock: GraphicsNugetLock,
    manifest: dict[str, object],
) -> list[dict[str, object]]:
    """Validate and describe the package payload copied to consumer output."""
    managed_package_paths = {
        "Termin.Native.dll": f"lib/{lock.target_framework}/Termin.Native.dll",
        "Termin.Wpf.dll": f"lib/{lock.target_framework}/Termin.Wpf.dll",
    }
    native_prefix = f"runtimes/{lock.runtime_identifier}/native/"
    resource_prefix = "share/termin/"
    package_payloads: dict[str, tuple[str, str]] = {}
    raw_packages = manifest.get("packages")
    if not isinstance(raw_packages, list):
        raise GraphicsNugetConsumerGateError("candidate manifest package list is invalid")
    for raw_package in raw_packages:
        if not isinstance(raw_package, dict):
            raise GraphicsNugetConsumerGateError("candidate package record is invalid")
        raw_archive_files = raw_package.get("archive_files")
        if not isinstance(raw_archive_files, list):
            raise GraphicsNugetConsumerGateError(
                "candidate package archive manifest is invalid"
            )
        for raw_file in raw_archive_files:
            if (
                not isinstance(raw_file, dict)
                or not isinstance(raw_file.get("path"), str)
                or not isinstance(raw_file.get("sha256"), str)
            ):
                raise GraphicsNugetConsumerGateError(
                    "candidate package archive file record is invalid"
                )
            archive_path = raw_file["path"]
            archive_hash = raw_file["sha256"]
            kind: str | None = None
            output_key: str | None = None
            for managed_name, managed_path in managed_package_paths.items():
                if archive_path == managed_path:
                    kind = "managed assembly"
                    output_key = managed_name
                    break
            if archive_path.startswith(native_prefix):
                kind = "native library"
                output_key = PurePosixPath(archive_path).name
            elif archive_path.startswith(resource_prefix):
                kind = "shader resource"
                output_key = archive_path
            if kind is None or output_key is None:
                continue
            previous = package_payloads.setdefault(
                output_key,
                (kind, archive_hash),
            )
            if previous != (kind, archive_hash):
                raise GraphicsNugetConsumerGateError(
                    f"candidate archives disagree on payload: {output_key}"
                )

    expected_managed = set(managed_package_paths)
    expected_native = {
        key for key, (kind, _) in package_payloads.items() if kind == "native library"
    }
    expected_resources = {
        key for key, (kind, _) in package_payloads.items() if kind == "shader resource"
    }
    missing_managed = sorted(expected_managed - package_payloads.keys())
    if missing_managed:
        raise GraphicsNugetConsumerGateError(
            "candidate manifest is missing managed assemblies: "
            + ", ".join(missing_managed)
        )
    missing_required_native = sorted(
        set(lock.required_native_libraries) - expected_native
    )
    if missing_required_native:
        raise GraphicsNugetConsumerGateError(
            "candidate manifest is missing required native libraries: "
            + ", ".join(missing_required_native)
        )
    required_resources = {
        f"share/termin/{relative.as_posix()}" for relative in lock.required_resources
    }
    missing_required_resources = sorted(required_resources - expected_resources)
    if missing_required_resources:
        raise GraphicsNugetConsumerGateError(
            "candidate manifest is missing required shader resources: "
            + ", ".join(missing_required_resources)
        )

    native_matches: dict[str, list[Path]] = {
        name: sorted(
            path
            for path in output_root.rglob(name)
            if path.is_file() and path.name.casefold() == name.casefold()
        )
        for name in expected_native
    }
    records: list[dict[str, object]] = []
    for output_key, (kind, expected_hash) in sorted(package_payloads.items()):
        if kind == "native library":
            matches = native_matches[output_key]
            if not matches:
                raise GraphicsNugetConsumerGateError(
                    f"consumer output is missing required {kind}: {output_key}"
                )
            if len(matches) != 1:
                raise GraphicsNugetConsumerGateError(
                    f"consumer output contains duplicate {kind} {output_key}: "
                    + ", ".join(
                        path.relative_to(output_root).as_posix() for path in matches
                    )
                )
            path = matches[0]
        else:
            relative = PurePosixPath(output_key)
            path = output_root.joinpath(*relative.parts)
        if not path.is_file():
            raise GraphicsNugetConsumerGateError(
                f"consumer output is missing required {kind}: {output_key}"
            )
        actual_hash = _sha256_file(path)
        if actual_hash != expected_hash:
            raise GraphicsNugetConsumerGateError(
                f"consumer output hash mismatch for {kind} {output_key}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        relative_path = path.relative_to(output_root).as_posix()
        package_path = (
            managed_package_paths[output_key]
            if kind == "managed assembly"
            else output_key
        )
        if kind == "native library":
            package_path = f"{native_prefix}{output_key}"
        records.append(
            {
                "kind": kind,
                "path": relative_path,
                "package_path": package_path,
                "sha256": actual_hash,
                "size": path.stat().st_size,
            }
        )

    actual_product_native = {
        path.name
        for path in output_root.rglob("*.dll")
        if path.is_file()
        and (
            path.name.casefold() == "termin.dll"
            or path.name.casefold().startswith("termin_")
            or path.name.casefold().startswith("tcplot")
        )
    }
    unexpected_native = sorted(actual_product_native - expected_native)
    if unexpected_native:
        raise GraphicsNugetConsumerGateError(
            "consumer output contains native libraries absent from the candidate: "
            + ", ".join(unexpected_native)
        )
    actual_resources = {
        path.relative_to(output_root).as_posix()
        for path in (output_root / "share" / "termin").rglob("*")
        if path.is_file()
    }
    unexpected_resources = sorted(actual_resources - expected_resources)
    if unexpected_resources:
        raise GraphicsNugetConsumerGateError(
            "consumer output contains shader resources absent from the candidate: "
            + ", ".join(unexpected_resources)
        )
    return sorted(records, key=lambda item: str(item["path"]))


def _checkout_leaks(root: Path, prohibited_roots: tuple[Path, ...]) -> list[str]:
    text_suffixes = {
        ".config",
        ".cs",
        ".csproj",
        ".json",
        ".log",
        ".props",
        ".targets",
        ".txt",
        ".xml",
    }
    leaks: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in text_suffixes:
            continue
        try:
            payload = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if _contains_path(payload, prohibited_roots):
            leaks.append(path.relative_to(root).as_posix())
    return leaks


def _parse_smoke_evidence(output: str) -> dict[str, object]:
    matches = [
        line.removeprefix(SMOKE_MARKER)
        for line in output.splitlines()
        if line.startswith(SMOKE_MARKER)
    ]
    if len(matches) != 1:
        raise GraphicsNugetConsumerGateError(
            "consumer did not emit exactly one retained WPF smoke evidence record"
        )
    try:
        evidence = json.loads(matches[0])
    except json.JSONDecodeError as error:
        raise GraphicsNugetConsumerGateError(
            f"consumer emitted invalid smoke evidence: {error}"
        ) from error
    if not isinstance(evidence, dict) or evidence.get("status") != "passed":
        raise GraphicsNugetConsumerGateError(
            f"consumer smoke evidence does not report success: {evidence!r}"
        )
    app_root_value = evidence.get("appContextBaseDirectory")
    if not isinstance(app_root_value, str) or not app_root_value:
        raise GraphicsNugetConsumerGateError(
            "consumer smoke evidence has no AppContext base directory"
        )
    app_root = Path(app_root_value).resolve()
    exact_roots = {
        "managedAssemblyRoot": app_root,
        "wpfAssemblyRoot": app_root,
        "resourceRoot": app_root / "share" / "termin",
    }
    relative_roots: dict[str, str] = {}
    for name, expected in exact_roots.items():
        value = evidence.get(name)
        if not isinstance(value, str) or Path(value).resolve() != expected.resolve():
            raise GraphicsNugetConsumerGateError(
                f"consumer loaded {name} outside AppContext output: {value!r}"
            )
        relative_roots[name] = (
            "." if expected == app_root else expected.relative_to(app_root).as_posix()
        )
    native_root_value = evidence.get("nativeModuleRoot")
    if not isinstance(native_root_value, str):
        raise GraphicsNugetConsumerGateError(
            "consumer smoke evidence has no native module root"
        )
    native_root = Path(native_root_value).resolve()
    if not _is_within(native_root, app_root):
        raise GraphicsNugetConsumerGateError(
            f"consumer loaded nativeModuleRoot outside AppContext output: {native_root_value!r}"
        )
    relative_roots["nativeModuleRoot"] = (
        "." if native_root == app_root else native_root.relative_to(app_root).as_posix()
    )
    for name in ("appContextBaseDirectory", *exact_roots, "nativeModuleRoot"):
        evidence.pop(name, None)
    evidence["runtime_roots"] = relative_roots
    return evidence


def _publish_evidence(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.new-{uuid.uuid4().hex}"
    backup = destination.parent / f".{destination.name}.old-{uuid.uuid4().hex}"
    shutil.copytree(source, temporary)
    had_destination = destination.exists()
    if had_destination:
        destination.replace(backup)
    try:
        temporary.replace(destination)
    except Exception:
        if had_destination:
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def run_consumer_gate(repo_root: Path, candidate: Path, output_dir: Path) -> Path:
    """Restore, build, and execute a candidate solely through PackageReference."""
    if os.name != "nt":
        raise GraphicsNugetConsumerGateError(
            "Termin Graphics NuGet consumer gate requires Windows"
        )
    repo_root = repo_root.resolve()
    candidate = candidate.resolve()
    output_dir = output_dir.resolve()
    lock = load_lock(repo_root)
    manifest = validate_candidate(repo_root, candidate)
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise GraphicsNugetConsumerGateError("candidate manifest has no version")
    dotnet_text = shutil.which("dotnet")
    if dotnet_text is None:
        raise GraphicsNugetConsumerGateError("dotnet executable was not found in PATH")
    dotnet = Path(dotnet_text).resolve()
    prohibited_roots = (repo_root, repo_root / "sdk", repo_root / "sdk-graphics")
    if any(_is_within(dotnet, root) for root in prohibited_roots):
        raise GraphicsNugetConsumerGateError(
            "dotnet executable must not come from the Termin checkout or SDK"
        )

    with tempfile.TemporaryDirectory(prefix="termin-graphics-nuget-consumer.") as temp:
        workspace = Path(temp).resolve()
        if any(_is_within(workspace, root) for root in prohibited_roots):
            raise GraphicsNugetConsumerGateError(
                "temporary consumer workspace must be outside the Termin checkout"
            )
        feed = workspace / "feed"
        project_root = workspace / "consumer"
        results = workspace / "evidence"
        app_output = workspace / "app-output"
        feed.mkdir()
        results.mkdir()
        shutil.copy2(candidate / PRODUCT_MANIFEST, results / "candidate-manifest.json")
        for package in manifest["packages"]:
            if not isinstance(package, dict) or not isinstance(package.get("filename"), str):
                raise GraphicsNugetConsumerGateError("candidate package record is invalid")
            shutil.copy2(candidate / package["filename"], feed / package["filename"])
        project = _write_consumer_project(project_root, lock, version)
        config = workspace / "NuGet.config"
        config.write_text(_nuget_config(feed), encoding="utf-8", newline="\n")
        environment = isolated_environment(
            dict(os.environ),
            workspace=workspace,
            prohibited_roots=prohibited_roots,
        )

        status = "failed"
        failure: str | None = None
        output_records: list[dict[str, object]] = []
        smoke: dict[str, object] | None = None
        try:
            _run_command(
                [
                    str(dotnet),
                    "restore",
                    str(project),
                    "--configfile",
                    str(config),
                    "--packages",
                    str(workspace / "packages"),
                    "--no-cache",
                    "--force-evaluate",
                ],
                cwd=project_root,
                environment=environment,
                log=results / "restore.log",
                timeout_seconds=300,
            )
            _run_command(
                [
                    str(dotnet),
                    "build",
                    str(project),
                    "--configuration",
                    "Release",
                    "--runtime",
                    lock.runtime_identifier,
                    "--no-restore",
                    "--output",
                    str(app_output),
                ],
                cwd=project_root,
                environment=environment,
                log=results / "build.log",
                timeout_seconds=600,
            )
            output_records = validate_consumer_output(app_output, lock, manifest)
            run_output = _run_command(
                [str(dotnet), str(app_output / "TerminGraphicsNugetConsumer.dll")],
                cwd=app_output,
                environment=environment,
                log=results / "run.log",
                timeout_seconds=45,
            )
            smoke = _parse_smoke_evidence(run_output)
            leaks = _checkout_leaks(workspace, prohibited_roots)
            if leaks:
                raise GraphicsNugetConsumerGateError(
                    "consumer artifacts contain Termin checkout/SDK path leakage: "
                    + ", ".join(leaks)
                )
            status = "passed"
        except (GraphicsNugetConsumerGateError, OSError, subprocess.SubprocessError) as error:
            failure = str(error)
        report = {
            "schema": REPORT_SCHEMA,
            "report_kind": REPORT_KIND,
            "status": status,
            "product": manifest.get("product"),
            "version": version,
            "platform": lock.platform,
            "runtime_identifier": lock.runtime_identifier,
            "target_framework": lock.target_framework,
            "candidate_manifest": {
                "filename": "candidate-manifest.json",
                "sha256": _sha256_file(results / "candidate-manifest.json"),
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
            "consumer_output": output_records,
            "smoke": smoke,
            "logs": sorted(path.name for path in results.glob("*.log")),
            "failure": failure,
        }
        (results / REPORT_NAME).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _publish_evidence(results, output_dir)
        if failure is not None:
            raise GraphicsNugetConsumerGateError(failure)
    print(f"Termin Graphics NuGet consumer gate passed; evidence: {output_dir}")
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        run_consumer_gate(args.repo_root, args.candidate, args.output_dir)
        return 0
    except (GraphicsNugetConsumerGateError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: Termin Graphics NuGet consumer gate failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
