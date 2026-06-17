"""Desktop project build wrapper."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from termin.project_build.common import preload_project_resources, read_project_name
from termin.project_build.desktop_runtime_packager import (
    DesktopRuntimeBundleResult,
    package_desktop_runtime,
)
from termin.project_build.python_module_packager import PythonModuleBundleResult, package_python_modules
from termin.project_build.runtime_package_exporter import (
    RuntimePackageExportDiagnostic,
    RuntimePackageExportResult,
    export_runtime_package,
)


@dataclass
class DesktopBuildResult:
    dist_dir: Path
    package_result: RuntimePackageExportResult
    python_result: PythonModuleBundleResult
    runtime_result: DesktopRuntimeBundleResult
    app_manifest_path: Path
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


def build_desktop_project(
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path | None = None,
    shader_compiler: str | Path | None = None,
    default_shader_language: str = "slang",
    sdk_root: str | Path | None = None,
) -> DesktopBuildResult:
    project_root_path = Path(project_root).resolve()
    project_name = read_project_name(project_root_path)
    dist_dir = _resolve_dist_dir(project_root_path, project_name, output_dir)
    _prepare_dist_dir(project_root_path, dist_dir)

    package_dir = dist_dir / "package"

    preload_project_resources(project_root_path, "[DesktopBuild]")

    package_result = export_runtime_package(
        project_root=project_root_path,
        entry_scene=entry_scene,
        output_dir=package_dir,
        shader_compiler=shader_compiler,
        default_shader_language=default_shader_language,
    )
    python_result = package_python_modules(
        project_root=project_root_path,
        output_dir=package_dir / "python",
    )
    runtime_result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=[
            requirement
            for module in python_result.modules
            for requirement in module.requirements
        ],
        sdk_root=sdk_root,
    )

    app_manifest_path = dist_dir / "app.json"
    python_descriptors = [
        f"package/python/{module.descriptor}"
        for module in python_result.modules
    ]
    _write_app_manifest(
        app_manifest_path,
        {
            "version": 1,
            "format": "termin.desktop_bundle",
            "target": "desktop",
            "project_name": project_name,
            "package": {
                "root": "package",
                "manifest": "package/manifest.json",
                "scene": "package/scene.json",
            },
            "runtime": {
                "launcher": "bin/termin_player",
                "python": {
                    "enabled": bool(python_result.modules),
                    "home": (
                        f"lib/{runtime_result.python_home.name}"
                        if runtime_result.python_home is not None
                        else ""
                    ),
                    "project_modules": "package/python",
                    "module_manifest": "package/python/modules.json",
                    "descriptors": python_descriptors,
                },
                "native_library_dirs": [
                    "lib",
                ],
                "mcp": {
                    "enabled": False,
                    "host": "127.0.0.1",
                    "port": 8766,
                    "session_file": "/tmp/termin-player-mcp.json",
                },
            },
            "entry": {
                "scene": "package/scene.json",
            },
        },
    )

    return DesktopBuildResult(
        dist_dir=dist_dir,
        package_result=package_result,
        python_result=python_result,
        runtime_result=runtime_result,
        app_manifest_path=app_manifest_path,
        diagnostics=[
            *package_result.diagnostics,
            *python_result.diagnostics,
            *runtime_result.diagnostics,
        ],
    )


def _resolve_dist_dir(project_root: Path, project_name: str, output_dir: str | Path | None) -> Path:
    if output_dir is not None:
        return Path(output_dir).resolve()
    return (project_root / "dist" / "desktop" / project_name).resolve()


def _prepare_dist_dir(project_root: Path, dist_dir: Path) -> None:
    if dist_dir == project_root:
        raise ValueError(f"Refusing to use project root as desktop build output: {dist_dir}")
    if project_root in dist_dir.parents:
        rel = dist_dir.relative_to(project_root)
        if rel.parts and rel.parts[0] == "dist":
            _replace_dir(dist_dir)
            return

    if not dist_dir.exists():
        dist_dir.mkdir(parents=True, exist_ok=True)
        return

    if (dist_dir / "app.json").exists() or (dist_dir / "package").exists():
        _replace_dir(dist_dir)
        return

    if any(dist_dir.iterdir()):
        raise ValueError(
            "Refusing to clean non-generated desktop build output directory: "
            f"{dist_dir}. Use a project dist/... path or an empty directory."
        )
    _replace_dir(dist_dir)


def _replace_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _write_app_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
