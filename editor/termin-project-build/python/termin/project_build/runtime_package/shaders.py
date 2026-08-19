"""Runtime shader specs and artifact generation."""

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

from termin.project_build.runtime_package.builtin_shader_catalog import (
    builtin_shader_catalog_entry,
    builtin_shader_source,
)
from termin.project_build.runtime_package.models import (
    RuntimePackageExportDiagnostic,
    ShaderSpec,
)
from termin.project_build.runtime_package.package_files import write_json
from termin.shader_tools import existing_executable, resolve_path_tool, resolve_sdk_tool


DEFAULT_SHADER_UUID = "termin-runtime-default-color"
DEFAULT_SHADER_NAME = "TerminRuntimeDefaultColor"
DEFAULT_SHADER_SOURCE_PATH = "termin-runtime/default-color"
DEFAULT_SHADER_LANGUAGE = "slang"

DEFAULT_SHADER_TARGETS_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    "glsl": ("vulkan",),
    "slang": ("vulkan", "opengl", "d3d11"),
}

SUPPORTED_SHADER_TARGETS_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    "glsl": ("vulkan",),
    "slang": ("vulkan", "opengl", "opengl330", "webgl2", "d3d11", "webgpu"),
    "hlsl": ("d3d11",),
}


ENGINE_SKYBOX_SHADER_UUID = "termin-engine-skybox"
ENGINE_FSQ_SHADER_UUID = "termin-engine-fsq"
ENGINE_SHADOW_SHADER_UUID = "termin-engine-shadow"
ENGINE_GRAYSCALE_SHADER_UUID = "termin-engine-grayscale"
ENGINE_BLOOM_BRIGHT_SHADER_UUID = "termin-engine-bloom-bright"
ENGINE_BLOOM_DOWNSAMPLE_SHADER_UUID = "termin-engine-bloom-downsample"
ENGINE_BLOOM_BLUR_VERTICAL_SHADER_UUID = "termin-engine-bloom-blur-vertical"
ENGINE_BLOOM_UPSAMPLE_SHADER_UUID = "termin-engine-bloom-upsample"
ENGINE_BLOOM_COMPOSITE_SHADER_UUID = "termin-engine-bloom-composite"
ENGINE_TONEMAP_SHADER_UUID = "termin-engine-tonemap"
ENGINE_OUTPUT_TRANSFORM_SHADER_UUID = "termin-engine-output-transform"
ENGINE_MULTIVIEW_TONEMAP_SHADER_UUID = "termin-engine-multiview-tonemap"
ENGINE_MULTIVIEW_OUTPUT_TRANSFORM_SHADER_UUID = (
    "termin-engine-multiview-output-transform"
)
ENGINE_CANVAS2D_SOLID_SHADER_UUID = "termin-engine-canvas2d-solid"
ENGINE_CANVAS2D_TEXTURE_SHADER_UUID = "termin-engine-canvas2d-texture"
ENGINE_TEXT2D_SHADER_UUID = "termin-engine-text2d"
ENGINE_TEXT2D_SDF_SHADER_UUID = "termin-engine-text2d-sdf"
ENGINE_TEXT3D_SHADER_UUID = "termin-engine-text3d"
ENGINE_WORLD2D_SHADER_UUID = "termin-engine-world2d"
ENGINE_SHADOW_MATERIAL_SHADER_UUID = "termin-engine-shadow-material"

# LineRenderer builds its final material variants from one canonical material
# shader. Its catalog entry owns the runtime source closure for the tube
# transform and pass-owned output adapters.
ENGINE_LINE_SHADER_UUIDS = (
    "termin-engine-line-default",
)


def normalize_shader_targets(shader_targets: Iterable[str] | None) -> tuple[str, ...] | None:
    if shader_targets is None:
        return None
    normalized: list[str] = []
    for target in shader_targets:
        text = str(target).strip().lower()
        if text == "":
            raise ValueError("Runtime package shader target must be a non-empty string")
        if text not in {"vulkan", "opengl", "opengl330", "webgl2", "d3d11", "webgpu"}:
            raise ValueError(f"Unsupported runtime package shader target: {target}")
        if text not in normalized:
            normalized.append(text)
    if not normalized:
        raise ValueError("Runtime package must request at least one shader target")
    return tuple(normalized)


