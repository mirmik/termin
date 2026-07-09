"""Validate runtime package manifests before target packaging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic


RUNTIME_PACKAGE_SCHEMA_VERSION = 1


def validate_runtime_package(package_dir: str | Path) -> list[RuntimePackageExportDiagnostic]:
    package_root = Path(package_dir).resolve()
    manifest_path = package_root / "manifest.json"
    diagnostics: list[RuntimePackageExportDiagnostic] = []

    manifest = _read_manifest(manifest_path, diagnostics)
    if manifest is None:
        return diagnostics

    _validate_version(manifest, diagnostics)
    scene = _validate_scene(package_root, manifest, diagnostics)
    resource_index = _validate_resources(package_root, manifest, diagnostics)
    if scene is not None:
        _validate_scene_resource_references(scene, resource_index, diagnostics)
    _validate_resource_graph(resource_index, diagnostics)
    _validate_target_requirements(manifest, resource_index, diagnostics)
    return diagnostics


def _read_manifest(
    manifest_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                f"Runtime package manifest cannot be read: {exc}",
            )
        )
        return None
    except json.JSONDecodeError as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                f"Runtime package manifest is not valid JSON: {exc}",
            )
        )
        return None

    if not isinstance(data, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest root must be a JSON object",
            )
        )
        return None
    return data


def _validate_version(
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    value = manifest.get("version")
    if value is None:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                f"Runtime package manifest must contain integer field 'version' with value {RUNTIME_PACKAGE_SCHEMA_VERSION}",
            )
        )
        return
    if not isinstance(value, int):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest field 'version' must be an integer",
            )
        )
        return
    if value != RUNTIME_PACKAGE_SCHEMA_VERSION:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                f"Unsupported runtime package schema version {value}; supported version is {RUNTIME_PACKAGE_SCHEMA_VERSION}",
            )
        )


def _validate_scene(
    package_root: Path,
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    scene = manifest.get("scene")
    if not isinstance(scene, str) or scene == "":
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest must contain non-empty string field 'scene'",
            )
        )
        return None

    scene_path = _validate_relative_existing_path(package_root, scene, "scene", diagnostics)
    if scene_path is not None and scene_path.suffix.lower() != ".json":
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "warning",
                scene,
                "Runtime package scene path does not use .json extension",
            )
        )
    if scene_path is None:
        return None
    return _read_json_file(scene_path, scene, diagnostics)


def _validate_resources(
    package_root: Path,
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, dict[str, Any]]:
    resources = manifest.get("resources")
    if not isinstance(resources, list):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest field 'resources' must be a list",
            )
        )
        return {}

    seen_uuids: dict[str, str] = {}
    resource_index: dict[str, dict[str, Any]] = {}
    for index, resource in enumerate(resources):
        context = f"resources[{index}]"
        if not isinstance(resource, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    "Runtime package resource entry must be a JSON object",
                )
            )
            continue

        path = resource.get("path")
        resolved_path: Path | None = None
        if not isinstance(path, str) or path == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    "Runtime package resource entry must contain non-empty string field 'path'",
                )
            )
        else:
            resolved_path = _validate_relative_existing_path(package_root, path, context, diagnostics)

        resource_type = resource.get("type")
        spec: dict[str, Any] | None = None
        if resource_type == "shader" and resolved_path is not None and isinstance(path, str):
            spec = _validate_shader_resource(package_root, path, resolved_path, diagnostics)
        elif resource_type == "material" and resolved_path is not None and isinstance(path, str):
            spec = _validate_material_resource(package_root, path, resolved_path, diagnostics)
        elif resource_type == "pipeline" and resolved_path is not None and isinstance(path, str):
            spec = _validate_pipeline_resource(package_root, path, resolved_path, diagnostics)

        uuid = resource.get("uuid")
        if uuid is None:
            continue
        if not isinstance(uuid, str) or uuid == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    "Runtime package resource field 'uuid' must be a non-empty string when present",
                )
            )
            continue

        previous_context = seen_uuids.get(uuid)
        if previous_context is not None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    f"Duplicate runtime package resource uuid '{uuid}' also declared at {previous_context}",
                )
            )
        else:
            seen_uuids[uuid] = context
            resource_index[uuid] = {
                "context": context,
                "type": resource_type,
                "path": path,
                "spec": spec,
            }
    return resource_index


def _validate_shader_resource(
    package_root: Path,
    resource_path: str,
    shader_spec_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    shader_spec = _read_json_file(shader_spec_path, resource_path, diagnostics)
    if shader_spec is None:
        return None

    artifacts = shader_spec.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                "Runtime shader spec must contain non-empty object field 'artifacts'",
            )
        )
        return shader_spec

    for target_name, target_artifacts in artifacts.items():
        target_context = f"{resource_path}:artifacts.{target_name}"
        if not isinstance(target_name, str) or target_name == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    "Runtime shader artifact target name must be a non-empty string",
                )
            )
            continue
        if not isinstance(target_artifacts, dict) or not target_artifacts:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    target_context,
                    "Runtime shader artifact target entry must be a non-empty object",
                )
            )
            continue

        _validate_required_shader_artifact_stages(resource_path, target_context, target_artifacts, diagnostics)

        for stage_name, artifact_path in target_artifacts.items():
            stage_context = f"{target_context}.{stage_name}"
            if not isinstance(stage_name, str) or stage_name == "":
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        target_context,
                        "Runtime shader artifact stage name must be a non-empty string",
                    )
                )
                continue
            if not isinstance(artifact_path, str) or artifact_path == "":
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        stage_context,
                        "Runtime shader artifact path must be a non-empty string",
                    )
                )
                continue
            _validate_relative_existing_path(package_root, artifact_path, stage_context, diagnostics)
    _validate_shader_stage_sources(package_root, resource_path, shader_spec, diagnostics)
    return shader_spec


def _validate_material_resource(
    package_root: Path,
    resource_path: str,
    material_spec_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    material_spec = _read_json_file(material_spec_path, resource_path, diagnostics)
    if material_spec is None:
        return None

    phases = material_spec.get("phases")
    if not isinstance(phases, list) or not phases:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                "Runtime material spec must contain non-empty list field 'phases'",
            )
        )
        return material_spec

    for index, phase in enumerate(phases):
        phase_context = f"{resource_path}:phases[{index}]"
        if not isinstance(phase, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    phase_context,
                    "Runtime material phase entry must be an object",
                )
            )
            continue
        mark = phase.get("mark")
        if not isinstance(mark, str) or mark == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    phase_context,
                    "Runtime material phase must contain non-empty string field 'mark'",
                )
            )
        shader = phase.get("shader")
        if not isinstance(shader, str) or shader == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    phase_context,
                    "Runtime material phase must contain non-empty string field 'shader'",
                )
            )
        priority = phase.get("priority")
        if priority is not None and not isinstance(priority, int):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    phase_context,
                    "Runtime material phase field 'priority' must be an integer when present",
                )
            )

    return material_spec


def _validate_pipeline_resource(
    package_root: Path,
    resource_path: str,
    pipeline_spec_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    pipeline_spec = _read_json_file(pipeline_spec_path, resource_path, diagnostics)
    if pipeline_spec is None:
        return None

    for key in ("shader", "shader_uuid"):
        value = pipeline_spec.get(key)
        if value is not None and (not isinstance(value, str) or value == ""):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    f"Runtime pipeline field '{key}' must be a non-empty string when present",
                )
            )

    phases = pipeline_spec.get("phases")
    if phases is not None:
        if not isinstance(phases, list):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    "Runtime pipeline field 'phases' must be a list when present",
                )
            )
        else:
            for index, phase in enumerate(phases):
                _validate_pipeline_phase_shape(resource_path, index, phase, diagnostics)

    return pipeline_spec


def _validate_pipeline_phase_shape(
    resource_path: str,
    index: int,
    phase: Any,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    context = f"{resource_path}:phases[{index}]"
    if not isinstance(phase, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                "Runtime pipeline phase entry must be an object",
            )
        )
        return
    mark = phase.get("mark")
    if mark is not None and (not isinstance(mark, str) or mark == ""):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                "Runtime pipeline phase field 'mark' must be a non-empty string when present",
            )
        )
    shader = phase.get("shader")
    if shader is not None and (not isinstance(shader, str) or shader == ""):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                "Runtime pipeline phase field 'shader' must be a non-empty string when present",
            )
        )
    shader_uuid = phase.get("shader_uuid")
    if shader_uuid is not None and (not isinstance(shader_uuid, str) or shader_uuid == ""):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                "Runtime pipeline phase field 'shader_uuid' must be a non-empty string when present",
            )
        )


def _validate_required_shader_artifact_stages(
    resource_path: str,
    target_context: str,
    target_artifacts: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    for required_stage in ("vertex", "fragment"):
        if required_stage not in target_artifacts:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    target_context,
                    f"Runtime shader artifact target must contain '{required_stage}' stage",
                )
            )


def _validate_shader_stage_sources(
    package_root: Path,
    resource_path: str,
    shader_spec: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    for field_name in ("vertex_source_path", "fragment_source_path", "geometry_source_path"):
        value = shader_spec.get(field_name)
        if value is None:
            if field_name in ("vertex_source_path", "fragment_source_path"):
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        resource_path,
                        f"Runtime shader spec must contain string field '{field_name}'",
                    )
                )
            continue
        if not isinstance(value, str) or value == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    f"Runtime shader spec field '{field_name}' must be a non-empty string",
                )
            )
            continue
        _validate_relative_existing_path(
            package_root,
            value,
            f"{resource_path}:{field_name}",
            diagnostics,
        )


def _validate_scene_resource_references(
    scene: dict[str, Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    _validate_scene_refs_recursive(scene, resource_index, diagnostics, "scene")


def _validate_scene_refs_recursive(
    value: Any,
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    context: str,
) -> None:
    if isinstance(value, dict):
        _validate_scene_typed_ref(value, resource_index, diagnostics, context)
        _validate_scene_pipeline_ref(value, resource_index, diagnostics, context)
        for key, child in value.items():
            _validate_scene_refs_recursive(child, resource_index, diagnostics, f"{context}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_scene_refs_recursive(child, resource_index, diagnostics, f"{context}[{index}]")


def _validate_scene_typed_ref(
    value: dict[str, Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    context: str,
) -> None:
    uuid_value = value.get("uuid")
    type_value = value.get("type")
    if not isinstance(uuid_value, str) or uuid_value == "" or type_value != "uuid":
        return

    expected_type = _expected_scene_resource_type(value, context)
    if expected_type is None:
        legacy_type, legacy_reason = _legacy_scene_resource_ref(value, context)
        if legacy_type is not None and legacy_reason is not None:
            _append_rejected_legacy_scene_ref(
                diagnostics,
                legacy_type,
                legacy_reason,
                context,
            )
        return
    _validate_resource_ref(
        uuid_value,
        expected_type,
        resource_index,
        diagnostics,
        context,
    )


def _validate_scene_pipeline_ref(
    value: dict[str, Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    context: str,
) -> None:
    pipeline_uuid = value.get("pipeline_uuid")
    if not isinstance(pipeline_uuid, str) or pipeline_uuid == "":
        return
    _validate_resource_ref(
        pipeline_uuid,
        "pipeline",
        resource_index,
        diagnostics,
        f"{context}.pipeline_uuid",
    )


def _expected_scene_resource_type(value: dict[str, Any], context: str) -> str | None:
    kind_value = value.get("kind")
    role_value = value.get("role")
    if kind_value == "tc_mesh" or role_value == "mesh":
        return "mesh"
    if kind_value == "tc_material" or role_value == "material":
        return "material"

    return None


def _legacy_scene_resource_ref(
    value: dict[str, Any],
    context: str,
) -> tuple[str | None, str | None]:
    context_tail = context.rsplit(".", 1)[-1]
    if context_tail == "mesh":
        return "mesh", "legacy field name"
    if context_tail == "material":
        return "material", "legacy field name"

    name_value = value.get("name")
    if isinstance(name_value, str):
        lowered = name_value.lower()
        if "mesh" in lowered:
            return "mesh", "legacy resource name"
        if "material" in lowered:
            return "material", "legacy resource name"
    return None, None


def _append_rejected_legacy_scene_ref(
    diagnostics: list[RuntimePackageExportDiagnostic],
    resource_type: str,
    reason: str,
    context: str,
) -> None:
    if resource_type == "mesh":
        canonical_hint = "kind='tc_mesh' or role='mesh'"
    elif resource_type == "material":
        canonical_hint = "kind='tc_material' or role='material'"
    else:
        raise ValueError(f"Unsupported runtime resource ref type: {resource_type}")
    diagnostics.append(
        RuntimePackageExportDiagnostic(
            "error",
            context,
            (
                f"Runtime package rejected legacy {resource_type} resource ref from {reason}; "
                f"add {canonical_hint} to the uuid ref"
            ),
        )
    )


def _validate_resource_graph(
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    for uuid_value, resource in resource_index.items():
        resource_type = resource.get("type")
        spec = resource.get("spec")
        resource_path = _resource_path(resource)
        if not isinstance(spec, dict):
            continue
        if resource_type == "material":
            _validate_material_graph(uuid_value, resource_path, spec, resource_index, diagnostics)
        elif resource_type == "pipeline":
            _validate_pipeline_graph(uuid_value, resource_path, spec, resource_index, diagnostics)


def _validate_material_graph(
    material_uuid: str,
    resource_path: str,
    material_spec: dict[str, Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    phases = material_spec.get("phases")
    if not isinstance(phases, list):
        return
    seen_marks: set[str] = set()
    for index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            continue
        phase_context = f"{resource_path}:phases[{index}]"
        mark = phase.get("mark")
        if isinstance(mark, str) and mark != "":
            if mark in seen_marks:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        phase_context,
                        f"Runtime material '{material_uuid}' declares duplicate phase mark '{mark}'",
                    )
                )
            seen_marks.add(mark)
        shader_uuid = phase.get("shader")
        if isinstance(shader_uuid, str) and shader_uuid != "":
            _validate_resource_ref(shader_uuid, "shader", resource_index, diagnostics, f"{phase_context}.shader")


def _validate_pipeline_graph(
    pipeline_uuid: str,
    resource_path: str,
    pipeline_spec: dict[str, Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    for field_name in ("shader", "shader_uuid"):
        value = pipeline_spec.get(field_name)
        if isinstance(value, str) and value != "":
            _validate_resource_ref(value, "shader", resource_index, diagnostics, f"{resource_path}:{field_name}")

    phases = pipeline_spec.get("phases")
    if not isinstance(phases, list):
        return
    seen_marks: set[str] = set()
    for index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            continue
        phase_context = f"{resource_path}:phases[{index}]"
        mark = phase.get("mark")
        if isinstance(mark, str) and mark != "":
            if mark in seen_marks:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        phase_context,
                        f"Runtime pipeline '{pipeline_uuid}' declares duplicate phase mark '{mark}'",
                    )
                )
            seen_marks.add(mark)
        for field_name in ("shader", "shader_uuid"):
            value = phase.get(field_name)
            if isinstance(value, str) and value != "":
                _validate_resource_ref(
                    value,
                    "shader",
                    resource_index,
                    diagnostics,
                    f"{phase_context}.{field_name}",
                )


def _validate_target_requirements(
    manifest: dict[str, Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    requirements = manifest.get("target_requirements")
    if requirements is None:
        return
    if not isinstance(requirements, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json:target_requirements",
                "Runtime package target_requirements field must be an object when present",
            )
        )
        return

    shader_targets = requirements.get("shader_targets")
    if shader_targets is not None:
        if not isinstance(shader_targets, list):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    "manifest.json:target_requirements.shader_targets",
                    "Runtime package target_requirements.shader_targets must be a list",
                )
            )
        else:
            _validate_required_shader_targets(shader_targets, resource_index, diagnostics)


def _validate_required_shader_targets(
    shader_targets: list[Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    required_targets: list[str] = []
    for index, target_name in enumerate(shader_targets):
        if not isinstance(target_name, str) or target_name == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"manifest.json:target_requirements.shader_targets[{index}]",
                    "Runtime package shader target requirement must be a non-empty string",
                )
            )
            continue
        required_targets.append(target_name)

    for shader_uuid, resource in resource_index.items():
        if resource.get("type") != "shader":
            continue
        spec = resource.get("spec")
        if not isinstance(spec, dict):
            continue
        artifacts = spec.get("artifacts")
        if not isinstance(artifacts, dict):
            continue
        for target_name in required_targets:
            if target_name not in artifacts:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        _resource_path(resource),
                        f"Runtime shader '{shader_uuid}' is missing required target artifacts: {target_name}",
                    )
                )


def _validate_resource_ref(
    uuid_value: str,
    expected_type: str,
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    context: str,
) -> None:
    resource = resource_index.get(uuid_value)
    if resource is None:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                f"Runtime package references missing {expected_type} resource uuid '{uuid_value}'",
            )
        )
        return
    actual_type = resource.get("type")
    if actual_type != expected_type:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                f"Runtime package resource uuid '{uuid_value}' has type '{actual_type}', expected '{expected_type}'",
            )
        )


def _resource_path(resource: dict[str, Any]) -> str:
    path = resource.get("path")
    if isinstance(path, str) and path != "":
        return path
    context = resource.get("context")
    if isinstance(context, str):
        return context
    return "resources"


def _read_json_file(
    path: Path,
    context: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                f"Runtime package JSON file cannot be read: {exc}",
            )
        )
        return None
    except json.JSONDecodeError as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                f"Runtime package JSON file is not valid JSON: {exc}",
            )
        )
        return None

    if not isinstance(data, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                "Runtime package JSON file root must be an object",
            )
        )
        return None
    return data


def _validate_relative_existing_path(
    package_root: Path,
    relative_path: str,
    context: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Path | None:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                f"Runtime package path must be relative: {relative_path}",
            )
        )
        return None
    resolved = (package_root / candidate).resolve()
    try:
        resolved.relative_to(package_root)
    except ValueError:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                f"Runtime package path escapes package root: {relative_path}",
            )
        )
        return None
    if not resolved.exists():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                relative_path,
                f"Runtime package path does not exist: {relative_path}",
            )
        )
        return None
    return resolved
