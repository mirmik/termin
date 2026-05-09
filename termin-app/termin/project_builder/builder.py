"""Public project build API."""

from __future__ import annotations

import json
from pathlib import Path

from termin.project_builder.manifest import BuildProjectResult
from termin.project_builder.scanner import ProjectScanner
from termin.project_builder.writer import ProjectBuildWriter


def build_project(
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path,
    copy_files: bool = True,
) -> BuildProjectResult:
    project_root_path = Path(project_root).resolve()
    output_dir_path = Path(output_dir).resolve()
    entry_scene_path = Path(entry_scene)

    scanner = ProjectScanner(
        project_root=project_root_path,
        entry_scene=entry_scene_path,
        output_dir=output_dir_path,
    )
    manifest = scanner.scan()

    writer = ProjectBuildWriter(
        project_root=project_root_path,
        output_dir=output_dir_path,
    )
    project_name = _read_project_name(project_root_path)
    build_json_path, manifest_json_path = writer.write(
        project_name=project_name,
        manifest=manifest,
        copy_files=copy_files,
    )

    return BuildProjectResult(
        output_dir=output_dir_path,
        build_json_path=build_json_path,
        manifest_json_path=manifest_json_path,
        manifest=manifest,
    )


def _read_project_name(project_root: Path) -> str:
    project_files = sorted(project_root.glob("*.terminproj"))
    if not project_files:
        return project_root.name

    project_file = project_files[0]
    try:
        with open(project_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return project_file.stem

    if not isinstance(data, dict):
        return project_file.stem

    name = data.get("name")
    if isinstance(name, str) and name != "":
        return name
    return project_file.stem
