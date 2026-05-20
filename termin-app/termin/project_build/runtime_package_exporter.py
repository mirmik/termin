"""Runtime package exporter.

The exporter writes the package contract consumed by termin-runtime:

    manifest.json
    scene.json
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_SHADER_UUID = "termin-runtime-default-color"
DEFAULT_SHADER_NAME = "TerminRuntimeDefaultColor"


DEFAULT_VERTEX_SOURCE = """#version 450
layout(location = 0) in vec3 in_position;
layout(location = 1) in vec3 in_color;

layout(location = 0) out vec3 v_color;

layout(set = 0, binding = 0) uniform CameraUBO {
    mat4 view;
    mat4 proj;
    mat4 view_proj;
    vec4 camera_pos;
} u_camera;

layout(push_constant) uniform PushConstants {
    mat4 model;
} pc;

void main() {
    v_color = in_color;
    gl_Position = u_camera.view_proj * pc.model * vec4(in_position, 1.0);
}
"""


DEFAULT_FRAGMENT_SOURCE = """#version 450
layout(location = 0) in vec3 v_color;
layout(location = 0) out vec4 out_color;

void main() {
    out_color = vec4(v_color, 1.0);
}
"""


ENGINE_SKYBOX_SHADER_UUID = "termin-engine-skybox"
ENGINE_FSQ_SHADER_UUID = "termin-engine-fsq"
ENGINE_SHADOW_SHADER_UUID = "termin-engine-shadow"
ENGINE_BLOOM_BRIGHT_SHADER_UUID = "termin-engine-bloom-bright"
ENGINE_BLOOM_DOWNSAMPLE_SHADER_UUID = "termin-engine-bloom-downsample"
ENGINE_BLOOM_UPSAMPLE_SHADER_UUID = "termin-engine-bloom-upsample"
ENGINE_BLOOM_COMPOSITE_SHADER_UUID = "termin-engine-bloom-composite"
ENGINE_TONEMAP_SHADER_UUID = "termin-engine-tonemap"


ENGINE_SKYBOX_SHADER_TEXT = """
@program Skybox

@phase opaque
@priority 0
@glDepthTest true
@glDepthMask false
@glCull false

@property Mat4  u_view
@property Mat4  u_projection
@property Int   u_skybox_type
@property Color u_skybox_color        = Color(0.5, 0.5, 0.5, 1.0)
@property Color u_skybox_top_color    = Color(0.3, 0.5, 1.0, 1.0)
@property Color u_skybox_bottom_color = Color(0.1, 0.1, 0.3, 1.0)

@stage vertex
#version 450 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_view;
uniform mat4 u_projection;

layout(location = 0) out vec3 v_dir;

void main() {
    mat4 view_no_translation = mat4(mat3(u_view));
    v_dir = a_position;
    gl_Position = u_projection * view_no_translation * vec4(a_position, 1.0);
}
@endstage

@stage fragment
#version 450 core

layout(location = 0) in vec3 v_dir;
layout(location = 0) out vec4 FragColor;

uniform int  u_skybox_type;
uniform vec4 u_skybox_color;
uniform vec4 u_skybox_top_color;
uniform vec4 u_skybox_bottom_color;

void main() {
    if (u_skybox_type == 1) {
        FragColor = vec4(u_skybox_color.rgb, 1.0);
    } else {
        float t = normalize(v_dir).z * 0.5 + 0.5;
        vec3 c = mix(u_skybox_bottom_color.rgb, u_skybox_top_color.rgb, t);
        FragColor = vec4(c, 1.0);
    }
}
@endstage

@endphase
"""


ENGINE_FSQ_VERTEX_SOURCE = """#version 450 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUV;
layout(location = 0) out vec2 vUV;
void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
    vUV = aUV;
}
"""


ENGINE_SHADOW_VERTEX_SOURCE = """#version 450 core
layout(location = 0) in vec3 a_position;

layout(std140, binding = 0) uniform PerFrame {
    mat4 u_view;
    mat4 u_projection;
};

struct ShadowPushData {
    mat4 u_model;
};
#ifdef VULKAN
layout(push_constant) uniform ShadowPushBlock { ShadowPushData pc; };
#else
layout(std140, binding = 14) uniform ShadowPushBlock { ShadowPushData pc; };
#endif

