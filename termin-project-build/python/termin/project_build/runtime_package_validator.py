"""Validate runtime package manifests before target packaging."""

from __future__ import annotations

import json
import struct
from pathlib import Path, PurePosixPath
from typing import Any

from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic


RUNTIME_PACKAGE_SCHEMA_VERSION = 2


def validate_runtime_package(package_dir: str | Path) -> list[RuntimePackageExportDiagnostic]:
    package_root = Path(package_dir).resolve()
    manifest_path = package_root / "manifest.json"
    diagnostics: list[RuntimePackageExportDiagnostic] = []

    manifest = _read_manifest(manifest_path, diagnostics)
    if manifest is None:
        return diagnostics

    _validate_version(manifest, diagnostics)
    scenes = _validate_scenes(package_root, manifest, diagnostics)
    resource_index = _validate_resources(package_root, manifest, diagnostics)
    for identity, scene in scenes:
        _validate_scene_resource_references(
            scene,
            resource_index,
            diagnostics,
            f"scenes[{identity}]",
        )
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


def _validate_scenes(
    package_root: Path,
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> list[tuple[str, dict[str, Any]]]:
    entry_scene = manifest.get("entry_scene")
    if not isinstance(entry_scene, str) or entry_scene == "":
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest must contain non-empty string field 'entry_scene'",
            )
        )
        entry_scene = None

    raw_scenes = manifest.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest field 'scenes' must be a non-empty list",
            )
        )
        return []

    seen_identities: set[str] = set()
    seen_paths: set[str] = set()
    result: list[tuple[str, dict[str, Any]]] = []
    for index, raw_scene in enumerate(raw_scenes):
        context = f"scenes[{index}]"
        if not isinstance(raw_scene, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", context, "Runtime package scene entry must be a JSON object"
                )
            )
            continue
        identity = raw_scene.get("identity")
        path = raw_scene.get("path")
        if not isinstance(identity, str) or identity == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", context, "Runtime package scene identity must be a non-empty string"
                )
            )
            continue
        if not _is_portable_scene_identity(identity):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"{context}.identity",
                    f"Runtime package scene identity must be a normalized project-relative .scene path: {identity}",
                )
            )
            continue
        if identity in seen_identities:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", f"{context}.identity", f"Duplicate runtime scene identity '{identity}'"
                )
            )
            continue
        seen_identities.add(identity)
        if not isinstance(path, str) or path == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", context, "Runtime package scene path must be a non-empty string"
                )
            )
            continue
        if path in seen_paths:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", f"{context}.path", f"Duplicate runtime scene path '{path}'"
                )
            )
            continue
        seen_paths.add(path)
        scene_path = _validate_relative_existing_path(
            package_root, path, f"{context}.path", diagnostics
        )
        if scene_path is None:
            continue
        if scene_path.suffix.lower() != ".json":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", path, "Runtime package scene path must use .json extension"
                )
            )
            continue
        scene = _read_json_file(scene_path, path, diagnostics)
        if scene is not None:
            result.append((identity, scene))

    if entry_scene is not None and entry_scene not in seen_identities:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "entry_scene",
                f"Runtime package entry scene '{entry_scene}' is absent from the scene table",
            )
        )
    return result


def _is_portable_scene_identity(identity: str) -> bool:
    if "\\" in identity or ":" in identity or identity.endswith("/"):
        return False
    path = PurePosixPath(identity)
    return (
        not path.is_absolute()
        and all(part not in ("", ".", "..") for part in path.parts)
        and path.as_posix() == identity
        and path.suffix.lower() == ".scene"
    )


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
        elif resource_type == "shader_program" and resolved_path is not None and isinstance(path, str):
            spec = _validate_shader_program_resource(path, resolved_path, diagnostics)
        elif resource_type == "material" and resolved_path is not None and isinstance(path, str):
            spec = _validate_material_resource(package_root, path, resolved_path, diagnostics)
        elif resource_type == "texture" and resolved_path is not None and isinstance(path, str):
            spec = _validate_texture_resource(package_root, path, resolved_path, diagnostics)
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
            if resource_type == "texture" and isinstance(spec, dict) and spec.get("uuid") != uuid:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        path,
                        f"Runtime texture spec UUID '{spec.get('uuid')}' does not match manifest UUID '{uuid}'",
                    )
                )
            if resource_type == "shader_program" and isinstance(spec, dict) and spec.get("uuid") != uuid:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        path,
                        f"Runtime shader program spec UUID '{spec.get('uuid')}' does not match manifest UUID '{uuid}'",
                    )
                )
    return resource_index


