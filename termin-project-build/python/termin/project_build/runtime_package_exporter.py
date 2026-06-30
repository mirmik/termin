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

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
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
from termin.shader_tools import existing_executable, resolve_path_tool, resolve_sdk_tool


DEFAULT_SHADER_UUID = "termin-runtime-default-color"
DEFAULT_SHADER_NAME = "TerminRuntimeDefaultColor"
DEFAULT_SHADER_SOURCE_PATH = "termin-runtime/default-color"
DEFAULT_SHADER_LANGUAGE = "slang"
DEFAULT_RESOURCE_POLICY = "strict"
SUPPORTED_RESOURCE_POLICIES = {"dev_smoke", "strict"}

_DEFAULT_SHADER_TARGETS_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    "glsl": ("vulkan",),
    "slang": ("vulkan", "opengl", "d3d11"),
}

_SUPPORTED_SHADER_TARGETS_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    "glsl": ("vulkan",),
    "slang": ("vulkan", "opengl", "d3d11"),
    "hlsl": ("d3d11",),
}


ENGINE_SKYBOX_SHADER_UUID = "termin-engine-skybox"
ENGINE_FSQ_SHADER_UUID = "termin-engine-fsq"
ENGINE_SHADOW_SHADER_UUID = "termin-engine-shadow"
ENGINE_GRAYSCALE_SHADER_UUID = "termin-engine-grayscale"
ENGINE_BLOOM_BRIGHT_SHADER_UUID = "termin-engine-bloom-bright"
ENGINE_BLOOM_DOWNSAMPLE_SHADER_UUID = "termin-engine-bloom-downsample"
ENGINE_BLOOM_UPSAMPLE_SHADER_UUID = "termin-engine-bloom-upsample"
ENGINE_BLOOM_COMPOSITE_SHADER_UUID = "termin-engine-bloom-composite"
ENGINE_TONEMAP_SHADER_UUID = "termin-engine-tonemap"
ENGINE_CANVAS2D_SOLID_SHADER_UUID = "termin-engine-canvas2d-solid"
ENGINE_CANVAS2D_TEXTURE_SHADER_UUID = "termin-engine-canvas2d-texture"
ENGINE_TEXT2D_SHADER_UUID = "termin-engine-text2d"
ENGINE_TEXT2D_SDF_SHADER_UUID = "termin-engine-text2d-sdf"
ENGINE_TEXT3D_SHADER_UUID = "termin-engine-text3d"
ENGINE_SHADOW_MATERIAL_SHADER_UUID = "termin-engine-shadow-material"
TCGUI_UI_SHADER_UUID = "termin-tcgui-ui-engine"
TCGUI_UI_SHADER_NAME = "UIEngineVSFS"


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
    refs = _collect_runtime_refs(scene_data)
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


def _normalize_shader_targets(shader_targets: Iterable[str] | None) -> tuple[str, ...] | None:
    if shader_targets is None:
        return None
    normalized: list[str] = []
    for target in shader_targets:
        text = str(target).strip().lower()
        if text == "":
            raise ValueError("Runtime package shader target must be a non-empty string")
        if text not in {"vulkan", "opengl", "d3d11"}:
            raise ValueError(f"Unsupported runtime package shader target: {target}")
        if text not in normalized:
            normalized.append(text)
    if not normalized:
        raise ValueError("Runtime package must request at least one shader target")
    return tuple(normalized)


def _shader_targets_for_language(
    language: str,
    requested_targets: tuple[str, ...] | None,
    context: str,
) -> tuple[str, ...]:
    if requested_targets is None:
        targets = _DEFAULT_SHADER_TARGETS_BY_LANGUAGE.get(language)
        if targets is None:
            raise ValueError(f"{context} has unsupported language: {language}")
        return targets

    supported = _SUPPORTED_SHADER_TARGETS_BY_LANGUAGE.get(language)
    if supported is None:
        raise ValueError(f"{context} has unsupported language: {language}")
    unsupported = [target for target in requested_targets if target not in supported]
    if unsupported:
        unsupported_text = ", ".join(unsupported)
        supported_text = ", ".join(supported)
        raise ValueError(
            f"{context} language '{language}' cannot produce requested shader "
            f"target(s): {unsupported_text}; supported targets: {supported_text}"
        )
    return requested_targets


