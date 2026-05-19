"""Project filesystem scanner for build manifests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from termin.assets.default_plugins import (
    build_import_plugin_extension_map,
    register_default_import_asset_plugins,
)
from termin.project_builder.manifest import BuildDiagnostic, BuildResource, ProjectBuildManifest
from termin_assets import AssetImportPlugin, AssetTypeRegistry


RESOURCE_EXTENSIONS: dict[str, str] = {
    ".scene": "scene",
    ".material": "material",
    ".shader": "shader",
    ".glsl": "glsl",
    ".png": "texture",
    ".jpg": "texture",
    ".jpeg": "texture",
    ".tga": "texture",
    ".bmp": "texture",
    ".hdr": "texture",
    ".obj": "mesh",
    ".stl": "mesh",
    ".fbx": "model",
    ".glb": "model",
    ".gltf": "model",
    ".prefab": "prefab",
    ".pipeline": "pipeline",
    ".scene_pipeline": "scene_pipeline",
    ".wav": "audio",
    ".mp3": "audio",
    ".ogg": "audio",
    ".uiscript": "ui",
}

PROJECT_FILE_EXTENSIONS: dict[str, str] = {
    ".terminproj": "project",
}


class ProjectScanner:
    def __init__(
        self,
        project_root: Path,
        entry_scene: Path,
        output_dir: Path | None = None,
        asset_type_registry: AssetTypeRegistry | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.entry_scene = entry_scene
        self.output_dir = output_dir.resolve() if output_dir is not None else None
        self.diagnostics: list[BuildDiagnostic] = []
        self.asset_type_registry = asset_type_registry or self._create_default_asset_type_registry()
        self.import_plugins_by_extension = build_import_plugin_extension_map(self.asset_type_registry)

    def _create_default_asset_type_registry(self) -> AssetTypeRegistry:
        registry = AssetTypeRegistry()
        register_default_import_asset_plugins(registry)
        return registry

    def scan(self) -> ProjectBuildManifest:
        self._validate_project_root()
        entry_scene_rel = self._resolve_entry_scene()

        resources: list[BuildResource] = []
        entry_scene_build_path = ""

        for path in self._iter_project_files():
            rel_path = self._relative_project_path(path)
            resource_type = self._resource_type(path)
            if resource_type is None:
                resource_type = self._project_file_type(path)

            if resource_type is None:
                continue

            resource = self._build_resource(path, rel_path, resource_type)
            resources.append(resource)
            if rel_path == entry_scene_rel:
                entry_scene_build_path = resource.build_path

        if entry_scene_build_path == "":
            message = "Entry scene was not included in build resources"
            self.diagnostics.append(BuildDiagnostic("error", entry_scene_rel, message))

        resources.sort(key=lambda resource: (resource.type, resource.source_path))

        return ProjectBuildManifest(
            project_root=str(self.project_root),
            entry_scene=entry_scene_rel,
            entry_scene_build_path=entry_scene_build_path,
            resources=resources,
            diagnostics=list(self.diagnostics),
        )

    def _validate_project_root(self) -> None:
        if not self.project_root.exists():
            raise FileNotFoundError(f"Project root does not exist: {self.project_root}")
        if not self.project_root.is_dir():
            raise NotADirectoryError(f"Project root is not a directory: {self.project_root}")

    def _resolve_entry_scene(self) -> str:
        scene_path = self.entry_scene
        if not scene_path.is_absolute():
            scene_path = self.project_root / scene_path
        scene_path = scene_path.resolve()

        if not scene_path.exists():
            raise FileNotFoundError(f"Entry scene does not exist: {scene_path}")
        if scene_path.suffix.lower() != ".scene":
            raise ValueError(f"Entry scene must be a .scene file: {scene_path}")

        return self._relative_project_path(scene_path)

    def _iter_project_files(self) -> list[Path]:
        files: list[Path] = []
        for root_str, dirs, filenames in os.walk(self.project_root):
            root = Path(root_str)
            dirs[:] = [
                dirname
                for dirname in dirs
                if self._should_enter_dir(root / dirname)
            ]

            for filename in filenames:
                if filename.startswith("."):
                    continue
                path = root / filename
                if self._is_inside_output_dir(path):
                    continue
                files.append(path)

        files.sort()
        return files

    def _should_enter_dir(self, path: Path) -> bool:
        name = path.name
        if name.startswith(".") or name.startswith("__"):
            return False
        if self._is_inside_output_dir(path):
            return False
        return True

    def _is_inside_output_dir(self, path: Path) -> bool:
        if self.output_dir is None:
            return False
        resolved = path.resolve()
        return resolved == self.output_dir or self.output_dir in resolved.parents

    def _relative_project_path(self, path: Path) -> str:
        try:
            rel = path.resolve().relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError(f"Path is outside project root: {path}") from exc
        return rel.as_posix()

    def _resource_type(self, path: Path) -> str | None:
        plugin = self._import_plugin_for(path)
        if plugin is not None:
            return plugin.type_id
        return RESOURCE_EXTENSIONS.get(path.suffix.lower())

    def _import_plugin_for(self, path: Path) -> AssetImportPlugin | None:
        return self.import_plugins_by_extension.get(path.suffix.lower())

    def _project_file_type(self, path: Path) -> str | None:
        if self._is_project_settings_file(path):
            return "project_settings"
        if self._is_module_file(path):
            return "module"
        return PROJECT_FILE_EXTENSIONS.get(path.suffix.lower())

    def _is_project_settings_file(self, path: Path) -> bool:
        rel = path.resolve().relative_to(self.project_root)
        return len(rel.parts) >= 2 and rel.parts[0] == "project_settings"

    def _is_module_file(self, path: Path) -> bool:
        rel = path.resolve().relative_to(self.project_root)
        return len(rel.parts) >= 2 and rel.parts[0] == "modules"

    def _build_resource(self, path: Path, rel_path: str, resource_type: str) -> BuildResource:
        uuid = self._read_uuid(path, resource_type)
        meta_path = self._find_meta_path(path)
        meta_rel_path = self._relative_project_path(meta_path) if meta_path is not None else None
        build_path = self._build_path_for(rel_path, resource_type)
        meta_build_path = self._build_path_for(meta_rel_path, "meta") if meta_rel_path is not None else None

        if uuid is None and resource_type not in ("project", "project_settings", "module", "glsl"):
            self.diagnostics.append(
                BuildDiagnostic("warning", rel_path, "Resource has no uuid")
            )

        return BuildResource(
            kind=self._kind_for(resource_type),
            type=resource_type,
            source_path=rel_path,
            build_path=build_path,
            uuid=uuid,
            name=path.stem,
            meta_path=meta_rel_path,
            meta_build_path=meta_build_path,
            size=path.stat().st_size,
        )

    def _kind_for(self, resource_type: str) -> str:
        if resource_type in ("project", "project_settings"):
            return "project"
        if resource_type == "module":
            return "module"
        return "asset"

    def _build_path_for(self, rel_path: str | None, resource_type: str) -> str | None:
        if rel_path is None:
            return None

        rel = Path(rel_path)
        if len(rel.parts) > 0 and rel.parts[0] in ("stdlib", "modules", "project_settings"):
            return rel.as_posix()
        if resource_type in ("project", "project_settings", "module"):
            return rel.as_posix()
        return (Path("assets") / rel).as_posix()

    def _find_meta_path(self, path: Path) -> Path | None:
        meta_path = Path(str(path) + ".meta")
        if meta_path.exists():
            return meta_path
        spec_path = Path(str(path) + ".spec")
        if spec_path.exists():
            return spec_path
        return None

    def _read_uuid(self, path: Path, resource_type: str) -> str | None:
        if resource_type == "scene":
            data = self._read_json(path)
            scene_data = data.get("scene")
            if isinstance(scene_data, dict):
                uuid = scene_data.get("uuid")
                if isinstance(uuid, str):
                    return uuid
            return None

        if resource_type in ("material", "prefab"):
            data = self._read_json(path)
            uuid = data.get("uuid")
            if isinstance(uuid, str):
                return uuid

        meta_path = self._find_meta_path(path)
        if meta_path is None:
            return None

        data = self._read_json(meta_path)
        uuid = data.get("uuid")
        if isinstance(uuid, str):
            return uuid
        return None

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            self.diagnostics.append(
                BuildDiagnostic("error", self._relative_project_path(path), f"Invalid JSON: {exc}")
            )
            return {}
        except Exception as exc:
            self.diagnostics.append(
                BuildDiagnostic("error", self._relative_project_path(path), f"Failed to read JSON: {exc}")
            )
            return {}

        if isinstance(data, dict):
            return data

        self.diagnostics.append(
            BuildDiagnostic("error", self._relative_project_path(path), "JSON root must be an object")
        )
        return {}
