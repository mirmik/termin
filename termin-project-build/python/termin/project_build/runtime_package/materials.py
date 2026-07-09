"""Runtime material asset export."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from termin.project_build.runtime_package.models import (
    RuntimePackageExportDiagnostic,
    ShaderSpec,
)
from termin.project_build.runtime_package.package_files import write_json


def write_materials(
    package_dir: Path,
    materials: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, ShaderSpec],
    default_shader_language: str,
    resource_policy: str,
    default_shader_uuid: str,
    default_shader_spec_factory: Callable[[str], ShaderSpec],
) -> None:
    material_dir = package_dir / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(materials.items()):
        path = material_dir / f"{uuid_value}.tmat.json"
        material_spec = export_material_spec(
            uuid_value,
            name,
            diagnostics,
            shaders,
            default_shader_language,
            resource_policy,
            default_shader_uuid,
            default_shader_spec_factory,
        )
        if material_spec is None:
            continue
        write_json(path, material_spec)
        resources.append(
            {
                "type": "material",
                "uuid": uuid_value,
                "path": f"materials/{uuid_value}.tmat.json",
            }
        )


def export_material_spec(
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, ShaderSpec],
    default_shader_language: str,
    resource_policy: str,
    default_shader_uuid: str,
    default_shader_spec_factory: Callable[[str], ShaderSpec],
) -> dict[str, Any] | None:
    try:
        from termin.materials import TcMaterial

        material = TcMaterial.from_uuid(uuid_value)
        if material.is_valid:
            return material_to_spec(material, shaders)
    except Exception as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"materials/{uuid_value}.tmat.json",
                message=f"Runtime exporter failed to read material registry entry: {exc}",
            )
        )

    if resource_policy_allows_fallback(resource_policy):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"materials/{uuid_value}.tmat.json",
                message="Runtime exporter used fallback material because registry entry is unavailable",
            )
        )
        shaders[default_shader_uuid] = default_shader_spec_factory(default_shader_language)
        return fallback_material_spec(uuid_value, name, default_shader_uuid)

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


def material_to_spec(material: Any, shaders: dict[str, ShaderSpec]) -> dict[str, Any]:
    import tgfx  # noqa: F401  # Registers TcShader before TcMaterialPhase.shader casts it.

    phases: list[dict[str, Any]] = []
    for phase in material.phases:
        shader = phase.shader
        if not shader.is_valid:
            raise ValueError(f"Material '{material.uuid}' has a phase with invalid shader")
        shaders[shader.uuid] = shader_to_spec(shader)
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
    uniforms = material_uniforms_to_json(material)
    if uniforms:
        spec["uniforms"] = uniforms
    textures = material_textures_to_json(material)
    if textures:
        spec["textures"] = textures
    return spec


def material_uniforms_to_json(material: Any) -> dict[str, Any]:
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


def material_textures_to_json(material: Any) -> dict[str, Any]:
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


def fallback_material_spec(uuid_value: str, name: str, default_shader_uuid: str) -> dict[str, Any]:
    return {
        "uuid": uuid_value,
        "name": name,
        "phases": [
            {
                "mark": "opaque",
                "shader": default_shader_uuid,
                "priority": 0,
            }
        ],
    }


def shader_to_spec(shader: Any) -> ShaderSpec:
    if shader.fragment_source == "":
        raise ValueError(f"Shader '{shader.uuid}' has no fragment source")
    return ShaderSpec(
        uuid=shader.uuid,
        name=shader.name or shader.uuid,
        source_path=shader.source_path or "runtime-registry",
        vertex_source=shader.vertex_source,
        fragment_source=shader.fragment_source,
        geometry_source=shader.geometry_source,
        language=shader_language(shader),
        vertex_entry=shader.vertex_entry,
        fragment_entry=shader.fragment_entry,
        geometry_entry=shader.geometry_entry,
        features=int(shader.features),
    )


def shader_language(shader: Any) -> str:
    language = shader.language
    if isinstance(language, str):
        text = language
    else:
        text = str(language)
    text = text.lower()
    if text.endswith(".glsl") or text == "glsl":
        return "glsl"
    if text.endswith(".slang") or text == "slang":
        return "slang"
    if text.endswith(".hlsl") or text == "hlsl":
        return "hlsl"
    return text


def resource_policy_allows_fallback(resource_policy: str) -> bool:
    return resource_policy == "dev_smoke"