def _artifact_extension_for_target(target: str) -> str:
    if target == "vulkan":
        return "spv"
    if target == "opengl":
        return "glsl"
    if target == "d3d11":
        return "cso"
    raise ValueError(f"Unsupported shader target: {target}")


def _artifact_stage_suffix(target: str, stage_name: str, fallback_stage_ext: str) -> str:
    if target != "d3d11":
        return fallback_stage_ext
    if stage_name == "vertex":
        return "vs"
    if stage_name == "fragment":
        return "ps"
    if stage_name == "geometry":
        return "gs"
    raise ValueError(f"Unsupported D3D11 shader stage: {stage_name}")


def _artifact_filename(shader_uuid: str, target: str, stage_name: str, fallback_stage_ext: str) -> str:
    suffix = _artifact_stage_suffix(target, stage_name, fallback_stage_ext)
    extension = _artifact_extension_for_target(target)
    return f"{shader_uuid}.{suffix}.{extension}"


def _artifact_path_text(shader_uuid: str, target: str, stage_name: str, fallback_stage_ext: str) -> str:
    return f"shaders/{target}/{_artifact_filename(shader_uuid, target, stage_name, fallback_stage_ext)}"


def _default_shader_spec(language: str) -> _ShaderSpec:
    normalized = _normalize_default_shader_language(language)
    if normalized == "glsl":
        raise ValueError("The runtime default shader is Slang-only")
    if normalized == "slang":
        entry = _builtin_shader_catalog_entry(DEFAULT_SHADER_UUID)
        stages = entry.get("stages")
        if not isinstance(stages, dict):
            raise ValueError(f"Built-in shader '{DEFAULT_SHADER_UUID}' has no stage map")
        return _ShaderSpec(
            uuid=DEFAULT_SHADER_UUID,
            name=str(entry.get("name", DEFAULT_SHADER_NAME)),
            source_path=DEFAULT_SHADER_SOURCE_PATH,
            vertex_source=_builtin_engine_stage_source(DEFAULT_SHADER_UUID, stages, "vertex"),
            fragment_source=_builtin_engine_stage_source(DEFAULT_SHADER_UUID, stages, "fragment"),
            geometry_source="",
            language="slang",
            vertex_entry=_builtin_engine_stage_entry(stages, "vertex"),
            fragment_entry=_builtin_engine_stage_entry(stages, "fragment"),
            allow_precompiled_default=False,
        )
    raise ValueError(f"Unsupported default shader language: {language}")


def _normalize_default_shader_language(language: str) -> str:
    text = language.strip().lower()
    if text.endswith(".glsl") or text == "glsl":
        return "glsl"
    if text.endswith(".slang") or text == "slang":
        return "slang"
    raise ValueError(f"Unsupported default shader language: {language}")


def _write_shaders(
    package_dir: Path,
    shaders: dict[str, _ShaderSpec],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader_compiler: str | Path | None,
    requested_targets: tuple[str, ...] | None,
) -> None:
    compiler = _resolve_shader_compiler(Path(shader_compiler) if shader_compiler is not None else None)
    for shader in sorted(shaders.values(), key=lambda item: item.uuid):
        _write_shader(package_dir, resources, diagnostics, shader, compiler, requested_targets)