def shader_targets_for_language(
    language: str,
    requested_targets: tuple[str, ...] | None,
    context: str,
) -> tuple[str, ...]:
    if requested_targets is None:
        targets = DEFAULT_SHADER_TARGETS_BY_LANGUAGE.get(language)
        if targets is None:
            raise ValueError(f"{context} has unsupported language: {language}")
        return targets

    supported = SUPPORTED_SHADER_TARGETS_BY_LANGUAGE.get(language)
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


def artifact_extension_for_target(target: str) -> str:
    if target == "vulkan":
        return "spv"
    if target in {"opengl", "opengl330", "webgl2"}:
        return "glsl"
    if target == "d3d11":
        return "cso"
    if target == "webgpu":
        return "wgsl"
    raise ValueError(f"Unsupported shader target: {target}")


def artifact_stage_suffix(target: str, stage_name: str, fallback_stage_ext: str) -> str:
    if target != "d3d11":
        return fallback_stage_ext
    if stage_name == "vertex":
        return "vs"
    if stage_name == "fragment":
        return "ps"
    if stage_name == "geometry":
        return "gs"
    raise ValueError(f"Unsupported D3D11 shader stage: {stage_name}")


def artifact_filename(shader_uuid: str, target: str, stage_name: str, fallback_stage_ext: str) -> str:
    suffix = artifact_stage_suffix(target, stage_name, fallback_stage_ext)
    extension = artifact_extension_for_target(target)
    return f"{shader_uuid}.{suffix}.{extension}"


def artifact_path_text(shader_uuid: str, target: str, stage_name: str, fallback_stage_ext: str) -> str:
    return f"shaders/{target}/{artifact_filename(shader_uuid, target, stage_name, fallback_stage_ext)}"


def default_shader_spec(language: str) -> ShaderSpec:
    normalized = normalize_default_shader_language(language)
    if normalized == "glsl":
        raise ValueError("The runtime default shader is Slang-only")
    if normalized == "slang":
        entry = builtin_shader_catalog_entry(DEFAULT_SHADER_UUID)
        stages = entry.get("stages")
        if not isinstance(stages, dict):
            raise ValueError(f"Built-in shader '{DEFAULT_SHADER_UUID}' has no stage map")
        return ShaderSpec(
            uuid=DEFAULT_SHADER_UUID,
            name=str(entry.get("name", DEFAULT_SHADER_NAME)),
            source_path=DEFAULT_SHADER_SOURCE_PATH,
            vertex_source=builtin_engine_stage_source(DEFAULT_SHADER_UUID, stages, "vertex"),
            fragment_source=builtin_engine_stage_source(DEFAULT_SHADER_UUID, stages, "fragment"),
            geometry_source="",
            language="slang",
            vertex_entry=builtin_engine_stage_entry(stages, "vertex"),
            fragment_entry=builtin_engine_stage_entry(stages, "fragment"),
            allow_precompiled_default=False,
        )
    raise ValueError(f"Unsupported default shader language: {language}")


def normalize_default_shader_language(language: str) -> str:
    text = language.strip().lower()
    if text.endswith(".glsl") or text == "glsl":
        return "glsl"
    if text.endswith(".slang") or text == "slang":
        return "slang"
    raise ValueError(f"Unsupported default shader language: {language}")


def write_shaders(
    package_dir: Path,
    shaders: dict[str, ShaderSpec],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader_compiler: str | Path | None,
    requested_targets: tuple[str, ...] | None,
    fxc: Path | None = None,
) -> None:
    compiler = resolve_shader_compiler(Path(shader_compiler) if shader_compiler is not None else None)
    for shader in sorted(shaders.values(), key=lambda item: item.uuid):
        write_shader(
            package_dir,
            resources,
            diagnostics,
            shader,
            compiler,
            requested_targets,
            fxc,
        )