void main() {
    gl_Position = u_projection * u_view * pc.u_model * vec4(a_position, 1.0);
}
"""


ENGINE_SHADOW_FRAGMENT_SOURCE = """#version 450 core
void main() {
}
"""


ENGINE_BLOOM_BRIGHT_FRAGMENT_SOURCE = """#version 450 core
layout(location = 0) in vec2 vUV;

layout(std140, binding = 0) uniform BloomBrightParams {
    float u_threshold;
    float u_soft_threshold;
};

layout(binding = 4) uniform sampler2D u_texture;

layout(location = 0) out vec4 FragColor;

void main() {
    vec3 color = texture(u_texture, vUV).rgb;
    float brightness = dot(color, vec3(0.2126, 0.7152, 0.0722));
    float knee = u_threshold * u_soft_threshold;
    float soft = brightness - u_threshold + knee;
    soft = clamp(soft, 0.0, 2.0 * knee);
    soft = soft * soft / (4.0 * knee + 0.00001);
    float contribution = max(soft, brightness - u_threshold) / max(brightness, 0.00001);
    contribution = max(contribution, 0.0);
    FragColor = vec4(color * contribution, 1.0);
}
"""


ENGINE_BLOOM_DOWNSAMPLE_FRAGMENT_SOURCE = """#version 450 core
layout(location = 0) in vec2 vUV;

layout(std140, binding = 0) uniform BloomDownsampleParams {
    vec2 u_texel_size;
};

layout(binding = 4) uniform sampler2D u_texture;

layout(location = 0) out vec4 FragColor;

void main() {
    vec2 ts = u_texel_size;
    vec3 a = texture(u_texture, vUV + vec2(-2.0, -2.0) * ts).rgb;
    vec3 b = texture(u_texture, vUV + vec2( 0.0, -2.0) * ts).rgb;
    vec3 c = texture(u_texture, vUV + vec2( 2.0, -2.0) * ts).rgb;
    vec3 d = texture(u_texture, vUV + vec2(-2.0,  0.0) * ts).rgb;
    vec3 e = texture(u_texture, vUV + vec2( 0.0,  0.0) * ts).rgb;
    vec3 f = texture(u_texture, vUV + vec2( 2.0,  0.0) * ts).rgb;
    vec3 g = texture(u_texture, vUV + vec2(-2.0,  2.0) * ts).rgb;
    vec3 h = texture(u_texture, vUV + vec2( 0.0,  2.0) * ts).rgb;
    vec3 i = texture(u_texture, vUV + vec2( 2.0,  2.0) * ts).rgb;
    vec3 j = texture(u_texture, vUV + vec2(-1.0, -1.0) * ts).rgb;
    vec3 k = texture(u_texture, vUV + vec2( 1.0, -1.0) * ts).rgb;
    vec3 l = texture(u_texture, vUV + vec2(-1.0,  1.0) * ts).rgb;
    vec3 m = texture(u_texture, vUV + vec2( 1.0,  1.0) * ts).rgb;
    vec3 result = e * 0.125;
    result += (a + c + g + i) * 0.03125;
    result += (b + d + f + h) * 0.0625;
    result += (j + k + l + m) * 0.125;
    FragColor = vec4(result, 1.0);
}
"""


ENGINE_BLOOM_UPSAMPLE_FRAGMENT_SOURCE = """#version 450 core
layout(location = 0) in vec2 vUV;

layout(std140, binding = 0) uniform BloomUpsampleParams {
    vec2 u_texel_size;
    float u_blend_factor;
};

layout(binding = 4) uniform sampler2D u_texture;

layout(location = 0) out vec4 FragColor;

