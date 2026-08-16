"""Validate runtime package resource payloads and paths."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic


@dataclass(frozen=True)
class SceneComponentFactoryPolicy:
    """Factory capabilities exposed by the runtime host for packaged scenes."""

    allowed_kinds: frozenset[str] = frozenset({"cxx"})
    allowed_python_owners: frozenset[str] = frozenset()


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
        elif resource_type == "ui_document" and resolved_path is not None and isinstance(path, str):
            spec = _validate_ui_document_resource(path, resolved_path, diagnostics)

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


def _validate_ui_document_resource(
    resource_path: str,
    spec_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    spec = _read_json_file(spec_path, resource_path, diagnostics)
    if spec is None:
        return None
    if spec.get("ui_document_asset") != 1:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                "Native UI document requires ui_document_asset schema version 1",
            )
        )

    dependencies = spec.get("type_dependencies")
    if (
        not isinstance(dependencies, list)
        or any(not isinstance(item, str) or item == "" for item in dependencies)
        or len(set(dependencies)) != len(dependencies)
    ):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                f"{resource_path}:type_dependencies",
                "Native UI document type_dependencies must be a unique list of non-empty strings",
            )
        )
        return spec

    recipe_dependencies = _ui_recipe_dependencies(spec.get("recipe"))
    if recipe_dependencies is None:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                f"{resource_path}:recipe",
                "Native UI document recipe must be a widget object with recursively valid children",
            )
        )
        return spec
    if dependencies != recipe_dependencies:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                f"{resource_path}:type_dependencies",
                "Native UI document type_dependencies do not match recipe widget types",
            )
        )

    try:
        from termin.gui_native import widget_type_info
    except (ImportError, RuntimeError) as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                f"Native UI widget factory registry is unavailable: {exc}",
            )
        )
        return spec

    for type_name in dependencies:
        context = f"{resource_path}:type_dependencies[{type_name}]"
        try:
            info = widget_type_info(type_name)
        except RuntimeError as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    f"Native UI widget factory registry query failed: {exc}",
                )
            )
            continue
        if not info["registered"]:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    f"Native UI widget factory is not registered for '{type_name}'",
                )
            )
        elif info["language"] != "cxx":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    f"Packaged UI requires a C++ widget factory; '{type_name}' is {info['language']}",
                )
            )
        elif not info["uiscript"]:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    f"Native UI widget '{type_name}' has no UiScript factory contract",
                )
            )
    return spec


def _ui_recipe_dependencies(recipe: Any) -> list[str] | None:
    if (
        not isinstance(recipe, dict)
        or recipe.get("uiscript") != 2
        or "root" not in recipe
    ):
        return None
    result: list[str] = []
    seen: set[str] = set()

    def visit(node: Any) -> bool:
        if not isinstance(node, dict):
            return False
        type_name = node.get("type")
        if not isinstance(type_name, str) or type_name == "":
            return False
        if type_name not in seen:
            seen.add(type_name)
            result.append(type_name)
        children = node.get("children", [])
        if not isinstance(children, list):
            return False
        return all(visit(child) for child in children)

    return result if visit(recipe["root"]) else None


def _scene_component_types(scene: dict[str, Any]) -> set[str]:
    component_types: set[str] = set()

    def visit_entity(entity: Any) -> None:
        if not isinstance(entity, dict):
            return
        components = entity.get("components", [])
        if isinstance(components, list):
            for component in components:
                if not isinstance(component, dict):
                    continue
                type_name = component.get("type")
                if isinstance(type_name, str) and type_name:
                    component_types.add(type_name)
        children = entity.get("children", [])
        if isinstance(children, list):
            for child in children:
                visit_entity(child)

    entities = scene.get("entities", [])
    if isinstance(entities, list):
        for entity in entities:
            visit_entity(entity)
    return component_types


def _validate_scene_component_factories(
    scene: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
    context: str,
    policy: SceneComponentFactoryPolicy,
) -> None:
    component_types = _scene_component_types(scene)
    if not component_types:
        return

    try:
        from termin.bootstrap import bootstrap_runtime
        from termin.scene import ComponentRegistry

        bootstrap_runtime()
        registry = ComponentRegistry.instance()
    except (ImportError, RuntimeError) as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                f"Scene component factory registry is unavailable: {exc}",
            )
        )
        return

    for type_name in sorted(component_types):
        component_context = f"{context}:components[{type_name}]"
        if not registry.has(type_name):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    component_context,
                    f"Runtime component factory is not registered for '{type_name}'",
                )
            )
            continue
        info = registry.get_info(type_name)
        kind = info["kind"]
        if kind not in policy.allowed_kinds:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    component_context,
                    f"Runtime host does not support {kind} component factory '{type_name}'",
                )
            )
            continue
        if kind == "python" and info["owner"] not in policy.allowed_python_owners:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    component_context,
                    f"Python component factory '{type_name}' is owned by unpackaged module "
                    f"'{info['owner']}'",
                )
            )


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
    properties = spec.get("properties")
    if not isinstance(properties, list):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error", resource_path, "Runtime shader program properties must be a list"
            )
        )
    else:
        for index, prop in enumerate(properties):
            context = f"{resource_path}:properties[{index}]"
            if not isinstance(prop, dict):
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error", context, "Shader program property must be an object"
                    )
                )
                continue
            property_type = prop.get("property_type")
            if not isinstance(prop.get("name"), str) or prop["name"] == "":
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error", context, "Shader program property name must be non-empty"
                    )
                )
            if not isinstance(property_type, str) or property_type == "":
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error", context, "Shader program property_type must be non-empty"
                    )
                )
                continue
            expected_encoding = prop.get("expected_encoding")
            if property_type in {"Texture", "Texture2D"}:
                if expected_encoding not in {None, "srgb", "linear"}:
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            context,
                            "Shader program texture property expected_encoding "
                            "must be 'srgb' or 'linear'",
                        )
                    )
                default = prop.get("default")
                if default not in {None, "white", "normal"}:
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            context,
                            "Shader program texture property default must be "
                            "'white' or 'normal'",
                        )
                    )
                elif default == "normal" and expected_encoding == "srgb":
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            context,
                            "Shader program texture property normal default "
                            "requires linear expected_encoding",
                        )
                    )
            elif expected_encoding is not None:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        context,
                        "Shader program non-texture property must not have expected_encoding",
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

    language = shader_spec.get("language")
    if not isinstance(language, str) or language.lower() not in {"glsl", "hlsl", "slang"}:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                "Runtime shader spec must declare supported language: glsl, hlsl, or slang",
            )
        )

    artifact_role = shader_spec.get("artifact_role", "executable")
    if artifact_role not in {"executable", "pipeline_variant", "surface_producer"}:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                resource_path,
                "Runtime shader spec has unsupported artifact_role",
            )
        )

    shader_contract = shader_spec.get("shader_contract")
    if shader_contract is not None:
        contract_context = f"{resource_path}:shader_contract"
        if not isinstance(shader_contract, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", contract_context, "Shader contract must be an object"
                )
            )
        else:
            schema_version = shader_contract.get("schema_version", 1)
            if schema_version != 1:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        contract_context,
                        "Shader contract requires schema_version 1",
                    )
                )
            vertex_inputs = shader_contract.get("vertex_inputs")
            if not isinstance(vertex_inputs, list):
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        contract_context,
                        "Shader contract vertex_inputs must be a list",
                    )
                )
            else:
                seen_semantics: set[str] = set()
                for index, vertex_input in enumerate(vertex_inputs):
                    input_context = f"{contract_context}.vertex_inputs[{index}]"
                    valid = (
                        isinstance(vertex_input, dict)
                        and isinstance(vertex_input.get("semantic"), str)
                        and vertex_input.get("semantic") != ""
                        and isinstance(vertex_input.get("type"), int)
                        and not isinstance(vertex_input.get("type"), bool)
                        and 1 <= vertex_input.get("type") <= 5
                        and isinstance(vertex_input.get("required", True), bool)
                    )
                    if not valid:
                        diagnostics.append(
                            RuntimePackageExportDiagnostic(
                                "error",
                                input_context,
                                "Shader contract vertex input is incomplete or invalid",
                            )
                        )
                        continue
                    semantic = vertex_input["semantic"]
                    if semantic in seen_semantics:
                        diagnostics.append(
                            RuntimePackageExportDiagnostic(
                                "error",
                                input_context,
                                f"Duplicate shader contract vertex semantic '{semantic}'",
                            )
                        )
                    seen_semantics.add(semantic)

    artifacts = shader_spec.get("artifacts")
    if artifact_role == "surface_producer":
        if artifacts not in (None, {}):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    "Evaluator-only surface producer must not declare compiled GPU artifacts",
                )
            )
        if not isinstance(shader_spec.get("surface_producer"), dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    "Evaluator-only surface producer must contain surface_producer metadata",
                )
            )
        contract = shader_spec.get("surface_contract")
        if (
            not isinstance(contract, dict)
            or not isinstance(contract.get("id"), str)
            or not contract.get("id")
            or not isinstance(contract.get("version"), int)
            or contract.get("version", 0) <= 0
            or not isinstance(contract.get("interface_source_identity"), str)
            or not contract.get("interface_source_identity")
        ):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    resource_path,
                    "Evaluator-only surface producer must identify its exact surface contract interface",
                )
            )
        _validate_shader_stage_sources(
            package_root, resource_path, shader_spec, diagnostics
        )
        return shader_spec

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

        _validate_shader_artifact_stages(
            target_context,
            shader_spec,
            target_artifacts,
            diagnostics,
        )

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
            if target_name == "webgpu":
                _validate_webgpu_shader_layout(
                    package_root,
                    artifact_path,
                    stage_name,
                    stage_context,
                    diagnostics,
                )
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
    if binary_version != 4:
        raise ValueError(f"unsupported binary version {binary_version}")
    if descriptor_version != 4:
        raise ValueError(f"unsupported descriptor version {descriptor_version}")
    execution_model = u32()
    if execution_model not in (1, 2):
        raise ValueError(f"unsupported execution model {execution_model}")
    name = text()
    if not name:
        raise ValueError("descriptor name must be non-empty")

    pass_count = u32()
    resource_count = u32()
    dependency_count = u32()
    target_count = u32()
    resource_view_count = u32()
    fbo_composition_count = u32()
    if (
        pass_count > 65536
        or resource_count > 65536
        or target_count > 65536
        or resource_view_count > 65536
        or fbo_composition_count > 65536
    ):
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
        array_layers = u32()
        flags = u32()
        if not resource_name or not resource_type:
            raise ValueError(f"resource {index} lacks name or type")
        if resource_name in resource_names:
            raise ValueError(f"resource '{resource_name}' is duplicated")
        if samples == 0:
            raise ValueError(f"resource '{resource_name}' has zero samples")
        if array_layers == 0:
            raise ValueError(f"resource '{resource_name}' has zero array layers")
        attachment_flags = 0x0F
        if flags & ~attachment_flags:
            raise ValueError(f"resource '{resource_name}' has unknown flags 0x{flags:x}")
        if flags & 0x02 and not flags & 0x01:
            raise ValueError(f"resource '{resource_name}' enables color without declaring it")
        if flags & 0x08 and not flags & 0x04:
            raise ValueError(f"resource '{resource_name}' enables depth without declaring it")
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
                "array_layers": array_layers,
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
        if access not in (1, 2, 3):
            raise ValueError(f"dependency {index} has invalid access {access}")
        dependencies.append(
            {"pass_index": pass_index, "resource": resource_name, "access": access}
        )

    targets: list[dict[str, Any]] = []
    for index in range(target_count):
        viewport_name = text()
        export_name = text()
        color_content = u32()
        if color_content not in (0, 1, 2):
            raise ValueError(
                f"target {index} has invalid color content {color_content}"
            )
        targets.append(
            {
                "viewport_name": viewport_name,
                "export_name": export_name,
                "color_content": color_content,
                "width": i32(),
                "height": i32(),
            }
        )

    resource_views: list[dict[str, Any]] = []
    view_names: set[str] = set()
    for index in range(resource_view_count):
        view_name = text()
        parent = text()
        attachment = u32()
        if not view_name or not parent or attachment not in (1, 2):
            raise ValueError(f"resource view {index} is invalid")
        if view_name in resource_names or view_name in view_names:
            raise ValueError(f"resource view '{view_name}' is duplicated")
        if parent not in resource_names:
            raise ValueError(
                f"resource view '{view_name}' references missing parent '{parent}'"
            )
        view_names.add(view_name)
        resource_views.append(
            {"name": view_name, "parent": parent, "attachment": attachment}
        )

    fbo_compositions: list[dict[str, Any]] = []
    composition_names: set[str] = set()
    for index in range(fbo_composition_count):
        composition_name = text()
        color = text()
        depth = text()
        if not composition_name or (not color and not depth):
            raise ValueError(f"FBO composition {index} is invalid")
        if (
            composition_name in resource_names
            or composition_name in view_names
            or composition_name in composition_names
        ):
            raise ValueError(f"FBO composition '{composition_name}' is duplicated")
        for attachment_name, expected_kind in ((color, 1), (depth, 2)):
            if not attachment_name:
                continue
            if attachment_name in resource_names:
                continue
            view = next(
                (item for item in resource_views if item["name"] == attachment_name),
                None,
            )
            if view is None:
                raise ValueError(
                    f"FBO composition '{composition_name}' references missing attachment '{attachment_name}'"
                )
            if view["attachment"] != expected_kind:
                raise ValueError(
                    f"FBO composition '{composition_name}' uses view '{attachment_name}' for the wrong attachment kind"
                )
        composition_names.add(composition_name)
        fbo_compositions.append(
            {"name": composition_name, "color": color, "depth": depth}
        )

    dependency_resources = resource_names | view_names | composition_names
    for index, dependency in enumerate(dependencies):
        if dependency["resource"] not in dependency_resources:
            raise ValueError(
                f"dependency {index} references missing resource '{dependency['resource']}'"
            )
    if offset != len(payload):
        raise ValueError("descriptor contains trailing data")
    return {
        "binary_version": binary_version,
        "descriptor_version": descriptor_version,
        "execution_model": execution_model,
        "name": name,
        "passes": passes,
        "resources": resources,
        "dependencies": dependencies,
        "targets": targets,
        "resource_views": resource_views,
        "fbo_compositions": fbo_compositions,
    }


def _validate_shader_artifact_stages(
    target_context: str,
    shader_spec: dict[str, Any],
    target_artifacts: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    source_fields = {
        "vertex": "vertex_source_path",
        "fragment": "fragment_source_path",
        "geometry": "geometry_source_path",
    }
    for required_stage, source_field in source_fields.items():
        if source_field not in shader_spec:
            continue
        if required_stage not in target_artifacts:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    target_context,
                    f"Runtime shader artifact target must contain '{required_stage}' stage",
                )
            )
    for stage_name in target_artifacts:
        source_field = source_fields.get(stage_name)
        if source_field is not None and source_field not in shader_spec:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"{target_context}.{stage_name}",
                    f"Runtime shader artifact stage '{stage_name}' has no corresponding '{source_field}'",
                )
            )


def _validate_webgpu_shader_layout(
    package_root: Path,
    artifact_path: str,
    stage_name: str,
    stage_context: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    layout_rel = f"{artifact_path}.layout.json"
    layout_path = package_root / layout_rel
    layout = _read_json_file(layout_path, layout_rel, diagnostics)
    if layout is None:
        return
    if (
        layout.get("version") != 3
        or layout.get("target") != "webgpu"
        or layout.get("stage") != stage_name
        or not isinstance(layout.get("resources"), list)
    ):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                stage_context,
                "WebGPU shader artifact requires a version 3 webgpu layout sidecar for the same stage",
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
            if field_name == "fragment_source_path":
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