def _validate_shader_program_resource(
    resource_path: str,
    spec_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    spec = _read_json_file(spec_path, resource_path, diagnostics)
    if spec is None:
        return None
    if spec.get("schema_version") != 1:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                "Runtime shader program spec requires schema_version 1",
            )
        )
    for field_name in ("uuid", "name", "language"):
        if not isinstance(spec.get(field_name), str) or spec[field_name] == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    f"Runtime shader program field '{field_name}' must be a non-empty string",
                )
            )
    if not isinstance(spec.get("properties"), list):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error", resource_path, "Runtime shader program properties must be a list"
            )
        )
    phases = spec.get("phases")
    if not isinstance(phases, list) or not phases:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error", resource_path, "Runtime shader program phases must be a non-empty list"
            )
        )
    return spec


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

    _validate_material_textures(resource_path, material_spec, diagnostics)
    return material_spec


def _validate_material_textures(
    resource_path: str,
    material_spec: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    textures = material_spec.get("textures")
    if textures is None:
        return
    if not isinstance(textures, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                "Runtime material field 'textures' must be an object when present",
            )
        )
        return

    for slot_name, reference in textures.items():
        context = f"{resource_path}:textures.{slot_name}"
        if not isinstance(slot_name, str) or slot_name == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    "Runtime material texture slot name must be a non-empty string",
                )
            )
            continue
        if not isinstance(reference, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    "Runtime material texture reference must be an object",
                )
            )
            continue
        kind = reference.get("kind")
        if kind == "builtin":
            name = reference.get("name")
            if name not in {"normal", "white"}:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        context,
                        "Runtime builtin material texture must be 'normal' or 'white'",
                    )
                )
            continue
        if kind != "asset":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    "Runtime material texture reference kind must be 'asset' or 'builtin'",
                )
            )
            continue
        uuid_value = reference.get("uuid")
        if not isinstance(uuid_value, str) or uuid_value == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    "Runtime material asset texture reference must contain a non-empty UUID",
                )
            )


def _validate_texture_resource(
    package_root: Path,
    resource_path: str,
    texture_spec_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    texture_spec = _read_json_file(texture_spec_path, resource_path, diagnostics)
    if texture_spec is None:
        return None

    for field_name in ("uuid", "name", "source_path"):
        value = texture_spec.get(field_name)
        if not isinstance(value, str) or value == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    f"Runtime texture spec must contain non-empty string field '{field_name}'",
                )
            )

    source_path = texture_spec.get("source_path")
    if isinstance(source_path, str) and source_path != "":
        _validate_relative_existing_path(
            package_root,
            source_path,
            f"{resource_path}:source_path",
            diagnostics,
        )

    settings = texture_spec.get("import_settings")
    if not isinstance(settings, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                "Runtime texture spec must contain object field 'import_settings'",
            )
        )
        return texture_spec
    for field_name in ("flip_x", "flip_y", "transpose"):
        if not isinstance(settings.get(field_name), bool):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"{resource_path}:import_settings.{field_name}",
                    "Runtime texture import setting must be boolean",
                )
            )
    return texture_spec


def _validate_pipeline_resource(
    package_root: Path,
    resource_path: str,
    pipeline_spec_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    try:
        payload = pipeline_spec_path.read_bytes()
        pipeline_spec = _decode_pipeline_template(payload)
    except (OSError, ValueError) as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                f"Runtime pipeline template descriptor is invalid: {exc}",
            )
        )
        return None
    return pipeline_spec