def shader_program_to_spec(program: Any) -> dict[str, Any]:
    from termin.geombase import LinearColor, SrgbColor

    if program is None or not program.is_valid:
        raise ValueError("Cannot export an invalid TcShaderProgram")

    properties: list[dict[str, Any]] = []
    for prop in program.properties:
        property_type = str(prop["property_type"])
        if property_type == "Color":
            raise ValueError(
                f"Shader program '{program.uuid}' property '{prop['name']}' uses legacy "
                "property_type 'Color'; use 'SrgbColor' or 'LinearColor'"
            )
        item: dict[str, Any] = {
            "name": str(prop["name"]),
            "property_type": property_type,
            "label": str(prop.get("label", "")),
        }
        if prop.get("expected_encoding") is not None:
            item["expected_encoding"] = str(prop["expected_encoding"])
        default = prop.get("default")
        if default is not None:
            if isinstance(default, (SrgbColor, LinearColor)):
                item["default"] = [float(default.r), float(default.g), float(default.b), float(default.a)]
            else:
                item["default"] = list(default) if isinstance(default, tuple) else default
        if prop.get("range_min") is not None:
            item["range_min"] = float(prop["range_min"])
        if prop.get("range_max") is not None:
            item["range_max"] = float(prop["range_max"])
        properties.append(item)

    phases: list[dict[str, Any]] = []
    for phase in program.phases:
        shader = phase["shader"]
        if shader is None or not shader.is_valid:
            raise ValueError(
                f"Shader program '{program.uuid}' has stale phase '{phase['phase_mark']}'"
            )
        state = phase["state"]
        phases.append(
            {
                "phase_mark": str(phase["phase_mark"]),
                "priority": int(phase["priority"]),
                "shader": shader.uuid,
                "state": {
                    "polygon_mode": int(state["polygon_mode"]),
                    "cull": bool(state["cull"]),
                    "depth_test": bool(state["depth_test"]),
                    "depth_write": bool(state["depth_write"]),
                    "blend": bool(state["blend"]),
                    "blend_src": int(state["blend_src"]),
                    "blend_dst": int(state["blend_dst"]),
                    "depth_func": int(state["depth_func"]),
                },
            }
        )

    if not phases:
        raise ValueError(f"Shader program '{program.uuid}' has no phases")
    return {
        "schema_version": 1,
        "uuid": program.uuid,
        "name": program.name or program.uuid,
        "source_path": program.source_path or "runtime-registry",
        "language": program.language,
        "features": int(program.features),
        "properties": properties,
        "phases": phases,
    }


def write_shader_programs(
    package_dir: Path,
    shader_programs: dict[str, dict[str, Any]],
    resources: list[dict[str, str]],
) -> None:
    shader_dir = package_dir / "shaders"
    shader_dir.mkdir(parents=True, exist_ok=True)
    for program_uuid, spec in sorted(shader_programs.items()):
        path = shader_dir / f"{program_uuid}.shader-program.json"
        write_json(path, spec)
        resources.append(
            {
                "type": "shader_program",
                "uuid": program_uuid,
                "path": f"shaders/{program_uuid}.shader-program.json",
            }
        )


