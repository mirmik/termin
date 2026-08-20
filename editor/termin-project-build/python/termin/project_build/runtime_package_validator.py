"""Validate runtime package manifests before target packaging."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic
from termin.project_build.runtime_package_resource_validator import (
    SceneComponentFactoryPolicy,
    _is_portable_scene_identity,
    _read_json_file,
    _resource_path,
    _scene_component_types,
    _validate_scene_component_factories,
    _validate_relative_existing_path,
    _validate_resources,
    _validate_shader_resource,
)


SUPPORTED_RUNTIME_BACKENDS = frozenset({"vulkan", "opengl", "opengl330", "webgl2", "d3d11", "webgpu"})
RUNTIME_PACKAGE_SCHEMA_VERSION = 3


ComponentFactoryPreparer = Callable[
    [frozenset[str]],
    list[RuntimePackageExportDiagnostic],
]


def validate_runtime_package(
    package_dir: str | Path,
    *,
    component_factory_policy: SceneComponentFactoryPolicy | None = None,
    prepare_component_factories: ComponentFactoryPreparer | None = None,
) -> list[RuntimePackageExportDiagnostic]:
    package_root = Path(package_dir).resolve()
    manifest_path = package_root / "manifest.json"
    diagnostics: list[RuntimePackageExportDiagnostic] = []

    manifest = _read_manifest(manifest_path, diagnostics)
    if manifest is None:
        return diagnostics

    _validate_version(manifest, diagnostics)
    _validate_world_controller(manifest, diagnostics)
    scenes = _validate_scenes(package_root, manifest, diagnostics)
    resource_index = _validate_resources(package_root, manifest, diagnostics)
    component_types = frozenset(
        type_name
        for _identity, scene in scenes
        for type_name in _scene_component_types(scene)
    )
    if prepare_component_factories is not None:
        diagnostics.extend(prepare_component_factories(component_types))
    factory_policy = component_factory_policy or SceneComponentFactoryPolicy()
    for identity, scene in scenes:
        _validate_scene_resource_references(
            scene,
            resource_index,
            diagnostics,
            f"scenes[{identity}]",
        )
        _validate_scene_component_factories(
            scene,
            diagnostics,
            f"scenes[{identity}]",
            factory_policy,
        )
    _validate_resource_graph(resource_index, diagnostics)
    _validate_target_requirements(manifest, resource_index, diagnostics)
    _validate_pipeline_shader_requirements(package_root, manifest, diagnostics)
    _validate_builtin_shader_contract(package_root, manifest, diagnostics)
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


def _validate_world_controller(
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    if "world_controller" not in manifest:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "world_controller",
                "Runtime package manifest must explicitly define world_controller as null or {module, type}",
            )
        )
        return
    value = manifest["world_controller"]
    if value is None:
        return
    if not isinstance(value, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "world_controller",
                "Runtime package world_controller must be null or an object",
            )
        )
        return
    expected = {"module", "type"}
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        detail: list[str] = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if unexpected:
            detail.append("unexpected " + ", ".join(unexpected))
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "world_controller",
                "Runtime package world_controller requires exactly module and type ("
                + "; ".join(detail)
                + ")",
            )
        )
        return
    for field in ("module", "type"):
        field_value = value[field]
        if (
            not isinstance(field_value, str)
            or not field_value
            or field_value.strip() != field_value
        ):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"world_controller.{field}",
                    f"Runtime package world_controller.{field} must be a non-empty trimmed string",
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
    program_resource = (
        resource_index.get(program_uuid)
        if isinstance(program_uuid, str) and program_uuid != ""
        else None
    )
    program_spec = (
        program_resource.get("spec")
        if isinstance(program_resource, dict)
        else None
    )
    texture_contract: dict[str, str | None] = {}
    if isinstance(program_spec, dict):
        properties = program_spec.get("properties")
        if isinstance(properties, list):
            texture_contract = {
                prop["name"]: prop.get("expected_encoding")
                for prop in properties
                if isinstance(prop, dict)
                and prop.get("property_type") in {"Texture", "Texture2D"}
                and isinstance(prop.get("name"), str)
                and prop.get("expected_encoding") in {None, "srgb", "linear"}
            }
    for slot_name, reference in textures.items():
        if not isinstance(slot_name, str) or not isinstance(reference, dict):
            continue
        slot_declared = slot_name in texture_contract
        expected_encoding = texture_contract.get(slot_name)
        context = f"{resource_path}:textures.{slot_name}"
        if isinstance(program_spec, dict) and not slot_declared:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    f"Runtime material texture slot '{slot_name}' is not declared "
                    "by its shader program",
                )
            )
            continue
        if expected_encoding is None:
            if reference.get("kind") == "asset":
                uuid_value = reference.get("uuid")
                if isinstance(uuid_value, str) and uuid_value != "":
                    _validate_resource_ref(
                        uuid_value,
                        "texture",
                        resource_index,
                        diagnostics,
                        context,
                    )
            continue
        if reference.get("kind") == "builtin":
            if reference.get("name") == "normal" and expected_encoding != "linear":
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        context,
                        "Runtime builtin normal texture requires a Linear slot",
                    )
                )
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
                context,
            )
            texture_resource = resource_index.get(uuid_value)
            texture_spec = (
                texture_resource.get("spec")
                if isinstance(texture_resource, dict)
                else None
            )
            import_settings = (
                texture_spec.get("import_settings")
                if isinstance(texture_spec, dict)
                else None
            )
            actual_encoding = (
                import_settings.get("encoding")
                if isinstance(import_settings, dict)
                else None
            )
            if actual_encoding in {"srgb", "linear"} and actual_encoding != expected_encoding:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "warning",
                        context,
                        f"Runtime material texture slot expects {expected_encoding}, "
                        f"but texture '{uuid_value}' is {actual_encoding}; "
                        "the binding remains renderable",
                    )
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


def _validate_builtin_shader_contract(
    package_root: Path,
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    contract = manifest.get("builtin_shader_contract")
    if contract is None:
        return
    context = "manifest.json:builtin_shader_contract"
    if not isinstance(contract, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                "Runtime package built-in shader contract must be an object",
            )
        )
        return
    if contract.get("version") != 1:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                f"{context}.version",
                "Runtime package built-in shader contract requires version 1",
            )
        )

    catalog_path = contract.get("catalog")
    catalog: dict[str, Any] | None = None
    if not isinstance(catalog_path, str) or catalog_path == "":
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                f"{context}.catalog",
                "Runtime package built-in shader contract requires a catalog path",
            )
        )
    else:
        resolved_catalog_path = _validate_relative_existing_path(
            package_root,
            catalog_path,
            f"{context}.catalog",
            diagnostics,
        )
        if resolved_catalog_path is not None:
            catalog = _read_json_file(resolved_catalog_path, catalog_path, diagnostics)

    catalog_entries: dict[str, dict[str, Any]] = {}
    if catalog is not None:
        if catalog.get("version") != 1:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    catalog_path,
                    "Built-in shader catalog requires version 1",
                )
            )
        raw_catalog_shaders = catalog.get("shaders")
        if not isinstance(raw_catalog_shaders, list):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    catalog_path,
                    "Built-in shader catalog must contain a shader list",
                )
            )
        else:
            for index, entry in enumerate(raw_catalog_shaders):
                entry_context = f"{catalog_path}:shaders[{index}]"
                if not isinstance(entry, dict):
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            entry_context,
                            "Built-in shader catalog entry must be an object",
                        )
                    )
                    continue
                uuid_value = entry.get("uuid")
                if not isinstance(uuid_value, str) or uuid_value == "":
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            entry_context,
                            "Built-in shader catalog entry requires a non-empty UUID",
                        )
                    )
                    continue
                if uuid_value in catalog_entries:
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            entry_context,
                            f"Duplicate built-in shader catalog UUID '{uuid_value}'",
                        )
                    )
                    continue
                catalog_entries[uuid_value] = entry

    shaders = contract.get("shaders")
    if not isinstance(shaders, list) or not shaders:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                f"{context}.shaders",
                "Runtime package built-in shader contract requires a non-empty shader list",
            )
        )
        return

    required_backends = _manifest_required_backends(manifest)
    seen_uuids: set[str] = set()
    for index, shader in enumerate(shaders):
        shader_context = f"{context}.shaders[{index}]"
        if not isinstance(shader, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    shader_context,
                    "Runtime built-in shader entry must be an object",
                )
            )
            continue
        uuid_value = shader.get("uuid")
        if not isinstance(uuid_value, str) or uuid_value == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    shader_context,
                    "Runtime built-in shader entry requires a non-empty UUID",
                )
            )
            continue
        if uuid_value in seen_uuids:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    shader_context,
                    f"Duplicate runtime built-in shader UUID '{uuid_value}'",
                )
            )
            continue
        seen_uuids.add(uuid_value)

        catalog_entry = catalog_entries.get(uuid_value)
        if catalog is not None and catalog_entry is None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    shader_context,
                    f"Runtime built-in shader '{uuid_value}' is absent from its catalog",
                )
            )
        elif catalog_entry is not None and isinstance(catalog_path, str):
            _validate_runtime_required_catalog_sources(
                package_root,
                PurePosixPath(catalog_path).parent,
                uuid_value,
                catalog_entry,
                diagnostics,
            )

        artifacts = shader.get("artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    shader_context,
                    f"Runtime built-in shader '{uuid_value}' requires artifact mappings",
                )
            )
            continue
        artifact_backends = list(artifacts)
        if required_backends is not None and set(artifact_backends) != set(required_backends):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    shader_context,
                    f"Runtime built-in shader '{uuid_value}' artifact backends "
                    f"{artifact_backends} do not match runtime backend order {required_backends}",
                )
            )
        for backend, stages in artifacts.items():
            backend_context = f"{shader_context}.artifacts.{backend}"
            if backend not in SUPPORTED_RUNTIME_BACKENDS:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        backend_context,
                        f"Unsupported built-in shader artifact backend '{backend}'",
                    )
                )
                continue
            if not isinstance(stages, dict) or not stages:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        backend_context,
                        "Built-in shader backend requires a non-empty stage map",
                    )
                )
                continue
            for stage_name, artifact_path in stages.items():
                stage_context = f"{backend_context}.{stage_name}"
                if stage_name not in {"vertex", "fragment", "geometry"}:
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            stage_context,
                            f"Unsupported built-in shader stage '{stage_name}'",
                        )
                    )
                    continue
                if not isinstance(artifact_path, str) or artifact_path == "":
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            stage_context,
                            "Built-in shader artifact path must be a non-empty string",
                        )
                    )
                    continue
                expected_path = _builtin_shader_artifact_path(
                    uuid_value,
                    backend,
                    stage_name,
                )
                if artifact_path != expected_path:
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            stage_context,
                            f"Built-in shader artifact path must match runtime resolver path "
                            f"'{expected_path}'",
                        )
                    )
                    continue
                resolved_artifact = _validate_relative_existing_path(
                    package_root,
                    artifact_path,
                    stage_context,
                    diagnostics,
                )
                if (
                    resolved_artifact is not None
                    and (not resolved_artifact.is_file() or resolved_artifact.stat().st_size == 0)
                ):
                    diagnostics.append(
                        RuntimePackageExportDiagnostic(
                            "error",
                            artifact_path,
                            f"Built-in shader artifact is empty or not a file: {artifact_path}",
                        )
                    )


def _manifest_required_backends(manifest: dict[str, Any]) -> list[str] | None:
    requirements = manifest.get("target_requirements")
    if not isinstance(requirements, dict):
        return None
    backends = requirements.get("backends")
    if not isinstance(backends, list) or not all(
        isinstance(backend, str) and backend in SUPPORTED_RUNTIME_BACKENDS
        for backend in backends
    ):
        return None
    return backends


def _validate_runtime_required_catalog_sources(
    package_root: Path,
    catalog_parent: PurePosixPath,
    shader_uuid: str,
    entry: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    language = entry.get("language")
    runtime_sources = entry.get("runtime_sources", [])
    if not isinstance(runtime_sources, list) or not all(
        isinstance(source_path, str) and source_path != ""
        for source_path in runtime_sources
    ):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                f"builtin_shader_contract:{shader_uuid}",
                f"Built-in shader '{shader_uuid}' has invalid runtime source paths",
            )
        )
        return
    source_paths = set(runtime_sources)
    if language == "shader":
        program = entry.get("program")
        source_path = program.get("path") if isinstance(program, dict) else None
        if not isinstance(source_path, str) or source_path == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"builtin_shader_contract:{shader_uuid}",
                    f"Built-in shader program '{shader_uuid}' requires a source path",
                )
            )
            return
        source_paths.add(source_path)
    elif language == "glsl":
        stages = entry.get("stages")
        if not isinstance(stages, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"builtin_shader_contract:{shader_uuid}",
                    f"Built-in GLSL shader '{shader_uuid}' requires a stage map",
                )
            )
            return
        for stage in stages.values():
            source_path = stage if isinstance(stage, str) else (
                stage.get("path") if isinstance(stage, dict) else None
            )
            if not isinstance(source_path, str) or source_path == "":
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        f"builtin_shader_contract:{shader_uuid}",
                        f"Built-in GLSL shader '{shader_uuid}' has an invalid stage source",
                    )
                )
                continue
            source_paths.add(source_path)
    elif language != "slang":
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                f"builtin_shader_contract:{shader_uuid}",
                f"Built-in shader '{shader_uuid}' has unsupported language '{language}'",
            )
        )
        return

    for source_path in source_paths:
        package_source_path = (catalog_parent / PurePosixPath(source_path)).as_posix()
        _validate_relative_existing_path(
            package_root,
            package_source_path,
            f"builtin_shader_contract:{shader_uuid}",
            diagnostics,
        )


def _builtin_shader_artifact_path(uuid_value: str, backend: str, stage: str) -> str:
    common_stage_suffixes = {"vertex": "vert", "fragment": "frag", "geometry": "geom"}
    stage_suffix = (
        {"vertex": "vs", "fragment": "ps", "geometry": "gs"}[stage]
        if backend == "d3d11"
        else common_stage_suffixes[stage]
    )
    extension = {
        "vulkan": "spv",
        "opengl": "glsl",
        "opengl330": "glsl",
        "webgl2": "glsl",
        "d3d11": "cso",
        "webgpu": "wgsl",
    }[backend]
    return f"shaders/{backend}/{uuid_value}.{stage_suffix}.{extension}"


def _validate_pipeline_shader_requirements(
    package_root: Path,
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    requirements = manifest.get("pipeline_shader_requirements", [])
    if not isinstance(requirements, list):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json:pipeline_shader_requirements",
                "Pipeline shader requirements must be a list",
            )
        )
        return

    target_requirements = manifest.get("target_requirements", {})
    required_backends = (
        target_requirements.get("backends", [])
        if isinstance(target_requirements, dict)
        else []
    )
    valid_required_backends = (
        required_backends
        if isinstance(required_backends, list)
        and all(
            isinstance(item, str)
            and item in SUPPORTED_RUNTIME_BACKENDS
            for item in required_backends
        )
        else []
    )

    for requirement_index, requirement in enumerate(requirements):
        context = f"pipeline_shader_requirements[{requirement_index}]"
        if not isinstance(requirement, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", context, "Pipeline shader requirement must be an object"
                )
            )
            continue
        pipeline_name = requirement.get("pipeline")
        scene_path = requirement.get("scene")
        variants = requirement.get("variants")
        if not isinstance(pipeline_name, str) or not pipeline_name:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error", context, "Pipeline shader requirement has no pipeline name"
                )
            )
            continue
        if not isinstance(scene_path, str) or not scene_path:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    f"Pipeline '{pipeline_name}' shader requirement has no scene context",
                )
            )
        if not isinstance(variants, list) or not variants:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    f"Pipeline '{pipeline_name}' must declare its executable pass variants",
                )
            )
            continue

        for variant_index, variant in enumerate(variants):
            variant_context = f"{context}.variants[{variant_index}]"
            if not isinstance(variant, dict):
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        variant_context,
                        f"Pipeline '{pipeline_name}' pass variant must be an object",
                    )
                )
                continue
            shader_uuid = variant.get("uuid")
            shader_path = variant.get("path")
            source_identity = variant.get("source_identity")
            if not isinstance(shader_uuid, str) or not shader_uuid:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        variant_context,
                        f"Pipeline '{pipeline_name}' pass variant has no shader UUID",
                    )
                )
                continue
            if not isinstance(shader_path, str) or not shader_path:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        variant_context,
                        f"Pipeline '{pipeline_name}' pass variant '{shader_uuid}' has no spec path",
                    )
                )
                continue
            resolved = _validate_relative_existing_path(
                package_root, shader_path, variant_context, diagnostics
            )
            if resolved is None:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        variant_context,
                        f"Pipeline '{pipeline_name}' requires missing executable pass variant '{shader_uuid}'",
                    )
                )
                continue
            spec = _validate_shader_resource(
                package_root, shader_path, resolved, diagnostics
            )
            if not isinstance(spec, dict):
                continue
            if spec.get("uuid") != shader_uuid:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        variant_context,
                        f"Pipeline '{pipeline_name}' pass variant UUID does not match its shader spec",
                    )
                )
            if spec.get("artifact_role") == "surface_producer":
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        variant_context,
                        f"Pipeline '{pipeline_name}' requires executable pass variant '{shader_uuid}', not an evaluator-only producer",
                    )
                )
            if (
                not isinstance(source_identity, str)
                or not source_identity
                or spec.get("source_identity") != source_identity
            ):
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        variant_context,
                        f"Pipeline '{pipeline_name}' pass variant '{shader_uuid}' has stale composed-source identity",
                    )
                )
            artifacts = spec.get("artifacts")
            if valid_required_backends and (
                not isinstance(artifacts, dict)
                or set(artifacts) != set(valid_required_backends)
            ):
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        "error",
                        variant_context,
                        f"Pipeline '{pipeline_name}' pass variant '{shader_uuid}' does not cover required backends {valid_required_backends}",
                    )
                )


def _validate_required_backends(
    backends: list[Any],
    resource_index: dict[str, dict[str, Any]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    required_backends: list[str] = []
    for index, backend_name in enumerate(backends):
        if not isinstance(backend_name, str) or backend_name not in SUPPORTED_RUNTIME_BACKENDS:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    f"manifest.json:target_requirements.backends[{index}]",
                    "Runtime package backend must be one of: vulkan, opengl, opengl330, webgl2, d3d11, webgpu",
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
        if spec.get("artifact_role") == "surface_producer":
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
