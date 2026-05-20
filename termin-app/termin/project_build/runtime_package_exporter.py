"""Runtime package exporter.

The exporter writes the package contract consumed by termin-runtime:

    manifest.json
    scene.json
    meshes/*.tmesh.json
    materials/*.tmat.json
    shaders/*.shader.json
    shaders/vulkan/*.spv

This first implementation intentionally prefers an end-to-end package over
perfect resource fidelity. Real mesh/material extraction will replace the
diagnostic placeholder artifacts incrementally.
"""

from __future__ import annotations

import json
import shutil
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
    _write_default_shader(output_dir_path, resources)
    _write_placeholder_meshes(output_dir_path, refs.meshes, resources, diagnostics)
    _write_placeholder_materials(output_dir_path, refs.materials, resources, diagnostics)

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


def _write_default_shader(package_dir: Path, resources: list[dict[str, str]]) -> None:
    shader_dir = package_dir / "shaders"
    vulkan_dir = shader_dir / "vulkan"
    shader_dir.mkdir(parents=True, exist_ok=True)
    vulkan_dir.mkdir(parents=True, exist_ok=True)

    vertex_source_path = vulkan_dir / f"{DEFAULT_SHADER_UUID}.vert.glsl"
    fragment_source_path = vulkan_dir / f"{DEFAULT_SHADER_UUID}.frag.glsl"
    vertex_source_path.write_text(DEFAULT_VERTEX_SOURCE, encoding="utf-8")
    fragment_source_path.write_text(DEFAULT_FRAGMENT_SOURCE, encoding="utf-8")

    _copy_default_spirv(
        package_dir / "shaders" / "vulkan" / f"{DEFAULT_SHADER_UUID}.vert.spv",
        "termin-android-scene-color.vert.spv",
    )
    _copy_default_spirv(
        package_dir / "shaders" / "vulkan" / f"{DEFAULT_SHADER_UUID}.frag.spv",
        "termin-android-scene-color.frag.spv",
    )

    shader_spec_path = shader_dir / f"{DEFAULT_SHADER_UUID}.shader.json"
    _write_json(
        shader_spec_path,
        {
            "uuid": DEFAULT_SHADER_UUID,
            "name": DEFAULT_SHADER_NAME,
            "vertex_source_path": f"shaders/vulkan/{DEFAULT_SHADER_UUID}.vert.glsl",
            "fragment_source_path": f"shaders/vulkan/{DEFAULT_SHADER_UUID}.frag.glsl",
            "source_path": "termin-runtime/default-color",
        },
    )
    resources.append(
        {
            "type": "shader",
            "uuid": DEFAULT_SHADER_UUID,
            "path": f"shaders/{DEFAULT_SHADER_UUID}.shader.json",
        }
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


def _write_placeholder_meshes(
    package_dir: Path,
    meshes: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    mesh_dir = package_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(meshes.items()):
        path = mesh_dir / f"{uuid_value}.tmesh.json"
        _write_json(
            path,
            {
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
            },
        )
        resources.append(
            {
                "type": "mesh",
                "uuid": uuid_value,
                "path": f"meshes/{uuid_value}.tmesh.json",
            }
        )
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"meshes/{uuid_value}.tmesh.json",
                message="Runtime exporter used placeholder mesh geometry",
            )
        )


def _write_placeholder_materials(
    package_dir: Path,
    materials: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    material_dir = package_dir / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(materials.items()):
        path = material_dir / f"{uuid_value}.tmat.json"
        _write_json(
            path,
            {
                "uuid": uuid_value,
                "name": name,
                "phases": [
                    {
                        "mark": "opaque",
                        "shader": DEFAULT_SHADER_UUID,
                        "priority": 0,
                    }
                ],
            },
        )
        resources.append(
            {
                "type": "material",
                "uuid": uuid_value,
                "path": f"materials/{uuid_value}.tmat.json",
            }
        )
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"materials/{uuid_value}.tmat.json",
                message="Runtime exporter used placeholder material",
            )
        )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