void main() {
    vec2 ts = u_texel_size;
    vec3 a = texture(u_texture, vUV + vec2(-1.0, -1.0) * ts).rgb;
    vec3 b = texture(u_texture, vUV + vec2( 0.0, -1.0) * ts).rgb;
    vec3 c = texture(u_texture, vUV + vec2( 1.0, -1.0) * ts).rgb;
    vec3 d = texture(u_texture, vUV + vec2(-1.0,  0.0) * ts).rgb;
    vec3 e = texture(u_texture, vUV + vec2( 0.0,  0.0) * ts).rgb;
    vec3 f = texture(u_texture, vUV + vec2( 1.0,  0.0) * ts).rgb;
    vec3 g = texture(u_texture, vUV + vec2(-1.0,  1.0) * ts).rgb;
    vec3 h = texture(u_texture, vUV + vec2( 0.0,  1.0) * ts).rgb;
    vec3 i = texture(u_texture, vUV + vec2( 1.0,  1.0) * ts).rgb;
    vec3 upsampled = e * 4.0;
    upsampled += (b + d + f + h) * 2.0;
    upsampled += (a + c + g + i);
    upsampled /= 16.0;
    FragColor = vec4(upsampled * u_blend_factor, 1.0);
}
"""


ENGINE_BLOOM_COMPOSITE_FRAGMENT_SOURCE = """#version 450 core
layout(location = 0) in vec2 vUV;

layout(std140, binding = 0) uniform BloomCompositeParams {
    float u_intensity;
};

layout(binding = 4) uniform sampler2D u_original;
layout(binding = 5) uniform sampler2D u_bloom;

layout(location = 0) out vec4 FragColor;

void main() {
    vec3 original = texture(u_original, vUV).rgb;
    vec3 bloom = texture(u_bloom, vUV).rgb;
    vec3 result = original + bloom * u_intensity;
    FragColor = vec4(result, 1.0);
}
"""


ENGINE_TONEMAP_FRAGMENT_SOURCE = """#version 450 core
layout(location=0) in vec2 vUV;

layout(std140, binding = 0) uniform TonemapParams {
    float u_exposure;
    int u_method;
};

layout(binding = 4) uniform sampler2D u_input;

layout(location=0) out vec4 FragColor;

