"""Runtime pipeline asset export."""

from __future__ import annotations

import json
from pathlib import Path

from termin.project_build.runtime_package.models import RuntimePackageExportDiagnostic
from termin.project_build.runtime_package.package_files import (
    append_project_file_diagnostic,
    project_relative_path,
    write_json,
)


def write_pipelines(
    project_root: Path,
    package_dir: Path,
    pipelines: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    if not pipelines:
        return

    pipeline_dir = package_dir / "pipelines"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(pipelines.items()):
        source = find_pipeline_source(project_root, uuid_value, name, diagnostics)
        if source is None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=f"pipelines/{uuid_value}.pipeline.json",
                    message=(
                        f"Runtime exporter could not find pipeline asset "
                        f"'{name}' ({uuid_value})"
                    ),
                )
            )
            continue

        try:
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("pipeline JSON root must be an object")
        except Exception as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, source),
                    message=f"Runtime exporter failed to read pipeline asset: {exc}",
                )
            )
            continue

        data.setdefault("uuid", uuid_value)
        data.setdefault("name", name)

        target_name = safe_package_stem(uuid_value or name)
        target = pipeline_dir / f"{target_name}.pipeline.json"
        write_json(target, data)
        resources.append(
            {
                "type": "pipeline",
                "uuid": uuid_value,
                "name": name,
                "path": f"pipelines/{target_name}.pipeline.json",
            }
        )


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