def _write_shader(
    package_dir: Path,
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader: _ShaderSpec,
    compiler: Path | None,
    requested_targets: tuple[str, ...] | None,
) -> None:
    targets = _shader_targets_for_language(
        shader.language,
        requested_targets,
        f"Shader '{shader.uuid}'",
    )

    shader_dir = package_dir / "shaders"
    vulkan_dir = shader_dir / "vulkan"
    shader_dir.mkdir(parents=True, exist_ok=True)
    vulkan_dir.mkdir(parents=True, exist_ok=True)
    for target in targets:
        (shader_dir / target).mkdir(parents=True, exist_ok=True)

    source_ext = _source_extension_for_language(shader.language)
    shared_stage_source = (
        shader.language == "slang"
        and shader.geometry_source == ""
        and shader.vertex_source == shader.fragment_source
    )
    if shared_stage_source:
        vertex_source_path = vulkan_dir / f"{shader.uuid}.{source_ext}"
        fragment_source_path = vertex_source_path
    else:
        vertex_source_path = vulkan_dir / f"{shader.uuid}.vert.{source_ext}"
        fragment_source_path = vulkan_dir / f"{shader.uuid}.frag.{source_ext}"
    vertex_source_path.write_text(shader.vertex_source, encoding="utf-8")
    if fragment_source_path != vertex_source_path:
        fragment_source_path.write_text(shader.fragment_source, encoding="utf-8")

    geometry_source_path = None
    if shader.geometry_source != "":
        geometry_source_path = vulkan_dir / f"{shader.uuid}.geom.{source_ext}"
        geometry_source_path.write_text(shader.geometry_source, encoding="utf-8")

    if compiler is None and shader.allow_precompiled_default and targets == ("vulkan",):
        _copy_default_spirv(vulkan_dir / f"{shader.uuid}.vert.spv", "termin-android-scene-color.vert.spv")
        _copy_default_spirv(vulkan_dir / f"{shader.uuid}.frag.spv", "termin-android-scene-color.frag.spv")
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"shaders/{shader.uuid}.shader.json",
                message="Runtime exporter reused built-in default SPIR-V artifacts",
            )
        )
    else:
        if compiler is None:
            raise FileNotFoundError(
                "Shader compiler 'termin_shaderc' was not found. "
                "Pass shader_compiler=..., add it to PATH, or set TERMIN_SDK."
            )
        for target in targets:
            target_dir = shader_dir / target
            _compile_shader_stage(
                compiler,
                shader.language,
                target,
                "vertex",
                vertex_source_path,
                target_dir / _artifact_filename(shader.uuid, target, "vertex", "vert"),
                f"{shader.name or shader.uuid}:vertex",
                shader.vertex_entry,
            )
            _compile_shader_stage(
                compiler,
                shader.language,
                target,
                "fragment",
                fragment_source_path,
                target_dir / _artifact_filename(shader.uuid, target, "fragment", "frag"),
                f"{shader.name or shader.uuid}:fragment",
                shader.fragment_entry,
            )
            if geometry_source_path is not None:
                _compile_shader_stage(
                    compiler,
                    shader.language,
                    target,
                    "geometry",
                    geometry_source_path,
                    target_dir / _artifact_filename(shader.uuid, target, "geometry", "geom"),
                    f"{shader.name or shader.uuid}:geometry",
                    shader.geometry_entry,
                )

    shader_spec: dict[str, Any] = {
        "uuid": shader.uuid,
        "name": shader.name or shader.uuid,
        "language": shader.language,
        "vertex_source_path": (
            f"shaders/vulkan/{shader.uuid}.{source_ext}"
            if shared_stage_source
            else f"shaders/vulkan/{shader.uuid}.vert.{source_ext}"
        ),
        "fragment_source_path": (
            f"shaders/vulkan/{shader.uuid}.{source_ext}"
            if shared_stage_source
            else f"shaders/vulkan/{shader.uuid}.frag.{source_ext}"
        ),
        "vertex_entry": shader.vertex_entry,
        "fragment_entry": shader.fragment_entry,
        "source_path": shader.source_path,
        "features": int(shader.features),
        "artifacts": {
            target: {
                "vertex": _artifact_path_text(shader.uuid, target, "vertex", "vert"),
                "fragment": _artifact_path_text(shader.uuid, target, "fragment", "frag"),
            }
            for target in targets
        },
    }
    if geometry_source_path is not None:
        shader_spec["geometry_source_path"] = f"shaders/vulkan/{shader.uuid}.geom.{source_ext}"
        shader_spec["geometry_entry"] = shader.geometry_entry
        for target in targets:
            shader_spec["artifacts"][target]["geometry"] = _artifact_path_text(
                shader.uuid,
                target,
                "geometry",
                "geom",
            )

    shader_spec_path = shader_dir / f"{shader.uuid}.shader.json"
    _write_json(shader_spec_path, shader_spec)
    resources.append(
        {
            "type": "shader",
            "uuid": shader.uuid,
            "path": f"shaders/{shader.uuid}.shader.json",
        }
    )


