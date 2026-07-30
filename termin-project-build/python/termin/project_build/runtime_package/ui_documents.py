"""Native UI document asset export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from termin.project_build.runtime_package.models import RuntimePackageExportDiagnostic
from termin.project_build.runtime_package.package_files import project_relative_path


def write_ui_documents(
    project_root: Path,
    package_dir: Path,
    ui_documents: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    if not ui_documents:
        return

    sources = _index_ui_sources(project_root, set(ui_documents), diagnostics)
    for uuid_value, name in sorted(ui_documents.items()):
        source = sources.get(uuid_value)
        output_rel = f"ui/{uuid_value}.ui-document.json"
        if source is None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=output_rel,
                    message=(
                        "Runtime exporter could not find native UI document "
                        f"UUID '{uuid_value}'"
                    ),
                )
            )
            continue
        try:
            from termin.gui_native import UiDocumentAsset

            compiled = UiDocumentAsset.compile_source_json(
                uuid_value,
                name or source.stem,
                project_relative_path(project_root, source),
                source.read_text(encoding="utf-8"),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, source),
                    message=f"Runtime exporter rejected native UI document: {exc}",
                )
            )
            continue

        output = package_dir / output_rel
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(compiled + "\n", encoding="utf-8")
        resources.append(
            {
                "type": "ui_document",
                "uuid": uuid_value,
                "name": name or source.stem,
                "path": output_rel,
            }
        )


def stage_ui_documents_for_scene_analysis(
    package_dir: Path,
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> list[Any]:
    from termin.gui_native import UiDocumentAsset

    temporary_assets: list[Any] = []
    for resource in resources:
        if resource.get("type") != "ui_document":
            continue
        uuid_value = resource.get("uuid", "")
        rel_path = resource.get("path", "")
        if not uuid_value or not rel_path:
            continue
        if UiDocumentAsset.from_uuid(uuid_value).valid:
            continue
        try:
            compiled = (package_dir / rel_path).read_text(encoding="utf-8")
            temporary = UiDocumentAsset.declare_compiled_json(
                compiled, uuid_value
            )
        except (OSError, RuntimeError, ValueError) as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=rel_path,
                    message=(
                        "Runtime exporter could not stage native UI document "
                        f"UUID '{uuid_value}' for scene analysis: {exc}"
                    ),
                )
            )
            continue
        if not temporary.valid:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=rel_path,
                    message=(
                        "Runtime exporter could not stage native UI document "
                        f"UUID '{uuid_value}' for scene analysis"
                    ),
                )
            )
            continue
        temporary_assets.append(temporary)
    return temporary_assets


def _index_ui_sources(
    project_root: Path,
    required: set[str],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Path]:
    result: dict[str, Path] = {}
    ignored = {".git", "__pycache__", "build", "dist"}
    for source in project_root.rglob("*.uiscript"):
        if any(part in ignored for part in source.relative_to(project_root).parts):
            continue
        meta_path = Path(f"{source}.meta")
        if not meta_path.is_file():
            continue
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=project_relative_path(project_root, meta_path),
                    message=(
                        "Runtime exporter failed to inspect native UI document "
                        f"metadata: {exc}"
                    ),
                )
            )
            continue
        uuid_value = metadata.get("uuid") if isinstance(metadata, dict) else None
        if uuid_value not in required:
            continue
        if uuid_value in result:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, source),
                    message=f"Duplicate native UI document UUID '{uuid_value}'",
                )
            )
            continue
        result[uuid_value] = source
    return result
