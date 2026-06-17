"""Runtime package exporter.

The exporter writes the package contract consumed by termin-runtime:

    manifest.json
    scene.json
    pipelines/*.pipeline.json
    meshes/*.tmesh.json
    materials/*.tmat.json
    shaders/*.shader.json
    shaders/vulkan/*.spv

When a referenced mesh/material exists in the current runtime registries, the
exporter writes real runtime artifacts. Missing registry entries are reported
and receive a fallback artifact so early Android builds remain installable.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from termin.shader_tools import existing_executable, resolve_path_tool, resolve_sdk_tool


DEFAULT_SHADER_UUID = "termin-runtime-default-color"
DEFAULT_SHADER_NAME = "TerminRuntimeDefaultColor"
DEFAULT_SHADER_SOURCE_PATH = "termin-runtime/default-color"
DEFAULT_SHADER_LANGUAGE = "slang"


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
ENGINE_SHADOW_MATERIAL_SHADER_UUID = "termin-engine-shadow-material"
TCGUI_UI_SHADER_UUID = "termin-tcgui-ui-engine"
TCGUI_UI_SHADER_NAME = "UIEngineVSFS"


PLACEHOLDER_MESH_VERTICES = [
    0.0, 0.65, 0.0, 1.0, 0.05, 0.05,
    -0.75, -0.55, 0.0, 0.05, 1.0, 0.05,
    0.75, -0.55, 0.0, 0.05, 0.20, 1.0,
]


@dataclass
class RuntimePackageExportDiagnostic:
    level: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class RuntimePackageExportResult:
    package_dir: Path
    manifest_path: Path
    scene_path: Path
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


def export_runtime_package(
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path,
    shader_compiler: str | Path | None = None,
    default_shader_language: str = DEFAULT_SHADER_LANGUAGE,
) -> RuntimePackageExportResult:
    project_root_path = Path(project_root).resolve()
    entry_scene_path = _resolve_entry_scene(project_root_path, Path(entry_scene))
    output_dir_path = Path(output_dir).resolve()

    scene_data = _read_scene_data(entry_scene_path)
    diagnostics: list[RuntimePackageExportDiagnostic] = []
    refs = _collect_runtime_refs(scene_data)
    _collect_project_material_refs(project_root_path, refs, diagnostics)

    _write_clean_package_dir(output_dir_path)
    scene_path = output_dir_path / "scene.json"
    _write_json(scene_path, scene_data)

    resources: list[dict[str, str]] = []
    shaders: dict[str, _ShaderSpec] = {}
    _write_meshes(project_root_path, output_dir_path, refs.meshes, resources, diagnostics)
    _write_materials(
        output_dir_path,
        refs.materials,
        resources,
        diagnostics,
        shaders,
        default_shader_language,
    )
    _write_pipelines(project_root_path, output_dir_path, refs.pipelines, resources, diagnostics)
    if not shaders:
        shaders[DEFAULT_SHADER_UUID] = _default_shader_spec(default_shader_language)
    _write_shaders(output_dir_path, shaders, resources, diagnostics, shader_compiler)
    _write_default_pipeline_shader_artifacts(output_dir_path, diagnostics, shader_compiler)
    resources.sort(key=_resource_sort_key)

    manifest = {
        "version": 1,
        "shader_artifact_root": ".",
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
        "resources": resources,
        "scene": "scene.json",
    }
    manifest_path = output_dir_path / "manifest.json"
    _write_json(manifest_path, manifest)

    return RuntimePackageExportResult(
        package_dir=output_dir_path,
        manifest_path=manifest_path,
        scene_path=scene_path,
        diagnostics=diagnostics,
    )


@dataclass
class _RuntimeRefs:
    meshes: dict[str, str] = field(default_factory=dict)
    materials: dict[str, str] = field(default_factory=dict)
    pipelines: dict[str, str] = field(default_factory=dict)


@dataclass
class _ShaderSpec:
    uuid: str
    name: str
    source_path: str
    vertex_source: str
    fragment_source: str
    geometry_source: str = ""
    language: str = "glsl"
    vertex_entry: str = "main"
    fragment_entry: str = "main"
    geometry_entry: str = "main"
    allow_precompiled_default: bool = False
    features: int = 0


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


def _stdlib_shader_text(*relative_path: str) -> str:
    path = (
        Path(__file__).resolve().parents[1]
        / "resources"
        / "stdlib"
        / Path(*relative_path)
    )
    return path.read_text(encoding="utf-8")


def _resolve_entry_scene(project_root: Path, entry_scene: Path) -> Path:
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


def _read_scene_data(scene_path: Path) -> dict[str, Any]:
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


def _collect_runtime_refs(scene_data: dict[str, Any]) -> _RuntimeRefs:
    refs = _RuntimeRefs()
    _collect_refs_recursive(scene_data, refs, "")
    return refs


def _collect_refs_recursive(value: Any, refs: _RuntimeRefs, field_name: str) -> None:
    if isinstance(value, dict):
        _collect_pipeline_refs(value, refs)
        _collect_typed_ref(value, refs, field_name)
        for key, child in value.items():
            _collect_refs_recursive(child, refs, key)
        return
    if isinstance(value, list):
        for child in value:
            _collect_refs_recursive(child, refs, field_name)


def _collect_typed_ref(value: dict[str, Any], refs: _RuntimeRefs, field_name: str) -> None:
    uuid_value = value.get("uuid")
    type_value = value.get("type")
    if not isinstance(uuid_value, str) or uuid_value == "":
        return
    if type_value != "uuid":
        return

    name_value = value.get("name")
    name = name_value if isinstance(name_value, str) and name_value != "" else uuid_value

    if _looks_like_mesh_ref(value, field_name):
        refs.meshes[uuid_value] = name
    if _looks_like_material_ref(value, field_name):
        refs.materials[uuid_value] = name


def _collect_pipeline_refs(value: dict[str, Any], refs: _RuntimeRefs) -> None:
    pipeline_uuid = value.get("pipeline_uuid")
    pipeline_name = value.get("pipeline_name")
    if isinstance(pipeline_uuid, str) and pipeline_uuid != "":
        name = pipeline_name if isinstance(pipeline_name, str) and pipeline_name != "" else pipeline_uuid
        refs.pipelines[pipeline_uuid] = name


def _collect_project_material_refs(
    project_root: Path,
    refs: _RuntimeRefs,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    for path in _iter_project_material_paths(project_root):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=str(path.relative_to(project_root)),
                    message=f"Runtime exporter failed to inspect material asset: {exc}",
                )
            )
            continue

        if not isinstance(data, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=str(path.relative_to(project_root)),
                    message="Runtime exporter skipped material asset because JSON root is not an object",
                )
            )
            continue

        uuid_value = data.get("uuid")
        if not isinstance(uuid_value, str) or uuid_value == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=str(path.relative_to(project_root)),
                    message="Runtime exporter skipped material asset because it has no uuid",
                )
            )
            continue

        refs.materials[uuid_value] = path.stem


def _iter_project_material_paths(project_root: Path):
    ignored_parts = {".git", "__pycache__", "build", "dist"}
    for path in project_root.rglob("*.material"):
        rel = path.relative_to(project_root)
        if any(part in ignored_parts for part in rel.parts):
            continue
        if path.is_file():
            yield path


def _looks_like_mesh_ref(value: dict[str, Any], field_name: str) -> bool:
    if field_name == "mesh":
        return True
    kind_value = value.get("kind")
    role_value = value.get("role")
    if kind_value == "tc_mesh" or role_value == "mesh":
        return True
    name_value = value.get("name")
    if isinstance(name_value, str):
        return "mesh" in name_value.lower()
    return False


def _looks_like_material_ref(value: dict[str, Any], field_name: str) -> bool:
    if field_name == "material":
        return True
    kind_value = value.get("kind")
    role_value = value.get("role")
    if kind_value == "tc_material" or role_value == "material":
        return True
    name_value = value.get("name")
    if isinstance(name_value, str):
        return "material" in name_value.lower()
    return False


def _write_clean_package_dir(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _write_shaders(
    package_dir: Path,
    shaders: dict[str, _ShaderSpec],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader_compiler: str | Path | None,
) -> None:
    compiler = _resolve_shader_compiler(Path(shader_compiler) if shader_compiler is not None else None)
    for shader in sorted(shaders.values(), key=lambda item: item.uuid):
        _write_shader(package_dir, resources, diagnostics, shader, compiler)


def _write_shader(
    package_dir: Path,
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader: _ShaderSpec,
    compiler: Path | None,
) -> None:
    if shader.language not in {"glsl", "slang"}:
        raise ValueError(f"Shader '{shader.uuid}' has unsupported language: {shader.language}")

    shader_dir = package_dir / "shaders"
    vulkan_dir = shader_dir / "vulkan"
    opengl_dir = shader_dir / "opengl"
    shader_dir.mkdir(parents=True, exist_ok=True)
    vulkan_dir.mkdir(parents=True, exist_ok=True)
    if shader.language == "slang":
        opengl_dir.mkdir(parents=True, exist_ok=True)

    source_ext = "slang" if shader.language == "slang" else "glsl"
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

    if compiler is None and shader.allow_precompiled_default:
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
        _compile_shader_stage(
            compiler,
            shader.language,
            "vulkan",
            "vertex",
            vertex_source_path,
            vulkan_dir / f"{shader.uuid}.vert.spv",
            f"{shader.name or shader.uuid}:vertex",
            shader.vertex_entry,
        )
        _compile_shader_stage(
            compiler,
            shader.language,
            "vulkan",
            "fragment",
            fragment_source_path,
            vulkan_dir / f"{shader.uuid}.frag.spv",
            f"{shader.name or shader.uuid}:fragment",
            shader.fragment_entry,
        )
        if geometry_source_path is not None:
            _compile_shader_stage(
                compiler,
                shader.language,
                "vulkan",
                "geometry",
                geometry_source_path,
                vulkan_dir / f"{shader.uuid}.geom.spv",
                f"{shader.name or shader.uuid}:geometry",
                shader.geometry_entry,
            )

        if shader.language == "slang":
            _compile_shader_stage(
                compiler,
                shader.language,
                "opengl",
                "vertex",
                vertex_source_path,
                opengl_dir / f"{shader.uuid}.vert.glsl",
                f"{shader.name or shader.uuid}:vertex",
                shader.vertex_entry,
            )
            _compile_shader_stage(
                compiler,
                shader.language,
                "opengl",
                "fragment",
                fragment_source_path,
                opengl_dir / f"{shader.uuid}.frag.glsl",
                f"{shader.name or shader.uuid}:fragment",
                shader.fragment_entry,
            )
            if geometry_source_path is not None:
                _compile_shader_stage(
                    compiler,
                    shader.language,
                    "opengl",
                    "geometry",
                    geometry_source_path,
                    opengl_dir / f"{shader.uuid}.geom.glsl",
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
            "vulkan": {
                "vertex": f"shaders/vulkan/{shader.uuid}.vert.spv",
                "fragment": f"shaders/vulkan/{shader.uuid}.frag.spv",
            }
        },
    }
    if geometry_source_path is not None:
        shader_spec["geometry_source_path"] = f"shaders/vulkan/{shader.uuid}.geom.{source_ext}"
        shader_spec["geometry_entry"] = shader.geometry_entry
        shader_spec["artifacts"]["vulkan"]["geometry"] = f"shaders/vulkan/{shader.uuid}.geom.spv"
    if shader.language == "slang":
        shader_spec["artifacts"]["opengl"] = {
            "vertex": f"shaders/opengl/{shader.uuid}.vert.glsl",
            "fragment": f"shaders/opengl/{shader.uuid}.frag.glsl",
        }
        if geometry_source_path is not None:
            shader_spec["artifacts"]["opengl"]["geometry"] = f"shaders/opengl/{shader.uuid}.geom.glsl"

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
    layout: dict[str, Any] = field(default_factory=dict)


def _write_default_pipeline_shader_artifacts(
    package_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader_compiler: str | Path | None,
) -> None:
    compiler = _resolve_shader_compiler(Path(shader_compiler) if shader_compiler is not None else None)
    if compiler is None:
        raise FileNotFoundError(
            "Shader compiler 'termin_shaderc' was not found. "
            "Default pipeline shaders require precompiled SPIR-V for Android."
        )

    for shader in _default_pipeline_engine_shaders():
        _write_engine_shader_artifact(package_dir, diagnostics, shader, compiler)
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
            layout=_builtin_engine_shader_layout(entry, artifact_language=program_language),
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
        layout=_builtin_engine_shader_layout(entry),
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


def _builtin_engine_shader_layout(
    entry: dict[str, Any],
    *,
    artifact_language: str | None = None,
) -> dict[str, Any]:
    source_language = entry.get("language", "glsl")
    layout = {
        "version": 1,
        "uuid": entry["uuid"],
        "name": entry.get("name", entry["uuid"]),
        "language": artifact_language or source_language,
        "resources": entry.get("resources", []),
        "binding_model": "resource_layout",
    }
    if artifact_language is not None and artifact_language != source_language:
        layout["source_language"] = source_language
    if "stages" in entry:
        layout["stages"] = entry.get("stages", {})
    if "program" in entry:
        layout["program"] = entry.get("program", {})
    return layout


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
) -> None:
    del diagnostics
    if shader.language not in {"glsl", "slang"}:
        raise ValueError(f"Engine shader '{shader.uuid}' has unsupported language: {shader.language}")

    vulkan_dir = package_dir / "shaders" / "vulkan"
    opengl_dir = package_dir / "shaders" / "opengl"
    layout_dir = package_dir / "shaders" / "layout"
    vulkan_dir.mkdir(parents=True, exist_ok=True)
    if shader.language == "slang":
        opengl_dir.mkdir(parents=True, exist_ok=True)
    if shader.layout:
        layout_dir.mkdir(parents=True, exist_ok=True)
        (layout_dir / f"{shader.uuid}.shader-layout.json").write_text(
            json.dumps(shader.layout, indent=2),
            encoding="utf-8",
        )

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
        _compile_shader_stage(
            compiler,
            shader.language,
            "vulkan",
            "vertex",
            vertex_source_path,
            vulkan_dir / f"{shader.uuid}.vert.spv",
            f"{shader.name}:vertex",
            shader.vertex_entry,
        )
        if shader.language == "slang":
            _compile_shader_stage(
                compiler,
                shader.language,
                "opengl",
                "vertex",
                vertex_source_path,
                opengl_dir / f"{shader.uuid}.vert.glsl",
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
    _compile_shader_stage(
        compiler,
        shader.language,
        "vulkan",
        "fragment",
        fragment_source_path,
        vulkan_dir / f"{shader.uuid}.frag.spv",
        f"{shader.name}:fragment",
        shader.fragment_entry,
    )
    if shader.language == "slang":
        _compile_shader_stage(
            compiler,
            shader.language,
            "opengl",
            "fragment",
            fragment_source_path,
            opengl_dir / f"{shader.uuid}.frag.glsl",
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
    raise ValueError(f"Unsupported shader language: {language}")


def _builtin_shader_catalog_entry(uuid_value: str) -> dict[str, Any]:
    catalog = _builtin_shader_catalog()
    shaders = catalog.get("shaders")
    if not isinstance(shaders, list):
        raise ValueError("Built-in shader catalog has no shader list")
    for entry in shaders:
        if isinstance(entry, dict) and entry.get("uuid") == uuid_value:
            return entry
    raise KeyError(f"Built-in shader catalog has no entry for '{uuid_value}'")


def _builtin_shader_catalog() -> dict[str, Any]:
    catalog_path = _builtin_shader_catalog_path()
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Built-in shader catalog is not an object: {catalog_path}")
    version = data.get("version")
    if version != 1:
        raise ValueError(f"Built-in shader catalog has unsupported version: {version}")
    return data


def _builtin_shader_catalog_path() -> Path:
    filename = "engine-shader-catalog.json"
    for root in _builtin_shader_roots():
        path = root / filename
        if path.exists():
            return path
    roots = ", ".join(str(root) for root in _builtin_shader_roots())
    raise FileNotFoundError(f"Built-in shader catalog '{filename}' was not found in: {roots}")


def _builtin_shader_source(filename: str) -> str:
    for root in _builtin_shader_roots():
        path = root / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
    roots = ", ".join(str(root) for root in _builtin_shader_roots())
    raise FileNotFoundError(f"Built-in shader source '{filename}' was not found in: {roots}")


def _builtin_shader_roots() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[3]
    roots = [
        repo_root / "termin-graphics" / "resources" / "builtin_shaders",
    ]

    sdk_env = os.environ.get("TERMIN_SDK")
    if sdk_env:
        roots.append(Path(sdk_env).resolve() / "share" / "termin" / "builtin_shaders")

    roots.append(Path(sys.prefix).resolve() / "share" / "termin" / "builtin_shaders")
    return roots


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


def _resource_sort_key(resource: dict[str, str]) -> tuple[int, str]:
    type_order = {
        "shader": 0,
        "pipeline": 1,
        "mesh": 2,
        "material": 3,
    }
    resource_type = resource["type"]
    return (type_order.get(resource_type, 100), resource["path"])


def _write_pipelines(
    project_root: Path,
    package_dir: Path,
    pipelines: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    if not pipelines:
        return

    pipeline_dir = package_dir / "pipelines"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(pipelines.items()):
        source = _find_pipeline_source(project_root, uuid_value, name)
        if source is None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=f"pipelines/{uuid_value}.pipeline.json",
                    message=(
                        f"Runtime exporter could not find pipeline asset "
                        f"'{name}' ({uuid_value})"
                    ),
                )
            )
            continue

        try:
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("pipeline JSON root must be an object")
        except Exception as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=str(source.relative_to(project_root)),
                    message=f"Runtime exporter failed to read pipeline asset: {exc}",
                )
            )
            continue

        data.setdefault("uuid", uuid_value)
        data.setdefault("name", name)

        target_name = _safe_package_stem(uuid_value or name)
        target = pipeline_dir / f"{target_name}.pipeline.json"
        _write_json(target, data)
        resources.append(
            {
                "type": "pipeline",
                "uuid": uuid_value,
                "name": name,
                "path": f"pipelines/{target_name}.pipeline.json",
            }
        )


def _safe_package_stem(value: str) -> str:
    result = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            result.append(ch)
        else:
            result.append("_")
    stem = "".join(result).strip("._")
    return stem or "pipeline"


def _find_pipeline_source(project_root: Path, uuid_value: str, name: str) -> Path | None:
    pipeline_paths = list(_iter_project_pipeline_paths(project_root))

    if uuid_value:
        for path in pipeline_paths:
            meta_path = path.with_suffix(path.suffix + ".meta")
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    if isinstance(meta, dict) and meta.get("uuid") == uuid_value:
                        return path
                except Exception:
                    pass

        for path in pipeline_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("uuid") == uuid_value:
                    return path
            except Exception:
                pass

    if name:
        expected = f"{name}.pipeline"
        for path in pipeline_paths:
            if path.name == expected:
                return path

    return None


def _iter_project_pipeline_paths(project_root: Path):
    ignored_parts = {".git", "__pycache__", "build", "dist"}
    for path in project_root.rglob("*.pipeline"):
        rel = path.relative_to(project_root)
        if any(part in ignored_parts for part in rel.parts):
            continue
        yield path


def _write_meshes(
    project_root: Path,
    package_dir: Path,
    meshes: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    mesh_dir = package_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(meshes.items()):
        path = mesh_dir / f"{uuid_value}.tmesh.json"
        mesh_spec = _export_mesh_spec(project_root, uuid_value, name, diagnostics)
        _write_json(path, mesh_spec)
        resources.append(
            {
                "type": "mesh",
                "uuid": uuid_value,
                "path": f"meshes/{uuid_value}.tmesh.json",
            }
        )


def _write_materials(
    package_dir: Path,
    materials: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, _ShaderSpec],
    default_shader_language: str,
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
        )
        _write_json(path, material_spec)
        resources.append(
            {
                "type": "material",
                "uuid": uuid_value,
                "path": f"materials/{uuid_value}.tmat.json",
            }
        )


def _export_mesh_spec(
    project_root: Path,
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any]:
    mesh_source = _find_mesh_source(project_root, uuid_value, name)
    if mesh_source is not None:
        try:
            return _mesh_source_to_spec(mesh_source, uuid_value, name)
        except Exception as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=str(mesh_source.relative_to(project_root)),
                    message=f"Runtime exporter failed to read mesh asset: {exc}",
                )
            )

    try:
        from tmesh import TcMesh

        mesh = TcMesh.from_uuid(uuid_value)
        if mesh.is_valid:
            return _mesh_to_spec(mesh)
    except Exception as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"meshes/{uuid_value}.tmesh.json",
                message=f"Runtime exporter failed to read mesh registry entry: {exc}",
            )
        )

    diagnostics.append(
        RuntimePackageExportDiagnostic(
            level="warning",
            path=f"meshes/{uuid_value}.tmesh.json",
            message="Runtime exporter used fallback mesh because registry entry is unavailable",
        )
    )
    return _fallback_mesh_spec(uuid_value, name)


def _find_mesh_source(project_root: Path, uuid_value: str, name: str) -> Path | None:
    mesh_paths = list(_iter_project_mesh_paths(project_root))

    if uuid_value:
        for path in mesh_paths:
            meta_path = Path(str(path) + ".meta")
            if not meta_path.exists():
                continue
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if isinstance(meta, dict) and meta.get("uuid") == uuid_value:
                    return path
            except Exception:
                pass

    if name:
        for path in mesh_paths:
            if path.stem == name:
                return path

    return None


def _iter_project_mesh_paths(project_root: Path):
    ignored_parts = {".git", "__pycache__", "build", "dist"}
    supported_suffixes = {".obj", ".stl"}
    for path in project_root.rglob("*"):
        rel = path.relative_to(project_root)
        if any(part in ignored_parts for part in rel.parts):
            continue
        if path.is_file() and path.suffix.lower() in supported_suffixes:
            yield path


def _mesh_source_to_spec(source_path: Path, uuid_value: str, name: str) -> dict[str, Any]:
    from termin.mesh.asset import MeshAsset

    asset = MeshAsset(name=name, source_path=source_path, uuid=uuid_value)
    meta_path = Path(str(source_path) + ".meta")
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            raise ValueError(f"mesh meta JSON root must be an object: {meta_path}")
        asset.parse_spec(meta)

    mesh = asset.data
    if mesh is None or not mesh.is_valid:
        raise ValueError(f"mesh asset did not produce a valid TcMesh: {source_path}")
    return _mesh_to_spec(mesh)


def _mesh_to_spec(mesh: Any) -> dict[str, Any]:
    vertices_buffer = mesh.get_vertices_buffer()
    indices_buffer = mesh.get_indices_buffer()
    if vertices_buffer is None or indices_buffer is None:
        raise ValueError(f"Mesh '{mesh.uuid}' has no vertex or index data")

    return {
        "uuid": mesh.uuid,
        "name": mesh.name or mesh.uuid,
        "draw_mode": _draw_mode_to_json(mesh.draw_mode),
        "layout": _mesh_layout_to_json(mesh),
        "vertices": _flat_number_list(vertices_buffer, float),
        "indices": _flat_number_list(indices_buffer, int),
        "vertex_count": int(mesh.vertex_count),
        "stride": int(mesh.stride),
    }


def _mesh_layout_to_json(mesh: Any) -> list[dict[str, Any]]:
    layout_obj = mesh.mesh.layout
    attributes: list[dict[str, Any]] = []
    for attr_name in ("position", "normal", "uv", "color", "tangent", "joints", "weights"):
        attr = layout_obj.find(attr_name)
        if attr is None:
            continue
        attr_type = _attrib_type_to_json(attr["type"])
        if attr_type != "float32":
            raise ValueError(
                f"Mesh '{mesh.uuid}' has unsupported runtime attribute type: {attr_name}={attr_type}"
            )
        attributes.append(
            {
                "name": str(attr["name"]),
                "location": int(attr["location"]),
                "components": int(attr["size"]),
                "type": attr_type,
            }
        )
    if not attributes:
        raise ValueError(f"Mesh '{mesh.uuid}' has no exportable vertex attributes")
    attributes.sort(key=lambda item: item["location"])
    return attributes


def _fallback_mesh_spec(uuid_value: str, name: str) -> dict[str, Any]:
    return {
        "uuid": uuid_value,
        "name": name,
        "draw_mode": "triangles",
        "layout": [
            {
                "name": "position",
                "location": 0,
                "components": 3,
                "type": "float32",
            },
            {
                "name": "color",
                "location": 1,
                "components": 3,
                "type": "float32",
            },
        ],
        "vertices": PLACEHOLDER_MESH_VERTICES,
        "indices": [0, 1, 2],
    }


def _export_material_spec(
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, _ShaderSpec],
    default_shader_language: str,
) -> dict[str, Any]:
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

    diagnostics.append(
        RuntimePackageExportDiagnostic(
            level="warning",
            path=f"materials/{uuid_value}.tmat.json",
            message="Runtime exporter used fallback material because registry entry is unavailable",
        )
    )
    shaders[DEFAULT_SHADER_UUID] = _default_shader_spec(default_shader_language)
    return _fallback_material_spec(uuid_value, name)


def _material_to_spec(material: Any, shaders: dict[str, _ShaderSpec]) -> dict[str, Any]:
    import tgfx  # Registers TcShader before TcMaterialPhase.shader casts it.

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


def _flat_number_list(values: Any, converter: Any) -> list[Any]:
    import numpy as np

    values = np.asarray(values).reshape(-1).tolist()
    result: list[Any] = []
    for value in values:
        result.append(converter(value))
    return result


def _draw_mode_to_json(value: Any) -> str:
    text = str(value)
    if text.endswith(".LINES"):
        return "lines"
    return "triangles"


def _attrib_type_to_json(value: Any) -> str:
    text = str(value)
    if text.endswith(".FLOAT32"):
        return "float32"
    if text.endswith(".INT32"):
        return "int32"
    if text.endswith(".UINT32"):
        return "uint32"
    if text.endswith(".INT16"):
        return "int16"
    if text.endswith(".UINT16"):
        return "uint16"
    if text.endswith(".INT8"):
        return "int8"
    if text.endswith(".UINT8"):
        return "uint8"
    raise ValueError(f"Unsupported vertex attribute type: {value}")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