@dataclass(frozen=True)
class _EngineShaderArtifact:
    uuid: str
    name: str
    language: str = "glsl"
    vertex_source: str = ""
    fragment_source: str = ""
    vertex_entry: str = "main"
    fragment_entry: str = "main"


def _write_default_pipeline_shader_artifacts(
    package_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader_compiler: str | Path | None,
    requested_targets: tuple[str, ...] | None = None,
) -> None:
    compiler = _resolve_shader_compiler(Path(shader_compiler) if shader_compiler is not None else None)
    if compiler is None:
        raise FileNotFoundError(
            "Shader compiler 'termin_shaderc' was not found. "
            "Default pipeline shaders require precompiled SPIR-V for Android."
        )

    for shader in _default_pipeline_engine_shaders():
        _write_engine_shader_artifact(package_dir, diagnostics, shader, compiler, requested_targets)
    _write_tcgui_ui_shader_artifacts(package_dir, compiler)


def _default_pipeline_engine_shaders() -> list[_EngineShaderArtifact]:
    return [
        _builtin_engine_shader_artifact(ENGINE_FSQ_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_SKYBOX_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_SHADOW_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_GRAYSCALE_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_BLOOM_BRIGHT_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_BLOOM_DOWNSAMPLE_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_BLOOM_UPSAMPLE_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_BLOOM_COMPOSITE_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_TONEMAP_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_CANVAS2D_SOLID_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_CANVAS2D_TEXTURE_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_TEXT2D_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_TEXT2D_SDF_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_TEXT3D_SHADER_UUID),
        _builtin_engine_shader_artifact(ENGINE_SHADOW_MATERIAL_SHADER_UUID),
    ]


def _builtin_engine_shader_artifact(uuid_value: str) -> _EngineShaderArtifact:
    entry = _builtin_shader_catalog_entry(uuid_value)
    language = str(entry.get("language", "glsl"))
    if language == "shader":
        program_language, vertex_source, fragment_source = _builtin_engine_shader_program_stages(uuid_value, entry)
        return _EngineShaderArtifact(
            uuid=uuid_value,
            name=str(entry.get("name", uuid_value)),
            language=program_language,
            vertex_source=vertex_source,
            fragment_source=fragment_source,
        )

    stages = entry.get("stages")
    if not isinstance(stages, dict):
        raise ValueError(f"Built-in shader '{uuid_value}' has no stage map")

    vertex_source = _builtin_engine_stage_source(uuid_value, stages, "vertex")
    fragment_source = _builtin_engine_stage_source(uuid_value, stages, "fragment")
    return _EngineShaderArtifact(
        uuid=uuid_value,
        name=str(entry.get("name", uuid_value)),
        language=language,
        vertex_source=vertex_source,
        fragment_source=fragment_source,
        vertex_entry=_builtin_engine_stage_entry(stages, "vertex"),
        fragment_entry=_builtin_engine_stage_entry(stages, "fragment"),
    )


def _builtin_engine_stage_source(
    uuid_value: str,
    stages: dict[str, Any],
    stage_name: str,
) -> str:
    stage = stages.get(stage_name)
    if stage is None:
        return ""
    if isinstance(stage, str):
        source_name = stage
    elif isinstance(stage, dict):
        source_name_raw = stage.get("path")
        if not isinstance(source_name_raw, str):
            raise ValueError(f"Built-in shader '{uuid_value}' stage '{stage_name}' has no source path")
        source_name = source_name_raw
    else:
        raise ValueError(f"Built-in shader '{uuid_value}' stage '{stage_name}' has invalid catalog data")
    return _builtin_shader_source(source_name)


def _builtin_engine_stage_entry(stages: dict[str, Any], stage_name: str) -> str:
    stage = stages.get(stage_name)
    if isinstance(stage, dict):
        entry = stage.get("entry")
        if isinstance(entry, str) and entry != "":
            return entry
    return "main"


