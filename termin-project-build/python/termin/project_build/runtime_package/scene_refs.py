"""Scene reading and runtime resource reference collection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from termin.project_build.runtime_package.models import (
    RuntimePackageExportDiagnostic,
    RuntimeRefs,
)
from termin.project_build.runtime_package.package_files import project_relative_path


def resolve_entry_scene(project_root: Path, entry_scene: Path) -> Path:
    scene_path = entry_scene
    if not scene_path.is_absolute():
        scene_path = project_root / scene_path
    scene_path = scene_path.resolve()
    if not scene_path.exists():
        raise FileNotFoundError(f"Entry scene does not exist: {scene_path}")
    if scene_path.suffix.lower() != ".scene":
        raise ValueError(f"Entry scene must be a .scene file: {scene_path}")
    try:
        scene_path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"Entry scene is outside project root: {scene_path}") from exc
    return scene_path


def read_scene_data(scene_path: Path) -> dict[str, Any]:
    with open(scene_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Scene JSON root must be an object: {scene_path}")

    scene_data = data.get("scene")
    if isinstance(scene_data, dict):
        return scene_data

    scenes_data = data.get("scenes")
    if isinstance(scenes_data, list) and len(scenes_data) > 0:
        first_scene = scenes_data[0]
        if isinstance(first_scene, dict):
            return first_scene

    if "entities" in data:
        return data

    raise ValueError(f"Scene file has no scene data: {scene_path}")


def collect_runtime_refs(
    scene_data: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic] | None = None,
) -> RuntimeRefs:
    refs = RuntimeRefs()
    collect_refs_recursive(scene_data, refs, "", diagnostics, "$")
    return refs


def collect_refs_recursive(
    value: Any,
    refs: RuntimeRefs,
    field_name: str,
    diagnostics: list[RuntimePackageExportDiagnostic] | None = None,
    ref_path: str = "$",
) -> None:
    if isinstance(value, dict):
        collect_pipeline_refs(value, refs)
        collect_typed_ref(value, refs, field_name, diagnostics, ref_path)
        for key, child in value.items():
            child_path = f"{ref_path}.{key}" if ref_path != "$" else f"$.{key}"
            collect_refs_recursive(child, refs, key, diagnostics, child_path)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            collect_refs_recursive(child, refs, field_name, diagnostics, f"{ref_path}[{index}]")


def collect_typed_ref(
    value: dict[str, Any],
    refs: RuntimeRefs,
    field_name: str,
    diagnostics: list[RuntimePackageExportDiagnostic] | None = None,
    ref_path: str = "$",
) -> None:
    uuid_value = value.get("uuid")
    type_value = value.get("type")
    if not isinstance(uuid_value, str) or uuid_value == "":
        return
    if type_value != "uuid":
        return

    name_value = value.get("name")
    name = name_value if isinstance(name_value, str) and name_value != "" else uuid_value

    mesh_reason = resource_ref_match_reason(value, field_name, "mesh")
    if mesh_reason is not None:
        refs.meshes[uuid_value] = name
    else:
        append_rejected_legacy_ref_diagnostic(
            diagnostics,
            legacy_resource_ref_reason(value, field_name, "mesh"),
            "mesh",
            ref_path,
        )
    material_reason = resource_ref_match_reason(value, field_name, "material")
    if material_reason is not None:
        refs.materials[uuid_value] = name
    else:
        append_rejected_legacy_ref_diagnostic(
            diagnostics,
            legacy_resource_ref_reason(value, field_name, "material"),
            "material",
            ref_path,
        )


def collect_pipeline_refs(value: dict[str, Any], refs: RuntimeRefs) -> None:
    pipeline_uuid = value.get("pipeline_uuid")
    pipeline_name = value.get("pipeline_name")
    if isinstance(pipeline_uuid, str) and pipeline_uuid != "":
        name = pipeline_name if isinstance(pipeline_name, str) and pipeline_name != "" else pipeline_uuid
        refs.pipelines[pipeline_uuid] = name


def collect_project_material_refs(
    project_root: Path,
    refs: RuntimeRefs,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    for path in iter_project_material_paths(project_root):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=project_relative_path(project_root, path),
                    message=f"Runtime exporter failed to inspect material asset: {exc}",
                )
            )
            continue

        if not isinstance(data, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=project_relative_path(project_root, path),
                    message="Runtime exporter skipped material asset because JSON root is not an object",
                )
            )
            continue

        uuid_value = data.get("uuid")
        if not isinstance(uuid_value, str) or uuid_value == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=project_relative_path(project_root, path),
                    message="Runtime exporter skipped material asset because it has no uuid",
                )
            )
            continue

        refs.materials[uuid_value] = path.stem


def iter_project_material_paths(project_root: Path):
    ignored_parts = {".git", "__pycache__", "build", "dist"}
    for path in project_root.rglob("*.material"):
        rel = path.relative_to(project_root)
        if any(part in ignored_parts for part in rel.parts):
            continue
        if path.is_file():
            yield path


def looks_like_mesh_ref(value: dict[str, Any], field_name: str) -> bool:
    return resource_ref_match_reason(value, field_name, "mesh") is not None


def looks_like_material_ref(value: dict[str, Any], field_name: str) -> bool:
    return resource_ref_match_reason(value, field_name, "material") is not None


def resource_ref_match_reason(
    value: dict[str, Any],
    field_name: str,
    resource_type: str,
) -> str | None:
    if resource_type == "mesh":
        canonical_kind = "tc_mesh"
    elif resource_type == "material":
        canonical_kind = "tc_material"
    else:
        raise ValueError(f"Unsupported runtime resource ref type: {resource_type}")

    kind_value = value.get("kind")
    role_value = value.get("role")
    if kind_value == canonical_kind or role_value == resource_type:
        return "explicit"

    return None


def legacy_resource_ref_reason(
    value: dict[str, Any],
    field_name: str,
    resource_type: str,
) -> str | None:
    if field_name == resource_type:
        return "legacy field name"

    name_value = value.get("name")
    if isinstance(name_value, str) and resource_type in name_value.lower():
        return "legacy resource name"

    return None


def append_rejected_legacy_ref_diagnostic(
    diagnostics: list[RuntimePackageExportDiagnostic] | None,
    reason: str | None,
    resource_type: str,
    ref_path: str,
) -> None:
    if diagnostics is None or reason is None:
        return
    if resource_type == "mesh":
        canonical_hint = "kind='tc_mesh' or role='mesh'"
    elif resource_type == "material":
        canonical_hint = "kind='tc_material' or role='material'"
    else:
        raise ValueError(f"Unsupported runtime resource ref type: {resource_type}")
    diagnostics.append(
        RuntimePackageExportDiagnostic(
            level="error",
            path="scene.json",
            message=(
                f"Runtime exporter rejected legacy {resource_type} resource ref from {reason} "
                f"at {ref_path}; add {canonical_hint} to the uuid ref"
            ),
        )
    )
