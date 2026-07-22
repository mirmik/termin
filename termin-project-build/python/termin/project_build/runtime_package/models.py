"""Shared models for runtime package export."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RuntimePackageExportDiagnostic:
    level: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class RuntimePackageExportResult:
    package_dir: Path
    manifest_path: Path
    scene_path: Path
    scene_paths: dict[str, Path] = field(default_factory=dict)
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


@dataclass
class RuntimeRefs:
    meshes: dict[str, str] = field(default_factory=dict)
    materials: dict[str, str] = field(default_factory=dict)
    textures: dict[str, str] = field(default_factory=dict)
    pipelines: dict[str, str] = field(default_factory=dict)


@dataclass
class ShaderSpec:
    uuid: str
    name: str
    source_path: str
    vertex_source: str
    fragment_source: str
    language: str
    geometry_source: str = ""
    vertex_entry: str = "main"
    fragment_entry: str = "main"
    geometry_entry: str = "main"
    allow_precompiled_default: bool = False
    features: int = 0
