"""Runtime material asset export."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from termin.project_build.runtime_package.models import (
    RuntimePackageExportDiagnostic,
    ShaderSpec,
)
from termin.project_build.runtime_package.package_files import write_json
from termin.project_build.runtime_package.package_files import project_relative_path
from termin.project_build.runtime_package.shaders import shader_program_to_spec
from termin.project_build.runtime_package.textures import collect_material_texture_refs


def prepare_project_material_resources(
    project_root: Path,
    materials: dict[str, str],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    """Load referenced project materials after registering their shader assets."""
    import json

    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.default_assets.render.shader_asset import ShaderAsset
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin.stdlib import stdlib_root

    resource_manager = DefaultResourceManager.instance()
    material_paths: dict[str, Path] = {}
    for path in project_root.rglob("*.material"):
        rel = path.relative_to(project_root)
        if any(part in {".git", "__pycache__", "build", "dist"} for part in rel.parts):
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(document, dict) and document.get("uuid") in materials:
            material_paths[document["uuid"]] = path

    for uuid_value, name in sorted(materials.items()):
        material_path = material_paths.get(uuid_value)
        if material_path is None:
            continue
        try:
            document = json.loads(material_path.read_text(encoding="utf-8"))
            shader_name = document.get("shader")
            if not isinstance(shader_name, str) or not shader_name:
                raise ValueError("material has no canonical shader name")

            if resource_manager.get_shader_asset(shader_name) is None:
                shader_path = _find_project_or_standard_shader(
                    project_root,
                    stdlib_root(),
                    shader_name,
                )
                shader_asset = ShaderAsset.from_file(shader_path, name=shader_name)
                resource_manager.register_shader_asset(
                    shader_name,
                    shader_asset,
                    source_path=str(shader_path),
                    uuid=shader_asset.uuid,
                )

            existing_asset = resource_manager.get_material_asset_by_uuid(uuid_value)
            existing_material = (
                existing_asset.cached_data if existing_asset is not None else None
            )
            if existing_material is not None and existing_material.phase_count > 0:
                continue
            if existing_material is not None:
                raise ValueError(
                    "material was preloaded before its shader dependency and has no phases"
                )

            material_asset = MaterialAsset.from_file(material_path, name=name)
            resource_manager.register_material_asset(
                name,
                material_asset,
                source_path=str(material_path),
                uuid=uuid_value,
            )
        except Exception as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, material_path),
                    message=f"Runtime exporter failed to prepare project material: {exc}",
                )
            )


def _find_project_or_standard_shader(
    project_root: Path,
    standard_root: Path,
    shader_name: str,
) -> Path:
    matches = sorted(
        path
        for path in project_root.rglob(f"{shader_name}.shader")
        if not any(
            part in {".git", "__pycache__", "build", "dist"}
            for part in path.relative_to(project_root).parts
        )
    )
    if matches:
        return matches[0]

    standard_path = standard_root / "shaders" / f"{shader_name}.shader"
    if standard_path.is_file():
        return standard_path
    raise FileNotFoundError(f"shader asset '{shader_name}' was not found")


def write_materials(
    package_dir: Path,
    materials: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, ShaderSpec],
    shader_programs: dict[str, dict[str, Any]],
    default_shader_language: str,
    resource_policy: str,
    default_shader_uuid: str,
    default_shader_spec_factory: Callable[[str], ShaderSpec],
    texture_refs: dict[str, str],
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
            shader_programs,
            default_shader_language,
            resource_policy,
            default_shader_uuid,
            default_shader_spec_factory,
        )
        if material_spec is None:
            continue
        write_json(path, material_spec)
        collect_material_texture_refs(
            material_spec,
            texture_refs,
            diagnostics,
            f"materials/{uuid_value}.tmat.json",
        )
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
    shader_programs: dict[str, dict[str, Any]],
    default_shader_language: str,
    resource_policy: str,
    default_shader_uuid: str,
    default_shader_spec_factory: Callable[[str], ShaderSpec],
) -> dict[str, Any] | None:
    try:
        from termin.materials import TcMaterial

        material = TcMaterial.from_uuid(uuid_value)
        if material.is_valid:
            return material_to_spec(
                material,
                diagnostics,
                shaders,
                shader_programs,
            )
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


def material_to_spec(
    material: Any,
    diagnostics: list[RuntimePackageExportDiagnostic],
    shaders: dict[str, ShaderSpec],
    shader_programs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
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
    program_uuid = material.shader_program_uuid
    if program_uuid:
        from tgfx import TcShaderProgram, TextureEncoding

        program = TcShaderProgram.find(program_uuid)
        if not program.is_valid:
            raise ValueError(
                f"Material '{material.uuid}' references missing shader program '{program_uuid}'"
            )
        for program_phase in program.phases:
            phase_shader = program_phase["shader"]
            if not phase_shader.is_valid:
                raise ValueError(
                    f"Shader program '{program_uuid}' has stale phase "
                    f"'{program_phase['phase_mark']}'"
                )
            shaders[phase_shader.uuid] = shader_to_spec(phase_shader)
        shader_programs[program_uuid] = shader_program_to_spec(program)
        spec["shader_program"] = program_uuid
        texture_contract = {
            prop["name"]: prop["expected_encoding"]
            for prop in program.properties
            if prop["property_type"] in ("Texture", "Texture2D")
        }
        for slot_name, texture in material.textures.items():
            expected = texture_contract.get(slot_name)
            if expected is None or texture is None or not texture.is_valid:
                continue
            actual = (
                "srgb"
                if texture.encoding == TextureEncoding.SRGB
                else "linear"
            )
            if actual != expected:
                diagnostics.append(
                    RuntimePackageExportDiagnostic(
                        level="warning",
                        path=f"materials/{material.uuid}.tmat.json",
                        message=(
                            f"Material texture slot '{slot_name}' expects "
                            f"{expected}, got {actual}; exporting the binding "
                            "unchanged"
                        ),
                    )
                )
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
        if texture.name in ("__white_1x1__", "__white_srgb_1x1__"):
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
