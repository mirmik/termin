"""Writers for project build artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tcbase import log
from termin.project.settings import ProjectSettings
from termin.project_builder.manifest import BuildDescription, ProjectBuildManifest


class ProjectBuildWriter:
    def __init__(self, project_root: Path, output_dir: Path) -> None:
        self.project_root = project_root.resolve()
        self.output_dir = output_dir.resolve()

    def write(
        self,
        project_name: str,
        manifest: ProjectBuildManifest,
        copy_files: bool,
    ) -> tuple[Path, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if copy_files:
            self._copy_manifest_files(manifest)

        manifest_path = self.output_dir / "assets" / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(manifest_path, manifest.to_dict())

        description = BuildDescription(
            project_name=project_name,
            entry_scene=manifest.entry_scene_build_path,
            asset_manifest="assets/manifest.json",
            runtime={"window": _load_project_settings(self.project_root).player_window.to_dict()},
        )
        build_json_path = self.output_dir / "build.json"
        self._write_json(build_json_path, description.to_dict())

        return build_json_path, manifest_path

    def _copy_manifest_files(self, manifest: ProjectBuildManifest) -> None:
        copied: set[str] = set()
        for resource in manifest.resources:
            if resource.kind == "generated":
                continue
            self._copy_file_once(resource.source_path, resource.build_path, copied)
            if resource.meta_path is not None and resource.meta_build_path is not None:
                self._copy_file_once(resource.meta_path, resource.meta_build_path, copied)

    def _copy_file_once(self, source_rel: str, build_rel: str, copied: set[str]) -> None:
        if build_rel in copied:
            return
        source_path = self.project_root / source_rel
        target_path = self.output_dir / build_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied.add(build_rel)

    def _write_json(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")


def _load_project_settings(project_root: Path) -> ProjectSettings:
    settings_path = project_root / "project_settings" / "project.json"
    if not settings_path.exists():
        return ProjectSettings()

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        log.error(f"[ProjectBuildWriter] Failed to read project settings: {exc}")
        return ProjectSettings()

    if not isinstance(data, dict):
        log.error("[ProjectBuildWriter] Project settings root must be an object")
        return ProjectSettings()
    return ProjectSettings.from_dict(data)