def _builtin_engine_shader_program_stages(
    uuid_value: str,
    entry: dict[str, Any],
) -> tuple[str, str, str]:
    from termin.materials import parse_shader_text

    program_entry = entry.get("program")
    if not isinstance(program_entry, dict):
        raise ValueError(f"Built-in shader '{uuid_value}' has no program source")
    path = program_entry.get("path")
    if not isinstance(path, str):
        raise ValueError(f"Built-in shader '{uuid_value}' program has no source path")

    program = parse_shader_text(_builtin_shader_source(path))
    if len(program.phases) == 0:
        raise RuntimeError(f"Built-in shader '{uuid_value}' parser returned no phases")
    phase = program.phases[0]
    vertex_stage = phase.stages.get("vertex")
    fragment_stage = phase.stages.get("fragment")
    if vertex_stage is None or fragment_stage is None:
        raise RuntimeError(f"Built-in shader '{uuid_value}' parser returned incomplete stages")
    return program.language, vertex_stage.source, fragment_stage.source


def _write_engine_shader_artifact(
    package_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader: _EngineShaderArtifact,
    compiler: Path,
    requested_targets: tuple[str, ...] | None = None,
) -> None:
    del diagnostics
    targets = _shader_targets_for_language(
        shader.language,
        requested_targets,
        f"Engine shader '{shader.uuid}'",
    )

    vulkan_dir = package_dir / "shaders" / "vulkan"
    vulkan_dir.mkdir(parents=True, exist_ok=True)
    for target in targets:
        (package_dir / "shaders" / target).mkdir(parents=True, exist_ok=True)

    source_ext = _source_extension_for_language(shader.language)
    shared_stage_source = (
        shader.language == "slang"
        and shader.vertex_source != ""
        and shader.fragment_source != ""
        and shader.vertex_source == shader.fragment_source
    )
    vertex_source_path: Path | None = None
    if shader.vertex_source != "":
        vertex_source_path = (
            vulkan_dir / f"{shader.uuid}.{source_ext}"
            if shared_stage_source
            else vulkan_dir / f"{shader.uuid}.vert.{source_ext}"
        )
        vertex_source_path.write_text(shader.vertex_source, encoding="utf-8")
        for target in targets:
            _compile_shader_stage(
                compiler,
                shader.language,
                target,
                "vertex",
                vertex_source_path,
                package_dir / "shaders" / target / _artifact_filename(shader.uuid, target, "vertex", "vert"),
                f"{shader.name}:vertex",
                shader.vertex_entry,
            )

    if shader.fragment_source == "":
        return

    fragment_source_path = (
        vulkan_dir / f"{shader.uuid}.{source_ext}"
        if shared_stage_source
        else vulkan_dir / f"{shader.uuid}.frag.{source_ext}"
    )
    if vertex_source_path is None or fragment_source_path != vertex_source_path:
        fragment_source_path.write_text(shader.fragment_source, encoding="utf-8")
    for target in targets:
        _compile_shader_stage(
            compiler,
            shader.language,
            target,
            "fragment",
            fragment_source_path,
            package_dir / "shaders" / target / _artifact_filename(shader.uuid, target, "fragment", "frag"),
            f"{shader.name}:fragment",
            shader.fragment_entry,
        )


def _write_tcgui_ui_shader_artifacts(package_dir: Path, compiler: Path) -> None:
    from tcgui.widgets.renderer import UI_FRAGMENT_SHADER, UI_VERTEX_SHADER

    vulkan_dir = package_dir / "shaders" / "vulkan"
    opengl_dir = package_dir / "shaders" / "opengl"
    vulkan_dir.mkdir(parents=True, exist_ok=True)
    opengl_dir.mkdir(parents=True, exist_ok=True)

    vulkan_vertex = vulkan_dir / f"{TCGUI_UI_SHADER_UUID}.vert.glsl"
    vulkan_fragment = vulkan_dir / f"{TCGUI_UI_SHADER_UUID}.frag.glsl"
    vulkan_vertex.write_text(UI_VERTEX_SHADER, encoding="utf-8")
    vulkan_fragment.write_text(UI_FRAGMENT_SHADER, encoding="utf-8")
    _compile_shader_stage(
        compiler,
        "glsl",
        "vulkan",
        "vertex",
        vulkan_vertex,
        vulkan_dir / f"{TCGUI_UI_SHADER_UUID}.vert.spv",
        f"{TCGUI_UI_SHADER_NAME}:vertex",
        "main",
    )
    _compile_shader_stage(
        compiler,
        "glsl",
        "vulkan",
        "fragment",
        vulkan_fragment,
        vulkan_dir / f"{TCGUI_UI_SHADER_UUID}.frag.spv",
        f"{TCGUI_UI_SHADER_NAME}:fragment",
        "main",
    )

    (opengl_dir / f"{TCGUI_UI_SHADER_UUID}.vert.glsl").write_text(UI_VERTEX_SHADER, encoding="utf-8")
    (opengl_dir / f"{TCGUI_UI_SHADER_UUID}.frag.glsl").write_text(UI_FRAGMENT_SHADER, encoding="utf-8")


