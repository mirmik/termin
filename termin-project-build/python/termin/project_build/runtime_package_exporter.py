"""Runtime package exporter.

The exporter writes the package contract consumed by termin-runtime:

    manifest.json
    scene.json
    pipelines/*.pipeline-template
    meshes/*.tmesh.json
    materials/*.tmat.json
    textures/*.texture.json
    textures/*.{png,jpg,jpeg,tga,bmp}
    shaders/*.shader.json
    shaders/*.shader-program.json
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
    ShaderSpec as _ShaderSpec,
)
from termin.project_build.runtime_package.meshes import write_meshes as _write_meshes
from termin.project_build.runtime_package.materials import (
    export_material_spec,
    fallback_material_spec,
    material_textures_to_json as _material_textures_to_json,
    shader_to_spec as _shader_to_spec,
    write_materials,
)
from termin.project_build.runtime_package.package_files import (
    resource_sort_key as _resource_sort_key,
    write_clean_package_dir as _write_clean_package_dir,
    write_json as _write_json,
)
from termin.project_build.runtime_package.pipelines import (
    CompiledPipelineExport as _CompiledPipelineExport,
    write_pipelines as _write_pipelines,
)
from termin.project_build.runtime_package.scene_refs import (
    collect_project_material_refs as _collect_project_material_refs,
    collect_runtime_refs as _collect_runtime_refs,
    read_scene_data as _read_scene_data,
    resolve_entry_scene as _resolve_entry_scene,
)
from termin.project_build.runtime_package.shaders import (
    DEFAULT_SHADER_LANGUAGE,
    DEFAULT_SHADER_UUID,
    ENGINE_TEXT3D_SHADER_UUID,
    default_pipeline_engine_shaders as _default_pipeline_engine_shaders,
    default_shader_spec as _default_shader_spec,
    normalize_shader_targets as _normalize_shader_targets,
    resolve_shader_compiler as _resolve_shader_compiler,
    write_default_pipeline_shader_artifacts as _write_default_pipeline_shader_artifacts,
    write_shader_programs as _write_shader_programs,
    write_shaders as _write_shaders,
)
from termin.project_build.runtime_package.textures import write_textures as _write_textures


DEFAULT_RESOURCE_POLICY = "strict"
SUPPORTED_RESOURCE_POLICIES = {"dev_smoke", "strict"}

__all__ = [
    "DEFAULT_RESOURCE_POLICY",
    "ENGINE_TEXT3D_SHADER_UUID",
    "RuntimePackageExportDiagnostic",
    "RuntimePackageExportResult",
    "SUPPORTED_RESOURCE_POLICIES",
    "_default_pipeline_engine_shaders",
    "_material_textures_to_json",
    "_resolve_shader_compiler",
    "export_runtime_package",
]


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
    shader_programs: dict[str, dict[str, Any]] = {}
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
        shader_programs,
        default_shader_language,
        resource_policy,
        refs.textures,
    )
    _write_textures(project_root_path, output_dir_path, refs.textures, resources, diagnostics)
    compiled_pipelines = _write_pipelines(
        project_root_path, output_dir_path, refs.pipelines, resources, diagnostics
    )
    _collect_pipeline_shader_usages(scene_data, compiled_pipelines, diagnostics, shaders)
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
    _write_shader_programs(output_dir_path, shader_programs, resources)
    _write_default_pipeline_shader_artifacts(
        output_dir_path,
        diagnostics,
        shader_compiler,
        requested_shader_targets,
    )
    resources.sort(key=_resource_sort_key)

    manifest = {
        "version": 1,
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


def _collect_pipeline_shader_usages(
    scene_data: dict[str, Any],
    pipelines: list[_CompiledPipelineExport],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, _ShaderSpec],
) -> None:
    if not pipelines:
        return

    try:
        from termin.bootstrap import bootstrap_player
        from termin.default_assets.resource_manager import DefaultResourceManager
        from termin.engine import deserialize_scene
        from termin.render_framework import collect_shader_usages_for_pipeline

        bootstrap_player()
        resource_manager = DefaultResourceManager.instance()
        resource_manager.register_builtin_frame_passes()
    except Exception as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="error",
                path="pipelines",
                message=f"Runtime exporter failed to initialize pipeline shader usage collection: {exc}",
            )
        )
        return

    scene = None
    try:
        scene = deserialize_scene(scene_data, "runtime-package-shader-usage")
    except Exception as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="error",
                path="scene.json",
                message=f"Runtime exporter failed to deserialize scene for shader usage collection: {exc}",
            )
        )
        return

    try:
        for compiled in pipelines:
            pipeline_rel = compiled.resource_path
            try:
                pipeline = compiled.asset.pipeline
                if pipeline is None:
                    raise ValueError("compiled pipeline template could not be instantiated")
                try:
                    for shader in collect_shader_usages_for_pipeline(scene.scene_handle(), pipeline):
                        shaders[shader.uuid] = _shader_to_spec(shader)
                finally:
                    pipeline.destroy()
            except Exception as exc:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        level="error",
                        path=pipeline_rel,
                        message=f"Runtime exporter failed to collect pipeline shader usages: {exc}",
                    )
                )
    finally:
        scene.destroy()


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
    shader_programs: dict[str, dict[str, Any]],
    default_shader_language: str,
    resource_policy: str,
    texture_refs: dict[str, str],
) -> None:
    write_materials(
        package_dir,
        materials,
        resources,
        diagnostics,
        shaders,
        shader_programs,
        default_shader_language,
        resource_policy,
        DEFAULT_SHADER_UUID,
        _default_shader_spec,
        texture_refs,
    )


def _export_material_spec(
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, _ShaderSpec],
    default_shader_language: str,
    resource_policy: str,
) -> dict[str, Any] | None:
    shader_programs: dict[str, dict[str, Any]] = {}
    return export_material_spec(
        uuid_value,
        name,
        diagnostics,
        shaders,
        shader_programs,
        default_shader_language,
        resource_policy,
        DEFAULT_SHADER_UUID,
        _default_shader_spec,
    )


def _fallback_material_spec(uuid_value: str, name: str) -> dict[str, Any]:
    return fallback_material_spec(uuid_value, name, DEFAULT_SHADER_UUID)