def write_shader(
    package_dir: Path,
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader: ShaderSpec,
    compiler: Path | None,
    requested_targets: tuple[str, ...] | None,
    fxc: Path | None = None,
) -> dict[str, Any]:
    compile_artifacts = shader.artifact_role != "surface_producer"
    targets = (
        shader_targets_for_language(
            shader.language,
            requested_targets,
            f"Shader '{shader.uuid}'",
        )
        if compile_artifacts
        else ()
    )

    shader_dir = package_dir / "shaders"
    vulkan_dir = shader_dir / "vulkan"
    shader_dir.mkdir(parents=True, exist_ok=True)
    vulkan_dir.mkdir(parents=True, exist_ok=True)
    for target in targets:
        (shader_dir / target).mkdir(parents=True, exist_ok=True)

    source_ext = source_extension_for_language(shader.language)
    shared_stage_source = (
        shader.language == "slang"
        and shader.vertex_source != ""
        and shader.geometry_source == ""
        and shader.vertex_source == shader.fragment_source
    )
    vertex_source_path: Path | None = None
    if shared_stage_source:
        vertex_source_path = vulkan_dir / f"{shader.uuid}.{source_ext}"
        fragment_source_path = vertex_source_path
    else:
        if shader.vertex_source != "":
            vertex_source_path = vulkan_dir / f"{shader.uuid}.vert.{source_ext}"
        fragment_source_path = vulkan_dir / f"{shader.uuid}.frag.{source_ext}"
    if vertex_source_path is not None:
        vertex_source_path.write_text(shader.vertex_source, encoding="utf-8")
    if vertex_source_path is None or fragment_source_path != vertex_source_path:
        fragment_source_path.write_text(shader.fragment_source, encoding="utf-8")
    fragment_compile_source_path = fragment_source_path
    if compile_artifacts and shader.surface_interface_source:
        fragment_compile_source_path = (
            vulkan_dir / f"{shader.uuid}.frag.compile.{source_ext}"
        )
        fragment_compile_source_path.write_text(
            f"{shader.surface_interface_source}\n{shader.fragment_source}",
            encoding="utf-8",
        )

    geometry_source_path = None
    if shader.geometry_source != "":
        geometry_source_path = vulkan_dir / f"{shader.uuid}.geom.{source_ext}"
        geometry_source_path.write_text(shader.geometry_source, encoding="utf-8")

    if (
        compile_artifacts
        and compiler is None
        and shader.allow_precompiled_default
        and targets == ("vulkan",)
    ):
        copy_default_spirv(vulkan_dir / f"{shader.uuid}.vert.spv", "termin-android-scene-color.vert.spv")
        copy_default_spirv(vulkan_dir / f"{shader.uuid}.frag.spv", "termin-android-scene-color.frag.spv")
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"shaders/{shader.uuid}.shader.json",
                message="Runtime exporter reused built-in default SPIR-V artifacts",
            )
        )
    elif compile_artifacts:
        if compiler is None:
            raise FileNotFoundError(
                "Shader compiler 'termin_shaderc' was not found. "
                "Pass shader_compiler=..., add it to PATH, or set TERMIN_SDK."
            )
        for target in targets:
            target_dir = shader_dir / target
            program_source_paths = tuple(
                dict.fromkeys(
                    path
                    for path in (
                        vertex_source_path,
                        fragment_compile_source_path,
                        geometry_source_path,
                    )
                    if path is not None
                )
            )
            if vertex_source_path is not None:
                compile_shader_stage(
                    compiler,
                    shader.language,
                    target,
                    "vertex",
                    vertex_source_path,
                    target_dir / artifact_filename(shader.uuid, target, "vertex", "vert"),
                    f"{shader.name or shader.uuid}:vertex",
                    shader.vertex_entry,
                    program_source_paths,
                    fxc,
                )
            compile_shader_stage(
                compiler,
                shader.language,
                target,
                "fragment",
                fragment_compile_source_path,
                target_dir / artifact_filename(shader.uuid, target, "fragment", "frag"),
                f"{shader.name or shader.uuid}:fragment",
                shader.fragment_entry,
                program_source_paths,
                fxc,
            )
            if geometry_source_path is not None:
                compile_shader_stage(
                    compiler,
                    shader.language,
                    target,
                    "geometry",
                    geometry_source_path,
                    target_dir / artifact_filename(shader.uuid, target, "geometry", "geom"),
                    f"{shader.name or shader.uuid}:geometry",
                    shader.geometry_entry,
                    program_source_paths,
                    fxc,
                )

    shader_spec: dict[str, Any] = {
        "uuid": shader.uuid,
        "name": shader.name or shader.uuid,
        "language": shader.language,
        "fragment_source_path": (
            f"shaders/vulkan/{shader.uuid}.{source_ext}"
            if shared_stage_source
            else f"shaders/vulkan/{shader.uuid}.frag.{source_ext}"
        ),
        "fragment_entry": shader.fragment_entry,
        "source_path": shader.source_path,
        "features": int(shader.features),
        "artifact_role": shader.artifact_role,
        "source_identity": shader.source_identity,
    }
    if vertex_source_path is not None:
        shader_spec["vertex_source_path"] = (
            f"shaders/vulkan/{shader.uuid}.{source_ext}"
            if shared_stage_source
            else f"shaders/vulkan/{shader.uuid}.vert.{source_ext}"
        )
        shader_spec["vertex_entry"] = shader.vertex_entry
    if compile_artifacts:
        shader_spec["artifacts"] = {
            target: {
                **(
                    {
                        "vertex": artifact_path_text(
                            shader.uuid, target, "vertex", "vert"
                        )
                    }
                    if vertex_source_path is not None
                    else {}
                ),
                "fragment": artifact_path_text(
                    shader.uuid, target, "fragment", "frag"
                ),
            }
            for target in targets
        }
    if shader.surface_producer is not None:
        shader_spec["surface_producer"] = shader.surface_producer
        shader_spec["surface_contract"] = {
            "id": shader.surface_producer["contract_id"],
            "version": shader.surface_producer["contract_version"],
            "interface_source_identity": shader.surface_interface_identity,
        }
    if geometry_source_path is not None:
        shader_spec["geometry_source_path"] = f"shaders/vulkan/{shader.uuid}.geom.{source_ext}"
        shader_spec["geometry_entry"] = shader.geometry_entry
        for target in targets:
            shader_spec["artifacts"][target]["geometry"] = artifact_path_text(
                shader.uuid,
                target,
                "geometry",
                "geom",
            )

    shader_spec_path = shader_dir / f"{shader.uuid}.shader.json"
    write_json(shader_spec_path, shader_spec)
    if shader.register_in_runtime:
        resources.append(
            {
                "type": "shader",
                "uuid": shader.uuid,
                "path": f"shaders/{shader.uuid}.shader.json",
            }
        )
    return shader_spec


