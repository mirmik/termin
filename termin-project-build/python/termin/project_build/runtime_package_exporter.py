"""Runtime package exporter.

The exporter writes the package contract consumed by termin-runtime:

    manifest.json
    scene.json
    pipelines/*.pipeline.json
    meshes/*.tmesh.json
    materials/*.tmat.json
    shaders/*.shader.json
    shaders/vulkan/*.spv

When a referenced mesh/material exists in project sources or the current runtime
registries, the exporter writes real runtime artifacts. Missing registry entries
are build errors by default. Placeholder fallback artifacts are only emitted
under the explicit `dev_smoke` resource policy.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from termin.project_build.runtime_package.models import (
    RuntimePackageExportDiagnostic,
    RuntimePackageExportResult,
    RuntimeRefs as _RuntimeRefs,
    ShaderSpec as _ShaderSpec,
)
from termin.project_build.runtime_package.meshes import (
    attrib_type_to_json as _attrib_type_to_json,
    draw_mode_to_json as _draw_mode_to_json,
    export_mesh_spec as _export_mesh_spec,
    fallback_mesh_spec as _fallback_mesh_spec,
    find_mesh_source as _find_mesh_source,
    flat_number_list as _flat_number_list,
    iter_project_mesh_paths as _iter_project_mesh_paths,
    mesh_layout_to_json as _mesh_layout_to_json,
    mesh_source_to_spec as _mesh_source_to_spec,
    mesh_to_spec as _mesh_to_spec,
    resource_policy_allows_fallback as _resource_policy_allows_fallback,
    write_meshes as _write_meshes,
)
from termin.project_build.runtime_package.materials import (
    export_material_spec,
    fallback_material_spec,
    material_textures_to_json as _material_textures_to_json,
    material_to_spec as _material_to_spec,
    material_uniforms_to_json as _material_uniforms_to_json,
    resource_policy_allows_fallback as _material_resource_policy_allows_fallback,
    shader_language as _shader_language,
    shader_to_spec as _shader_to_spec,
    write_materials,
)
from termin.project_build.runtime_package.builtin_shader_catalog import (
    builtin_shader_catalog as _builtin_shader_catalog,
    builtin_shader_catalog_entry as _builtin_shader_catalog_entry,
    builtin_shader_catalog_path as _builtin_shader_catalog_path,
    builtin_shader_roots as _builtin_shader_roots,
    builtin_shader_source as _builtin_shader_source,
)
from termin.project_build.runtime_package.package_files import (
    append_project_file_diagnostic as _append_project_file_diagnostic,
    project_relative_path as _project_relative_path,
    resource_sort_key as _resource_sort_key,
    write_clean_package_dir as _write_clean_package_dir,
    write_json as _write_json,
)
from termin.project_build.runtime_package.pipelines import (
    find_pipeline_source as _find_pipeline_source,
    iter_project_pipeline_paths as _iter_project_pipeline_paths,
    safe_package_stem as _safe_package_stem,
    write_pipelines as _write_pipelines,
)
from termin.project_build.runtime_package.scene_refs import (
    collect_pipeline_refs as _collect_pipeline_refs,
    collect_project_material_refs as _collect_project_material_refs,
    collect_refs_recursive as _collect_refs_recursive,
    collect_runtime_refs as _collect_runtime_refs,
    collect_typed_ref as _collect_typed_ref,
    iter_project_material_paths as _iter_project_material_paths,
    looks_like_material_ref as _looks_like_material_ref,
    looks_like_mesh_ref as _looks_like_mesh_ref,
    read_scene_data as _read_scene_data,
    resolve_entry_scene as _resolve_entry_scene,
)
from termin.project_build.runtime_package.shaders import (
    DEFAULT_SHADER_LANGUAGE,
    DEFAULT_SHADER_NAME,
    DEFAULT_SHADER_SOURCE_PATH,
    DEFAULT_SHADER_TARGETS_BY_LANGUAGE as _DEFAULT_SHADER_TARGETS_BY_LANGUAGE,
    DEFAULT_SHADER_UUID,
    ENGINE_BLOOM_BRIGHT_SHADER_UUID,
    ENGINE_BLOOM_COMPOSITE_SHADER_UUID,
    ENGINE_BLOOM_DOWNSAMPLE_SHADER_UUID,
    ENGINE_BLOOM_UPSAMPLE_SHADER_UUID,
    ENGINE_CANVAS2D_SOLID_SHADER_UUID,
    ENGINE_CANVAS2D_TEXTURE_SHADER_UUID,
    ENGINE_FSQ_SHADER_UUID,
    ENGINE_GRAYSCALE_SHADER_UUID,
    ENGINE_SHADOW_MATERIAL_SHADER_UUID,
    ENGINE_SHADOW_SHADER_UUID,
    ENGINE_SKYBOX_SHADER_UUID,
    ENGINE_TEXT2D_SDF_SHADER_UUID,
    ENGINE_TEXT2D_SHADER_UUID,
    ENGINE_TEXT3D_SHADER_UUID,
    ENGINE_TONEMAP_SHADER_UUID,
    SUPPORTED_SHADER_TARGETS_BY_LANGUAGE as _SUPPORTED_SHADER_TARGETS_BY_LANGUAGE,
    TCGUI_UI_SHADER_NAME,
    TCGUI_UI_SHADER_UUID,
    EngineShaderArtifact as _EngineShaderArtifact,
    artifact_extension_for_target as _artifact_extension_for_target,
    artifact_filename as _artifact_filename,
    artifact_path_text as _artifact_path_text,
    artifact_stage_suffix as _artifact_stage_suffix,
    builtin_engine_shader_artifact as _builtin_engine_shader_artifact,
    builtin_engine_shader_program_stages as _builtin_engine_shader_program_stages,
    builtin_engine_stage_entry as _builtin_engine_stage_entry,
    builtin_engine_stage_source as _builtin_engine_stage_source,
    compile_shader_stage as _compile_shader_stage,
    copy_default_spirv as _copy_default_spirv,
    default_pipeline_engine_shaders as _default_pipeline_engine_shaders,
    default_shader_spec as _default_shader_spec,
    executable_command as _executable_command,
    normalize_default_shader_language as _normalize_default_shader_language,
    normalize_shader_targets as _normalize_shader_targets,
    resolve_shader_compiler as _resolve_shader_compiler,
    shader_targets_for_language as _shader_targets_for_language,
    source_extension_for_language as _source_extension_for_language,
    write_default_pipeline_shader_artifacts as _write_default_pipeline_shader_artifacts,
    write_engine_shader_artifact as _write_engine_shader_artifact,
    write_shader as _write_shader,
    write_shaders as _write_shaders,
    write_tcgui_ui_shader_artifacts as _write_tcgui_ui_shader_artifacts,
)


DEFAULT_RESOURCE_POLICY = "strict"
SUPPORTED_RESOURCE_POLICIES = {"dev_smoke", "strict"}


def export_runtime_package(
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path,
    shader_compiler: str | Path | None = None,
    default_shader_language: str = DEFAULT_SHADER_LANGUAGE,
    resource_policy: str = DEFAULT_RESOURCE_POLICY,
    shader_targets: Iterable[str] | None = None,
) -> RuntimePackageExportResult:
    _validate_resource_policy(resource_policy)
    requested_shader_targets = _normalize_shader_targets(shader_targets)
    project_root_path = Path(project_root).resolve()
    entry_scene_path = _resolve_entry_scene(project_root_path, Path(entry_scene))
    output_dir_path = Path(output_dir).resolve()

    scene_data = _read_scene_data(entry_scene_path)
    from termin.glb.scene_animation_repair import repair_glb_animation_player_clip_refs

    repair_glb_animation_player_clip_refs(scene_data)
    diagnostics: list[RuntimePackageExportDiagnostic] = []
    refs = _collect_runtime_refs(scene_data, diagnostics)
    _collect_project_material_refs(project_root_path, refs, diagnostics)

    _write_clean_package_dir(output_dir_path)
    scene_path = output_dir_path / "scene.json"
    _write_json(scene_path, scene_data)

    resources: list[dict[str, str]] = []
    shaders: dict[str, _ShaderSpec] = {}
    _write_meshes(
        project_root_path,
        output_dir_path,
        refs.meshes,
        resources,
        diagnostics,
        resource_policy,
    )
    _write_materials(
        output_dir_path,
        refs.materials,
        resources,
        diagnostics,
        shaders,
        default_shader_language,
        resource_policy,
    )
    _write_pipelines(project_root_path, output_dir_path, refs.pipelines, resources, diagnostics)
    if not shaders:
        shaders[DEFAULT_SHADER_UUID] = _default_shader_spec(default_shader_language)
    _write_shaders(
        output_dir_path,
        shaders,
        resources,
        diagnostics,
        shader_compiler,
        requested_shader_targets,
    )
    _write_default_pipeline_shader_artifacts(
        output_dir_path,
        diagnostics,
        shader_compiler,
        requested_shader_targets,
    )
    resources.sort(key=_resource_sort_key)

    manifest = {
        "version": 1,
        "shader_artifact_root": ".",
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
        "resources": resources,
        "scene": "scene.json",
    }
    if requested_shader_targets is not None:
        manifest["target_requirements"] = {
            "shader_targets": list(requested_shader_targets),
        }
    manifest_path = output_dir_path / "manifest.json"
    _write_json(manifest_path, manifest)

    return RuntimePackageExportResult(
        package_dir=output_dir_path,
        manifest_path=manifest_path,
        scene_path=scene_path,
        diagnostics=diagnostics,
    )


def _validate_resource_policy(resource_policy: str) -> None:
    if resource_policy not in SUPPORTED_RESOURCE_POLICIES:
        supported = ", ".join(sorted(SUPPORTED_RESOURCE_POLICIES))
        raise ValueError(
            f"Unsupported runtime package resource_policy '{resource_policy}'. "
            f"Supported values: {supported}"
        )


def _write_materials(
    package_dir: Path,
    materials: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, _ShaderSpec],
    default_shader_language: str,
    resource_policy: str,
) -> None:
    write_materials(
        package_dir,
        materials,
        resources,
        diagnostics,
        shaders,
        default_shader_language,
        resource_policy,
        DEFAULT_SHADER_UUID,
        _default_shader_spec,
    )


def _export_material_spec(
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, _ShaderSpec],
    default_shader_language: str,
    resource_policy: str,
) -> dict[str, Any] | None:
    return export_material_spec(
        uuid_value,
        name,
        diagnostics,
        shaders,
        default_shader_language,
        resource_policy,
        DEFAULT_SHADER_UUID,
        _default_shader_spec,
    )


def _fallback_material_spec(uuid_value: str, name: str) -> dict[str, Any]:
    return fallback_material_spec(uuid_value, name, DEFAULT_SHADER_UUID)
