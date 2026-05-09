"""Build manifest data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


FORMAT_VERSION = 1


@dataclass
class BuildDiagnostic:
    level: str
    path: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class BuildResource:
    kind: str
    type: str
    source_path: str
    build_path: str
    uuid: str | None = None
    name: str | None = None
    meta_path: str | None = None
    meta_build_path: str | None = None
    size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "type": self.type,
            "uuid": self.uuid,
            "name": self.name,
            "source_path": self.source_path,
            "build_path": self.build_path,
            "meta_path": self.meta_path,
            "meta_build_path": self.meta_build_path,
            "size": self.size,
        }


@dataclass
class ProjectBuildManifest:
    project_root: str
    entry_scene: str
    entry_scene_build_path: str
    resources: list[BuildResource] = field(default_factory=list)
    diagnostics: list[BuildDiagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": FORMAT_VERSION,
            "project_root": self.project_root,
            "entry_scene": self.entry_scene,
            "entry_scene_build_path": self.entry_scene_build_path,
            "resources": [resource.to_dict() for resource in self.resources],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


@dataclass
class BuildDescription:
    project_name: str
    entry_scene: str
    asset_manifest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": FORMAT_VERSION,
            "project_name": self.project_name,
            "entry_scene": self.entry_scene,
            "asset_manifest": self.asset_manifest,
        }


@dataclass
class BuildProjectResult:
    output_dir: Path
    build_json_path: Path
    manifest_json_path: Path
    manifest: ProjectBuildManifest

