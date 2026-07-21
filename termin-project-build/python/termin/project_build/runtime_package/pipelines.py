"""Compile authored pipelines into canonical runtime template descriptors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from termin.project_build.runtime_package.models import RuntimePackageExportDiagnostic
from termin.project_build.runtime_package.package_files import (
    append_project_file_diagnostic,
    project_relative_path,
)


PIPELINE_TEMPLATE_SUFFIX = ".pipeline-template"


@dataclass(frozen=True)
class CompiledPipelineExport:
    """A compiled asset kept alive for shader-closure collection."""

    uuid: str
    name: str
    resource_path: str
    asset: Any


def write_pipelines(
    project_root: Path,
    package_dir: Path,
    pipelines: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> list[CompiledPipelineExport]:
    if not pipelines:
        return []

    pipeline_dir = package_dir / "pipelines"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    compiled: list[CompiledPipelineExport] = []
    resource_manager = _pipeline_resource_manager(diagnostics)
    if resource_manager is None:
        return compiled

    for uuid_value, name in sorted(pipelines.items()):
        source = find_pipeline_source(project_root, uuid_value, name, diagnostics)
        if source is None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=f"pipelines/{uuid_value}{PIPELINE_TEMPLATE_SUFFIX}",
                    message=(
                        f"Runtime exporter could not find pipeline asset "
                        f"'{name}' ({uuid_value})"
                    ),
                )
            )
            continue

        try:
            from termin.default_assets.render.pipeline_asset import PipelineAsset

            asset = PipelineAsset(name=name, source_path=source, uuid=uuid_value)
            asset.bind_resource_manager(resource_manager)
            pipeline_template = asset.canonical_resource
            if pipeline_template is None:
                raise ValueError("authored pipeline did not produce a compiled template")
            unsupported = [
                item.get("name") or item.get("type") or "<unnamed>"
                for item in pipeline_template.passes
                if item.get("type") == "UnknownPass"
            ]
            if unsupported:
                raise ValueError(
                    "pipeline contains unsupported pass contracts: " + ", ".join(unsupported)
                )
            payload = bytes(pipeline_template.serialize())
            if not payload:
                raise ValueError("compiled pipeline template descriptor is empty")
        except Exception as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, source),
                    message=f"Runtime exporter failed to compile pipeline asset: {exc}",
                )
            )
            continue

        target_name = safe_package_stem(uuid_value or name)
        resource_path = f"pipelines/{target_name}{PIPELINE_TEMPLATE_SUFFIX}"
        target = package_dir / resource_path
        target.write_bytes(payload)
        resources.append(
            {
                "type": "pipeline",
                "uuid": uuid_value,
                "name": name,
                "path": resource_path,
            }
        )
        compiled.append(
            CompiledPipelineExport(
                uuid=uuid_value,
                name=name,
                resource_path=resource_path,
                asset=asset,
            )
        )
    return compiled


def _pipeline_resource_manager(
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Any | None:
    try:
        from termin.bootstrap import bootstrap_player
        from termin.default_assets.resource_manager import DefaultResourceManager

        bootstrap_player()
        resource_manager = DefaultResourceManager.instance()
        resource_manager.register_builtin_frame_passes()
        return resource_manager
    except Exception as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="error",
                path="pipelines",
                message=f"Runtime exporter failed to initialize pipeline compiler: {exc}",
            )
        )
        return None


def safe_package_stem(value: str) -> str:
    result = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            result.append(ch)
        else:
            result.append("_")
    stem = "".join(result).strip("._")
    return stem or "pipeline"


def find_pipeline_source(
    project_root: Path,
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Path | None:
    pipeline_paths = list(iter_project_pipeline_paths(project_root))

    if uuid_value:
        for path in pipeline_paths:
            meta_path = path.with_suffix(path.suffix + ".meta")
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    if isinstance(meta, dict) and meta.get("uuid") == uuid_value:
                        return path
                    if not isinstance(meta, dict):
                        append_project_file_diagnostic(
                            diagnostics,
                            project_root,
                            meta_path,
                            "Runtime exporter skipped pipeline metadata because JSON root is not an object",
                        )
                except Exception as exc:
                    append_project_file_diagnostic(
                        diagnostics,
                        project_root,
                        meta_path,
                        f"Runtime exporter failed to inspect pipeline metadata: {exc}",
                    )

        for path in pipeline_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("uuid") == uuid_value:
                    return path
                if not isinstance(data, dict):
                    append_project_file_diagnostic(
                        diagnostics,
                        project_root,
                        path,
                        "Runtime exporter skipped pipeline asset during source lookup because JSON root is not an object",
                    )
            except Exception as exc:
                append_project_file_diagnostic(
                    diagnostics,
                    project_root,
                    path,
                    f"Runtime exporter failed to inspect pipeline asset during source lookup: {exc}",
                )

    if name:
        expected = f"{name}.pipeline"
        for path in pipeline_paths:
            if path.name == expected:
                return path

    return None


def iter_project_pipeline_paths(project_root: Path):
    ignored_parts = {".git", "__pycache__", "build", "dist"}
    for path in project_root.rglob("*.pipeline"):
        rel = path.relative_to(project_root)
        if any(part in ignored_parts for part in rel.parts):
            continue
        yield path