@dataclass(frozen=True)
class EngineShaderArtifact:
    uuid: str
    name: str
    language: str
    vertex_source: str = ""
    fragment_source: str = ""
    vertex_entry: str = "main"
    fragment_entry: str = "main"


def write_default_pipeline_shader_artifacts(
    package_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader_compiler: str | Path | None,
    requested_targets: tuple[str, ...] | None = None,
    fxc: Path | None = None,
) -> dict[str, Any]:
    compiler = resolve_shader_compiler(Path(shader_compiler) if shader_compiler is not None else None)
    if compiler is None:
        raise FileNotFoundError(
            "Shader compiler 'termin_shaderc' was not found. "
            "Default pipeline shaders require precompiled SPIR-V for Android."
        )

    shaders = default_pipeline_engine_shaders()
    for shader in shaders:
        write_engine_shader_artifact(
            package_dir,
            diagnostics,
            shader,
            compiler,
            requested_targets,
            fxc,
        )
    return write_builtin_shader_contract(package_dir, shaders, requested_targets)


def write_builtin_shader_contract(
    package_dir: Path,
    shaders: list[EngineShaderArtifact],
    requested_targets: tuple[str, ...] | None,
) -> dict[str, Any]:
    builtin_root = package_dir / "builtin_shaders"
    catalog_entries: list[dict[str, Any]] = []
    contract_shaders: list[dict[str, Any]] = []

    for shader in shaders:
        catalog_entry = builtin_shader_catalog_entry(shader.uuid)
        catalog_entries.append(catalog_entry)
        _write_runtime_required_builtin_sources(builtin_root, shader.uuid, catalog_entry)

        stages: list[tuple[str, str]] = []
        if shader.vertex_source != "":
            stages.append(("vertex", "vert"))
        if shader.fragment_source != "":
            stages.append(("fragment", "frag"))
        targets = shader_targets_for_language(
            shader.language,
            requested_targets,
            f"Engine shader '{shader.uuid}'",
        )
        contract_shaders.append(
            {
                "uuid": shader.uuid,
                "artifacts": {
                    target: {
                        stage_name: artifact_path_text(
                            shader.uuid,
                            target,
                            stage_name,
                            stage_suffix,
                        )
                        for stage_name, stage_suffix in stages
                    }
                    for target in targets
                },
            }
        )

    write_json(
        builtin_root / "engine-shader-catalog.json",
        {"version": 1, "shaders": catalog_entries},
    )
    return {
        "version": 1,
        "catalog": "builtin_shaders/engine-shader-catalog.json",
        "shaders": contract_shaders,
    }