def _source_extension_for_language(language: str) -> str:
    if language == "slang":
        return "slang"
    if language == "glsl":
        return "glsl"
    if language == "hlsl":
        return "hlsl"
    raise ValueError(f"Unsupported shader language: {language}")


def _copy_default_spirv(target_path: Path, source_name: str) -> None:
    source_path = (
        Path(__file__).resolve().parents[3]
        / "termin-android"
        / "assets"
        / "shaders"
        / "vulkan"
        / source_name
    )
    if not source_path.exists():
        raise FileNotFoundError(f"Default SPIR-V artifact is missing: {source_path}")
    shutil.copy2(source_path, target_path)


def _write_materials(
    package_dir: Path,
    materials: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, _ShaderSpec],
    default_shader_language: str,
    resource_policy: str,
) -> None:
    material_dir = package_dir / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(materials.items()):
        path = material_dir / f"{uuid_value}.tmat.json"
        material_spec = _export_material_spec(
            uuid_value,
            name,
            diagnostics,
            shaders,
            default_shader_language,
            resource_policy,
        )
        if material_spec is None:
            continue
        _write_json(path, material_spec)
        resources.append(
            {
                "type": "material",
                "uuid": uuid_value,
                "path": f"materials/{uuid_value}.tmat.json",
            }
        )


def _export_material_spec(
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, _ShaderSpec],
    default_shader_language: str,
    resource_policy: str,
) -> dict[str, Any] | None:
    try:
        from termin.materials import TcMaterial

        material = TcMaterial.from_uuid(uuid_value)
        if material.is_valid:
            return _material_to_spec(material, shaders)
    except Exception as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"materials/{uuid_value}.tmat.json",
                message=f"Runtime exporter failed to read material registry entry: {exc}",
            )
        )

    if _resource_policy_allows_fallback(resource_policy):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"materials/{uuid_value}.tmat.json",
                message="Runtime exporter used fallback material because registry entry is unavailable",
            )
        )
        shaders[DEFAULT_SHADER_UUID] = _default_shader_spec(default_shader_language)
        return _fallback_material_spec(uuid_value, name)

    diagnostics.append(
        RuntimePackageExportDiagnostic(
            level="error",
            path=f"materials/{uuid_value}.tmat.json",
            message=(
                "Runtime exporter could not export material because no runtime "
                "registry entry was found; fallback material requires "
                "resource_policy=dev_smoke"
            ),
        )
    )
    return None


def _material_to_spec(material: Any, shaders: dict[str, _ShaderSpec]) -> dict[str, Any]:
    import tgfx  # noqa: F401  # Registers TcShader before TcMaterialPhase.shader casts it.

    phases: list[dict[str, Any]] = []
    for phase in material.phases:
        shader = phase.shader
        if not shader.is_valid:
            raise ValueError(f"Material '{material.uuid}' has a phase with invalid shader")
        shaders[shader.uuid] = _shader_to_spec(shader)
        phases.append(
            {
                "mark": phase.phase_mark or "opaque",
                "shader": shader.uuid,
                "priority": int(phase.priority),
            }
        )

    if not phases:
        raise ValueError(f"Material '{material.uuid}' has no phases")

    spec = {
        "uuid": material.uuid,
        "name": material.name or material.uuid,
        "phases": phases,
    }
    uniforms = _material_uniforms_to_json(material)
    if uniforms:
        spec["uniforms"] = uniforms
    textures = _material_textures_to_json(material)
    if textures:
        spec["textures"] = textures
    return spec