def _decode_pipeline_template(payload: bytes) -> dict[str, Any]:
    """Decode and strictly validate the portable tc_pipeline_template payload."""

    offset = 0

    def take(size: int) -> bytes:
        nonlocal offset
        if size < 0 or offset > len(payload) or size > len(payload) - offset:
            raise ValueError("descriptor is truncated")
        result = payload[offset : offset + size]
        offset += size
        return result

    def u32() -> int:
        return struct.unpack("<I", take(4))[0]

    def i32() -> int:
        return struct.unpack("<i", take(4))[0]

    def f32() -> float:
        return struct.unpack("<f", take(4))[0]

    def text() -> str:
        size = u32()
        if size > 16 * 1024 * 1024:
            raise ValueError("descriptor string exceeds the size limit")
        try:
            return take(size).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("descriptor contains invalid UTF-8") from exc

    if take(4) != b"TPLT":
        raise ValueError("descriptor magic must be TPLT")
    binary_version = u32()
    descriptor_version = u32()
    if binary_version != 1:
        raise ValueError(f"unsupported binary version {binary_version}")
    if descriptor_version != 1:
        raise ValueError(f"unsupported descriptor version {descriptor_version}")
    name = text()
    if not name:
        raise ValueError("descriptor name must be non-empty")

    pass_count = u32()
    resource_count = u32()
    dependency_count = u32()
    target_count = u32()
    if pass_count > 65536 or resource_count > 65536 or target_count > 65536:
        raise ValueError("descriptor array count exceeds the size limit")
    if dependency_count > 262144:
        raise ValueError("descriptor dependency count exceeds the size limit")

    passes: list[dict[str, Any]] = []
    for index in range(pass_count):
        type_name = text()
        pass_name = text()
        parameters = text()
        viewport_name = text()
        if not type_name or not pass_name:
            raise ValueError(f"pass {index} lacks type or name")
        if type_name == "UnknownPass":
            raise ValueError(f"pass {index} uses unsupported UnknownPass contract")
        if parameters:
            try:
                parameter_data = json.loads(parameters)
            except json.JSONDecodeError as exc:
                raise ValueError(f"pass {index} parameters are not valid JSON") from exc
            if not isinstance(parameter_data, dict):
                raise ValueError(f"pass {index} parameters must be a JSON object")
        passes.append(
            {
                "type": type_name,
                "name": pass_name,
                "parameters": parameters,
                "viewport_name": viewport_name,
            }
        )

    resources: list[dict[str, Any]] = []
    resource_names: set[str] = set()
    for index in range(resource_count):
        resource_name = text()
        resource_type = text()
        format_name = text()
        viewport_name = text()
        width = i32()
        height = i32()
        scale = f32()
        samples = u32()
        flags = u32()
        if not resource_name or not resource_type:
            raise ValueError(f"resource {index} lacks name or type")
        if resource_name in resource_names:
            raise ValueError(f"resource '{resource_name}' is duplicated")
        if samples == 0:
            raise ValueError(f"resource '{resource_name}' has zero samples")
        resource_names.add(resource_name)
        resources.append(
            {
                "name": resource_name,
                "resource_type": resource_type,
                "format": format_name,
                "viewport_name": viewport_name,
                "width": width,
                "height": height,
                "scale": scale,
                "samples": samples,
                "flags": flags,
            }
        )

    dependencies: list[dict[str, Any]] = []
    for index in range(dependency_count):
        pass_index = u32()
        resource_name = text()
        access = u32()
        if pass_index >= pass_count:
            raise ValueError(f"dependency {index} references missing pass {pass_index}")
        if resource_name not in resource_names:
            raise ValueError(f"dependency {index} references missing resource '{resource_name}'")
        if access not in (1, 2, 3):
            raise ValueError(f"dependency {index} has invalid access {access}")
        dependencies.append(
            {"pass_index": pass_index, "resource": resource_name, "access": access}
        )

    targets: list[dict[str, Any]] = []
    for _ in range(target_count):
        targets.append(
            {
                "viewport_name": text(),
                "export_name": text(),
                "width": i32(),
                "height": i32(),
            }
        )
    if offset != len(payload):
        raise ValueError("descriptor contains trailing data")
    return {
        "binary_version": binary_version,
        "descriptor_version": descriptor_version,
        "name": name,
        "passes": passes,
        "resources": resources,
        "dependencies": dependencies,
        "targets": targets,
    }


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
    context: str = "scene",
) -> None:
    _validate_scene_refs_recursive(scene, resource_index, diagnostics, context)


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
    reference_context = f"{context}.pipeline_uuid"
    if (
        (not isinstance(pipeline_uuid, str) or pipeline_uuid == "")
        and ".pipeline_templates[" in context
        and context.endswith("]")
    ):
        pipeline_uuid = value.get("uuid")
        reference_context = f"{context}.uuid"
    if not isinstance(pipeline_uuid, str) or pipeline_uuid == "":
        return
    _validate_resource_ref(
        pipeline_uuid,
        "pipeline",
        resource_index,
        diagnostics,
        reference_context,
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
        elif resource_type == "shader_program":
            _validate_shader_program_graph(uuid_value, resource_path, spec, resource_index, diagnostics)
        elif resource_type == "pipeline":
            _validate_pipeline_graph(uuid_value, resource_path, spec, resource_index, diagnostics)


def _validate_material_graph(
    material_uuid: str,
    resource_path: str,
    material_spec: dict[str, Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    program_uuid = material_spec.get("shader_program")
    if isinstance(program_uuid, str) and program_uuid != "":
        _validate_resource_ref(
            program_uuid,
            "shader_program",
            resource_index,
            diagnostics,
            f"{resource_path}:shader_program",
        )
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

    textures = material_spec.get("textures")
    if not isinstance(textures, dict):
        return
    for slot_name, reference in textures.items():
        if not isinstance(slot_name, str) or not isinstance(reference, dict):
            continue
        if reference.get("kind") != "asset":
            continue
        uuid_value = reference.get("uuid")
        if isinstance(uuid_value, str) and uuid_value != "":
            _validate_resource_ref(
                uuid_value,
                "texture",
                resource_index,
                diagnostics,
                f"{resource_path}:textures.{slot_name}",
            )


def _validate_shader_program_graph(
    program_uuid: str,
    resource_path: str,
    program_spec: dict[str, Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    phases = program_spec.get("phases")
    if not isinstance(phases, list):
        return
    seen_marks: set[str] = set()
    for index, phase in enumerate(phases):
        context = f"{resource_path}:phases[{index}]"
        if not isinstance(phase, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic("error", context, "Shader program phase must be an object")
            )
            continue
        mark = phase.get("phase_mark")
        if not isinstance(mark, str) or mark == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic("error", context, "Shader program phase_mark must be non-empty")
            )
        elif mark in seen_marks:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", context, f"Shader program '{program_uuid}' has duplicate phase '{mark}'"
                )
            )
        else:
            seen_marks.add(mark)
        shader_uuid = phase.get("shader")
        if isinstance(shader_uuid, str) and shader_uuid != "":
            _validate_resource_ref(shader_uuid, "shader", resource_index, diagnostics, f"{context}.shader")
        else:
            diagnostics.append(
                RuntimePackageExportDiagnostic("error", context, "Shader program phase shader must be non-empty")
            )


def _validate_pipeline_graph(
    pipeline_uuid: str,
    resource_path: str,
    pipeline_spec: dict[str, Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    # Shader/resource closure is emitted as independent manifest resources.
    # The template itself deliberately contains only backend-neutral execution
    # descriptors and therefore has no authored graph edges to validate here.
    del pipeline_uuid, resource_path, pipeline_spec, resource_index, diagnostics


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

    platform = requirements.get("platform")
    if platform is not None:
        if not isinstance(platform, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    "manifest.json:target_requirements.platform",
                    "Runtime package target platform must be an object",
                )
            )
        else:
            for field in ("os", "arch"):
                value = platform.get(field)
                if not isinstance(value, str) or value == "":
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            f"manifest.json:target_requirements.platform.{field}",
                            f"Runtime package target platform {field} must be a non-empty string",
                        )
                    )

    backends = requirements.get("backends")
    if not isinstance(backends, list) or not backends:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json:target_requirements.backends",
                "Runtime package target requirements must contain a non-empty backends list",
            )
        )
    else:
        _validate_required_backends(backends, resource_index, diagnostics)


def _validate_required_backends(
    backends: list[Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    required_backends: list[str] = []
    for index, backend_name in enumerate(backends):
        if not isinstance(backend_name, str) or backend_name not in {"vulkan", "opengl", "d3d11"}:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"manifest.json:target_requirements.backends[{index}]",
                    "Runtime package backend must be one of: vulkan, opengl, d3d11",
                )
            )
            continue
        if backend_name in required_backends:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"manifest.json:target_requirements.backends[{index}]",
                    f"Runtime package backend order contains duplicate '{backend_name}'",
                )
            )
            continue
        required_backends.append(backend_name)

    for shader_uuid, resource in resource_index.items():
        if resource.get("type") != "shader":
            continue
        spec = resource.get("spec")
        if not isinstance(spec, dict):
            continue
        artifacts = spec.get("artifacts")
        if not isinstance(artifacts, dict):
            continue
        artifact_backends = list(artifacts)
        if set(artifact_backends) != set(required_backends):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    _resource_path(resource),
                    f"Runtime shader '{shader_uuid}' artifact backends {artifact_backends} "
                    f"do not match runtime backend order {required_backends}",
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