vec3 aces_tonemap(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

vec3 reinhard_tonemap(vec3 x) {
    return x / (x + vec3(1.0));
}

void main() {
    vec3 color = texture(u_input, vUV).rgb;
    color *= u_exposure;
    if (u_method == 0) {
        color = aces_tonemap(color);
    } else if (u_method == 1) {
        color = reinhard_tonemap(color);
    }
    FragColor = vec4(color, 1.0);
}
"""


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
) -> RuntimePackageExportResult:
    project_root_path = Path(project_root).resolve()
    entry_scene_path = _resolve_entry_scene(project_root_path, Path(entry_scene))
    output_dir_path = Path(output_dir).resolve()

    scene_data = _read_scene_data(entry_scene_path)
    diagnostics: list[RuntimePackageExportDiagnostic] = []
    refs = _collect_runtime_refs(scene_data)

    _write_clean_package_dir(output_dir_path)
    scene_path = output_dir_path / "scene.json"
    _write_json(scene_path, scene_data)

    resources: list[dict[str, str]] = []
    shaders: dict[str, _ShaderSpec] = {}
    _write_meshes(output_dir_path, refs.meshes, resources, diagnostics)
    _write_materials(output_dir_path, refs.materials, resources, diagnostics, shaders)
    if not shaders:
        shaders[DEFAULT_SHADER_UUID] = _ShaderSpec(
            uuid=DEFAULT_SHADER_UUID,
            name=DEFAULT_SHADER_NAME,
            source_path="termin-runtime/default-color",
            vertex_source=DEFAULT_VERTEX_SOURCE,
            fragment_source=DEFAULT_FRAGMENT_SOURCE,
            geometry_source="",
            allow_precompiled_default=True,
        )
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


@dataclass
class _ShaderSpec:
    uuid: str
    name: str
    source_path: str
    vertex_source: str
    fragment_source: str
    geometry_source: str = ""
    allow_precompiled_default: bool = False


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
    shader_dir = package_dir / "shaders"
    vulkan_dir = shader_dir / "vulkan"
    shader_dir.mkdir(parents=True, exist_ok=True)
    vulkan_dir.mkdir(parents=True, exist_ok=True)

    vertex_source_path = vulkan_dir / f"{shader.uuid}.vert.glsl"
    fragment_source_path = vulkan_dir / f"{shader.uuid}.frag.glsl"
    vertex_source_path.write_text(shader.vertex_source, encoding="utf-8")
    fragment_source_path.write_text(shader.fragment_source, encoding="utf-8")

    geometry_source_path = None
    if shader.geometry_source != "":
        geometry_source_path = vulkan_dir / f"{shader.uuid}.geom.glsl"
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
            "vertex",
            vertex_source_path,
            vulkan_dir / f"{shader.uuid}.vert.spv",
            f"{shader.name or shader.uuid}:vertex",
        )
        _compile_shader_stage(
            compiler,
            "fragment",
            fragment_source_path,
            vulkan_dir / f"{shader.uuid}.frag.spv",
            f"{shader.name or shader.uuid}:fragment",
        )
        if geometry_source_path is not None:
            _compile_shader_stage(
                compiler,
                "geometry",
                geometry_source_path,
                vulkan_dir / f"{shader.uuid}.geom.spv",
                f"{shader.name or shader.uuid}:geometry",
            )

    shader_spec: dict[str, Any] = {
        "uuid": shader.uuid,
        "name": shader.name or shader.uuid,
        "vertex_source_path": f"shaders/vulkan/{shader.uuid}.vert.glsl",
        "fragment_source_path": f"shaders/vulkan/{shader.uuid}.frag.glsl",
        "source_path": shader.source_path,
    }
    if geometry_source_path is not None:
        shader_spec["geometry_source_path"] = f"shaders/vulkan/{shader.uuid}.geom.glsl"

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
    vertex_source: str = ""
    fragment_source: str = ""


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


def _default_pipeline_engine_shaders() -> list[_EngineShaderArtifact]:
    skybox_vertex, skybox_fragment = _parse_skybox_engine_shader()
    return [
        _EngineShaderArtifact(
            uuid=ENGINE_FSQ_SHADER_UUID,
            name="FullscreenQuadEngineVS",
            vertex_source=ENGINE_FSQ_VERTEX_SOURCE,
        ),
        _EngineShaderArtifact(
            uuid=ENGINE_SKYBOX_SHADER_UUID,
            name="SkyboxEngineVSFS",
            vertex_source=skybox_vertex,
            fragment_source=skybox_fragment,
        ),
        _EngineShaderArtifact(
            uuid=ENGINE_SHADOW_SHADER_UUID,
            name="ShadowEngineVSFS",
            vertex_source=ENGINE_SHADOW_VERTEX_SOURCE,
            fragment_source=ENGINE_SHADOW_FRAGMENT_SOURCE,
        ),
        _EngineShaderArtifact(
            uuid=ENGINE_BLOOM_BRIGHT_SHADER_UUID,
            name="BloomBrightFS",
            fragment_source=ENGINE_BLOOM_BRIGHT_FRAGMENT_SOURCE,
        ),
        _EngineShaderArtifact(
            uuid=ENGINE_BLOOM_DOWNSAMPLE_SHADER_UUID,
            name="BloomDownsampleFS",
            fragment_source=ENGINE_BLOOM_DOWNSAMPLE_FRAGMENT_SOURCE,
        ),
        _EngineShaderArtifact(
            uuid=ENGINE_BLOOM_UPSAMPLE_SHADER_UUID,
            name="BloomUpsampleFS",
            fragment_source=ENGINE_BLOOM_UPSAMPLE_FRAGMENT_SOURCE,
        ),
        _EngineShaderArtifact(
            uuid=ENGINE_BLOOM_COMPOSITE_SHADER_UUID,
            name="BloomCompositeFS",
            fragment_source=ENGINE_BLOOM_COMPOSITE_FRAGMENT_SOURCE,
        ),
        _EngineShaderArtifact(
            uuid=ENGINE_TONEMAP_SHADER_UUID,
            name="TonemapEngineFS",
            fragment_source=ENGINE_TONEMAP_FRAGMENT_SOURCE,
        ),
    ]


def _parse_skybox_engine_shader() -> tuple[str, str]:
    from termin.materials import parse_shader_text

    program = parse_shader_text(ENGINE_SKYBOX_SHADER_TEXT)
    if len(program.phases) == 0:
        raise RuntimeError("Default pipeline skybox shader parser returned no phases")
    phase = program.phases[0]
    vertex_stage = phase.stages.get("vertex")
    fragment_stage = phase.stages.get("fragment")
    if vertex_stage is None or fragment_stage is None:
        raise RuntimeError("Default pipeline skybox shader parser returned incomplete stages")
    return vertex_stage.source, fragment_stage.source


def _write_engine_shader_artifact(
    package_dir: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shader: _EngineShaderArtifact,
    compiler: Path,
) -> None:
    del diagnostics
    vulkan_dir = package_dir / "shaders" / "vulkan"
    vulkan_dir.mkdir(parents=True, exist_ok=True)

    if shader.vertex_source != "":
        vertex_source_path = vulkan_dir / f"{shader.uuid}.vert.glsl"
        vertex_source_path.write_text(shader.vertex_source, encoding="utf-8")
        _compile_shader_stage(
            compiler,
            "vertex",
            vertex_source_path,
            vulkan_dir / f"{shader.uuid}.vert.spv",
            f"{shader.name}:vertex",
        )

    if shader.fragment_source == "":
        return

    fragment_source_path = vulkan_dir / f"{shader.uuid}.frag.glsl"
    fragment_source_path.write_text(shader.fragment_source, encoding="utf-8")
    _compile_shader_stage(
        compiler,
        "fragment",
        fragment_source_path,
        vulkan_dir / f"{shader.uuid}.frag.spv",
        f"{shader.name}:fragment",
    )


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
        "mesh": 1,
        "material": 2,
    }
    resource_type = resource["type"]
    return (type_order.get(resource_type, 100), resource["path"])


def _write_meshes(
    package_dir: Path,
    meshes: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    mesh_dir = package_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(meshes.items()):
        path = mesh_dir / f"{uuid_value}.tmesh.json"
        mesh_spec = _export_mesh_spec(uuid_value, name, diagnostics)
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
) -> None:
    material_dir = package_dir / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(materials.items()):
        path = material_dir / f"{uuid_value}.tmat.json"
        material_spec = _export_material_spec(uuid_value, name, diagnostics, shaders)
        _write_json(path, material_spec)
        resources.append(
            {
                "type": "material",
                "uuid": uuid_value,
                "path": f"materials/{uuid_value}.tmat.json",
            }
        )


def _export_mesh_spec(
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any]:
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
    shaders[DEFAULT_SHADER_UUID] = _ShaderSpec(
        uuid=DEFAULT_SHADER_UUID,
        name=DEFAULT_SHADER_NAME,
        source_path="termin-runtime/default-color",
        vertex_source=DEFAULT_VERTEX_SOURCE,
        fragment_source=DEFAULT_FRAGMENT_SOURCE,
        geometry_source="",
        allow_precompiled_default=True,
    )
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

    return {
        "uuid": material.uuid,
        "name": material.name or material.uuid,
        "phases": phases,
    }


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
    )


def _resolve_shader_compiler(shader_compiler: Path | None) -> Path | None:
    if shader_compiler is not None:
        compiler = shader_compiler.resolve()
        if not compiler.exists():
            raise FileNotFoundError(f"Shader compiler does not exist: {compiler}")
        return compiler

    found = shutil.which("termin_shaderc")
    if found is not None:
        return Path(found).resolve()

    sdk_env = os.environ.get("TERMIN_SDK")
    if sdk_env is not None and sdk_env != "":
        sdk_compiler = Path(sdk_env).resolve() / "bin" / "termin_shaderc"
        if sdk_compiler.exists():
            return sdk_compiler

    local_sdk_compiler = Path(__file__).resolve().parents[3] / "sdk" / "bin" / "termin_shaderc"
    if local_sdk_compiler.exists():
        return local_sdk_compiler

    return None


def _compile_shader_stage(
    compiler: Path,
    stage: str,
    input_path: Path,
    output_path: Path,
    debug_name: str,
) -> None:
    cmd = [
        str(compiler),
        "compile",
        "--target",
        "vulkan",
        "--stage",
        stage,
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--entry",
        "main",
        "--debug-name",
        debug_name,
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Shader compilation failed for {input_path.name}: {message}")
    if not output_path.exists():
        raise RuntimeError(f"Shader compiler did not produce expected output: {output_path}")


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