def _material_uniforms_to_json(material: Any) -> dict[str, Any]:
    from termin.geombase import Vec3, Vec4

    result: dict[str, Any] = {}
    for name, value in material.uniforms.items():
        if isinstance(value, Vec3):
            result[name] = [float(value.x), float(value.y), float(value.z)]
        elif isinstance(value, Vec4):
            result[name] = [float(value.x), float(value.y), float(value.z), float(value.w)]
        elif isinstance(value, bool):
            result[name] = value
        elif isinstance(value, (int, float)):
            result[name] = value
        elif isinstance(value, tuple):
            result[name] = list(value)
        elif isinstance(value, list):
            result[name] = value
    return result


def _material_textures_to_json(material: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, texture in material.textures.items():
        if texture is None or not texture.is_valid:
            continue
        if texture.name == "__normal_1x1__":
            result[name] = {"kind": "builtin", "name": "normal"}
            continue
        if texture.name == "__white_1x1__":
            result[name] = {"kind": "builtin", "name": "white"}
            continue
        texture_uuid = texture.uuid
        if texture_uuid:
            result[name] = {
                "kind": "asset",
                "uuid": texture_uuid,
                "name": texture.name,
            }
    return result


def _fallback_material_spec(uuid_value: str, name: str) -> dict[str, Any]:
    return {
        "uuid": uuid_value,
        "name": name,
        "phases": [
            {
                "mark": "opaque",
                "shader": DEFAULT_SHADER_UUID,
                "priority": 0,
            }
        ],
    }


def _shader_to_spec(shader: Any) -> _ShaderSpec:
    if shader.fragment_source == "":
        raise ValueError(f"Shader '{shader.uuid}' has no fragment source")
    return _ShaderSpec(
        uuid=shader.uuid,
        name=shader.name or shader.uuid,
        source_path=shader.source_path or "runtime-registry",
        vertex_source=shader.vertex_source,
        fragment_source=shader.fragment_source,
        geometry_source=shader.geometry_source,
        language=_shader_language(shader),
        vertex_entry=shader.vertex_entry,
        fragment_entry=shader.fragment_entry,
        geometry_entry=shader.geometry_entry,
        features=int(shader.features),
    )


def _shader_language(shader: Any) -> str:
    try:
        language = shader.language
    except AttributeError:
        return "glsl"

    if isinstance(language, str):
        text = language
    else:
        try:
            text = language.name
        except AttributeError:
            text = str(language)
    text = text.lower()
    if text.endswith(".glsl") or text == "glsl":
        return "glsl"
    if text.endswith(".slang") or text == "slang":
        return "slang"
    if text.endswith(".hlsl") or text == "hlsl":
        return "hlsl"
    return text


def _resolve_shader_compiler(shader_compiler: Path | None) -> Path | None:
    if shader_compiler is not None:
        compiler = shader_compiler.resolve()
        resolved = existing_executable(compiler)
        if resolved is None:
            raise FileNotFoundError(f"Shader compiler does not exist: {compiler}")
        return resolved

    found = resolve_path_tool("termin_shaderc")
    if found is not None:
        return found.resolve()

    sdk_compiler = resolve_sdk_tool("termin_shaderc", Path(__file__))
    if sdk_compiler is not None:
        return sdk_compiler.resolve()

    return None


def _compile_shader_stage(
    compiler: Path,
    language: str,
    target: str,
    stage: str,
    input_path: Path,
    output_path: Path,
    debug_name: str,
    entry: str = "main",
) -> None:
    cmd = _executable_command(compiler) + [
        str(compiler),
        "compile",
        "--language",
        language,
        "--target",
        target,
        "--stage",
        stage,
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--entry",
        entry,
        "--debug-name",
        debug_name,
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Shader compilation failed for {input_path.name}: {message}")
    if not output_path.exists():
        raise RuntimeError(f"Shader compiler did not produce expected output: {output_path}")


def _executable_command(path: Path) -> list[str]:
    if os.name == "nt" and path.suffix.lower() == ".py":
        return [sys.executable]
    return []
