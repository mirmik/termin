"""Desktop project build wrapper."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from termin.project_build.common import preload_project_resources, read_project_name
from termin.project_build.runtime_package_exporter import (
    RuntimePackageExportDiagnostic,
    RuntimePackageExportResult,
    export_runtime_package,
)


@dataclass
class DesktopBuildResult:
    dist_dir: Path
    package_result: RuntimePackageExportResult
    app_manifest_path: Path
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


def build_desktop_project(
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path | None = None,
    shader_compiler: str | Path | None = None,
    default_shader_language: str = "slang",
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

    app_manifest_path = dist_dir / "app.json"
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
                "python": {
                    "enabled": True,
                    "root": "python",
                    "project_modules": "package/python",
                },
                "native_library_dirs": [
                    "lib",
                ],
            },
            "entry": {
                "scene": "package/scene.json",
            },
        },
    )

    return DesktopBuildResult(
        dist_dir=dist_dir,
        package_result=package_result,
        app_manifest_path=app_manifest_path,
        diagnostics=list(package_result.diagnostics),
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