def _write_runtime_required_builtin_sources(
    builtin_root: Path,
    shader_uuid: str,
    catalog_entry: dict[str, Any],
) -> None:
    runtime_sources = catalog_entry.get("runtime_sources", [])
    if not isinstance(runtime_sources, list) or not all(
        isinstance(source_path, str) and source_path != ""
        for source_path in runtime_sources
    ):
        raise ValueError(
            f"Built-in shader '{shader_uuid}' has invalid runtime source paths"
        )
    source_paths = set(runtime_sources)

    language = catalog_entry.get("language")
    if language == "shader":
        program = catalog_entry.get("program")
        if not isinstance(program, dict) or not isinstance(program.get("path"), str):
            raise ValueError(f"Built-in shader program '{shader_uuid}' has no source path")
        source_paths.add(program["path"])
    elif language == "glsl":
        stages = catalog_entry.get("stages")
        if not isinstance(stages, dict):
            raise ValueError(f"Built-in GLSL shader '{shader_uuid}' has no stage map")
        for stage in stages.values():
            source_path = stage if isinstance(stage, str) else stage.get("path")
            if not isinstance(source_path, str):
                raise ValueError(f"Built-in GLSL shader '{shader_uuid}' has invalid stage source")
            source_paths.add(source_path)

    for source_path in source_paths:
        target_path = builtin_root / source_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(builtin_shader_source(source_path), encoding="utf-8")


def default_pipeline_engine_shaders() -> list[EngineShaderArtifact]:
    shaders = [
        builtin_engine_shader_artifact(ENGINE_FSQ_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_SKYBOX_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_SHADOW_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_GRAYSCALE_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_BLOOM_BRIGHT_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_BLOOM_DOWNSAMPLE_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_BLOOM_BLUR_VERTICAL_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_BLOOM_UPSAMPLE_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_BLOOM_COMPOSITE_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_TONEMAP_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_OUTPUT_TRANSFORM_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_MULTIVIEW_TONEMAP_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_MULTIVIEW_OUTPUT_TRANSFORM_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_CANVAS2D_SOLID_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_CANVAS2D_TEXTURE_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_TEXT2D_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_TEXT2D_SDF_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_TEXT3D_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_WORLD2D_SHADER_UUID),
        builtin_engine_shader_artifact(ENGINE_SHADOW_MATERIAL_SHADER_UUID),
    ]
    shaders.extend(
        builtin_engine_shader_artifact(shader_uuid)
        for shader_uuid in ENGINE_LINE_SHADER_UUIDS
    )
    return shaders


def builtin_engine_shader_artifact(uuid_value: str) -> EngineShaderArtifact:
    entry = builtin_shader_catalog_entry(uuid_value)
    language_value = entry.get("language")
    if not isinstance(language_value, str) or not language_value.strip():
        raise ValueError(f"Built-in shader '{uuid_value}' has no explicit language")
    language = language_value.strip().lower()
    if language == "shader":
        program_language, vertex_source, fragment_source = builtin_engine_shader_program_stages(
            uuid_value,
            entry,
        )
        return EngineShaderArtifact(
            uuid=uuid_value,
            name=str(entry.get("name", uuid_value)),
            language=program_language,
            vertex_source=vertex_source,
            fragment_source=fragment_source,
        )

    stages = entry.get("stages")
    if not isinstance(stages, dict):
        raise ValueError(f"Built-in shader '{uuid_value}' has no stage map")

    vertex_source = builtin_engine_stage_source(uuid_value, stages, "vertex")
    fragment_source = builtin_engine_stage_source(uuid_value, stages, "fragment")
    return EngineShaderArtifact(
        uuid=uuid_value,
        name=str(entry.get("name", uuid_value)),
        language=language,
        vertex_source=vertex_source,
        fragment_source=fragment_source,
        vertex_entry=builtin_engine_stage_entry(stages, "vertex"),
        fragment_entry=builtin_engine_stage_entry(stages, "fragment"),
    )


def builtin_engine_stage_source(
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
    return builtin_shader_source(source_name)


def builtin_engine_stage_entry(stages: dict[str, Any], stage_name: str) -> str:
    stage = stages.get(stage_name)
    if isinstance(stage, dict):
        entry = stage.get("entry")
        if isinstance(entry, str) and entry != "":
            return entry
    return "main"


def builtin_engine_shader_program_stages(
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

    program = parse_shader_text(builtin_shader_source(path))
    if len(program.phases) == 0:
        raise RuntimeError(f"Built-in shader '{uuid_value}' parser returned no phases")
    phase = program.phases[0]
    vertex_stage = phase.stages.get("vertex")
    fragment_stage = phase.stages.get("fragment")
    if vertex_stage is None or fragment_stage is None:
        raise RuntimeError(f"Built-in shader '{uuid_value}' parser returned incomplete stages")
    return program.language, vertex_stage.source, fragment_stage.source


def write_engine_shader_artifact(
    package_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader: EngineShaderArtifact,
    compiler: Path,
    requested_targets: tuple[str, ...] | None = None,
    fxc: Path | None = None,
) -> None:
    del diagnostics
    targets = shader_targets_for_language(
        shader.language,
        requested_targets,
        f"Engine shader '{shader.uuid}'",
    )

    vulkan_dir = package_dir / "shaders" / "vulkan"
    vulkan_dir.mkdir(parents=True, exist_ok=True)
    for target in targets:
        (package_dir / "shaders" / target).mkdir(parents=True, exist_ok=True)

    source_ext = source_extension_for_language(shader.language)
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
            compile_shader_stage(
                compiler,
                shader.language,
                target,
                "vertex",
                vertex_source_path,
                package_dir / "shaders" / target / artifact_filename(shader.uuid, target, "vertex", "vert"),
                f"{shader.name}:vertex",
                shader.vertex_entry,
                fxc=fxc,
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
        compile_shader_stage(
            compiler,
            shader.language,
            target,
            "fragment",
            fragment_source_path,
            package_dir / "shaders" / target / artifact_filename(shader.uuid, target, "fragment", "frag"),
            f"{shader.name}:fragment",
            shader.fragment_entry,
            fxc=fxc,
        )


def source_extension_for_language(language: str) -> str:
    if language == "slang":
        return "slang"
    if language == "glsl":
        return "glsl"
    if language == "hlsl":
        return "hlsl"
    raise ValueError(f"Unsupported shader language: {language}")


def copy_default_spirv(target_path: Path, source_name: str) -> None:
    source_path = (
        Path(__file__).resolve().parents[4]
        / "termin-android"
        / "assets"
        / "shaders"
        / "vulkan"
        / source_name
    )
    if not source_path.exists():
        raise FileNotFoundError(f"Default SPIR-V artifact is missing: {source_path}")
    shutil.copy2(source_path, target_path)


def resolve_shader_compiler(shader_compiler: Path | None) -> Path | None:
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


def compile_shader_stage(
    compiler: Path,
    language: str,
    target: str,
    stage: str,
    input_path: Path,
    output_path: Path,
    debug_name: str,
    entry: str = "main",
    program_source_paths: tuple[Path, ...] = (),
    fxc: Path | None = None,
) -> None:
    cmd = executable_command(compiler) + [
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
    for program_source_path in program_source_paths:
        cmd.extend(["--program-source", str(program_source_path)])
    if target == "d3d11" and fxc is not None:
        cmd.extend(["--fxc", str(fxc)])
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Shader compilation failed for {input_path.name}: {message}")
    if not output_path.exists():
        raise RuntimeError(f"Shader compiler did not produce expected output: {output_path}")
    layout_path = Path(f"{output_path}.layout.json")
    if not layout_path.exists():
        raise RuntimeError(
            f"Shader compiler did not produce expected layout sidecar: {layout_path}"
        )
    if target == "webgpu":
        try:
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"WebGPU shader layout sidecar is invalid: {layout_path}: {exc}"
            ) from exc
        if (
            not isinstance(layout, dict)
            or layout.get("version") != 3
            or layout.get("target") != "webgpu"
            or layout.get("stage") != stage
            or not isinstance(layout.get("resources"), list)
        ):
            raise RuntimeError(
                f"WebGPU shader layout sidecar has an incompatible contract: {layout_path}"
            )


def executable_command(path: Path) -> list[str]:
    if os.name == "nt" and path.suffix.lower() == ".py":
        return [sys.executable]
    return []
