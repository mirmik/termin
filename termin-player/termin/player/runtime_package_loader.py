"""Runtime package resource loader for the Python desktop player."""

from __future__ import annotations

import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class _RuntimeShader:
    shader: Any
    material_texture_resources: tuple[str, ...]


def load_runtime_package_assets(package_dir: Path, manifest_path: Path) -> None:
    """Load meshes/materials/shaders from a runtime package manifest."""
    from tcbase import log

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    if not isinstance(manifest, dict):
        log.error(f"[PlayerRuntime] Runtime package manifest root is not an object: {manifest_path}")
        return

    _configure_shader_runtime(package_dir, manifest)

    resources = manifest.get("resources")
    if not isinstance(resources, list):
        log.error(f"[PlayerRuntime] Runtime package manifest has no resources list: {manifest_path}")
        return

    loaded = 0
    shaders: dict[str, _RuntimeShader] = {}
    for resource_type in ("shader", "mesh", "material", "pipeline", "foliage_data"):
        for entry in resources:
            if not isinstance(entry, dict) or entry.get("type") != resource_type:
                continue
            if _load_resource(package_dir, entry, shaders):
                loaded += 1

    log.info(f"[PlayerRuntime] Loaded {loaded} runtime package resource(s)")


def _configure_shader_runtime(package_dir: Path, manifest: dict[str, Any]) -> None:
    from tcbase import log

    artifact_root_value = manifest.get("shader_artifact_root", ".")
    artifact_root = package_dir / str(artifact_root_value)
    cache_root = package_dir / ".shader-cache"
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.error(f"[PlayerRuntime] Failed to create runtime shader cache: {exc}")
        return

    os.environ["TERMIN_SHADER_ARTIFACT_ROOT"] = str(artifact_root)
    os.environ["TERMIN_SHADER_CACHE_ROOT"] = str(cache_root)
    os.environ["TERMIN_SHADER_DEV_COMPILE"] = "0"

    try:
        import tgfx

        tgfx.configure_shader_runtime(
            artifact_root=str(artifact_root),
            cache_root=str(cache_root),
            shader_compiler=os.environ.get("TERMIN_SHADERC", ""),
            dev_compile=False,
        )
    except Exception as exc:
        log.error(f"[PlayerRuntime] Failed to configure runtime package shader runtime: {exc}")
        return

    log.info(f"[PlayerRuntime] Runtime package shader artifacts: {artifact_root}")


def _load_resource(package_dir: Path, entry: dict[str, Any], shaders: dict[str, _RuntimeShader]) -> bool:
    from tcbase import log

    resource_type = entry.get("type")
    rel_path = entry.get("path")
    if not isinstance(resource_type, str) or not isinstance(rel_path, str):
        log.error("[PlayerRuntime] Runtime package resource entry requires type and path")
        return False
    if resource_type == "pipeline":
        return True
    if resource_type == "foliage_data":
        log.warning(f"[PlayerRuntime] Python player does not load foliage_data yet: {rel_path}")
        return True

    path = package_dir / rel_path
    if not path.exists():
        log.error(f"[PlayerRuntime] Runtime package resource file not found: {path}")
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except Exception as exc:
        log.error(f"[PlayerRuntime] Failed to read runtime package resource {path}: {exc}")
        return False
    if not isinstance(spec, dict):
        log.error(f"[PlayerRuntime] Runtime package resource is not an object: {path}")
        return False

    if resource_type == "shader":
        shader = _load_shader(package_dir, spec, path)
        if shader is None:
            return False
        shaders[shader.shader.uuid] = shader
        return True
    if resource_type == "mesh":
        return _load_mesh(spec, path)
    if resource_type == "material":
        return _load_material(spec, path, shaders)

    log.error(f"[PlayerRuntime] Unsupported runtime package resource type: {resource_type}")
    return False


def _load_shader(package_dir: Path, spec: dict[str, Any], path: Path) -> _RuntimeShader | None:
    from tcbase import log
    import tgfx
    from termin.default_assets.render.shader_asset import shader_language_enum

    uuid_value = _string(spec, "uuid")
    if uuid_value == "":
        log.error(f"[PlayerRuntime] Runtime shader has no uuid: {path}")
        return None
    vertex_source = _read_optional_text(package_dir, _string(spec, "vertex_source_path"))
    fragment_source = _read_optional_text(package_dir, _string(spec, "fragment_source_path"))
    geometry_source = _read_optional_text(package_dir, _string(spec, "geometry_source_path"))
    if fragment_source == "":
        log.error(f"[PlayerRuntime] Runtime shader has no fragment source: {uuid_value}")
        return None

    shader = tgfx.TcShader.get_or_create(uuid_value)
    if not shader.is_valid:
        log.error(f"[PlayerRuntime] Failed to create runtime shader: {uuid_value}")
        return None

    language = _string(spec, "language", "glsl")
    shader.set_language(shader_language_enum(language))
    if language.lower() == "slang":
        shader.set_artifact_policy(tgfx.ShaderArtifactPolicy.REQUIRED)
    else:
        shader.set_artifact_policy(tgfx.ShaderArtifactPolicy.OPTIONAL)
    shader.set_sources_with_entries(
        vertex_source,
        fragment_source,
        geometry_source,
        _string(spec, "name", uuid_value),
        str(path),
        _string(spec, "vertex_entry"),
        _string(spec, "fragment_entry"),
        _string(spec, "geometry_entry"),
    )
    shader.set_features(int(spec.get("features", 0)))
    return _RuntimeShader(
        shader=shader,
        material_texture_resources=_material_texture_resources_from_shader_spec(package_dir, spec),
    )


def _load_mesh(spec: dict[str, Any], path: Path) -> bool:
    from tcbase import log
    from tmesh import TcAttribType, TcDrawMode, TcMesh, TcVertexLayout
    from termin.default_assets.mesh.asset import MeshAsset
    from termin.default_assets.resource_manager import DefaultResourceManager

    uuid_value = _string(spec, "uuid")
    name = _string(spec, "name", uuid_value)
    layout_spec = spec.get("layout")
    vertices_spec = spec.get("vertices")
    indices_spec = spec.get("indices")
    if uuid_value == "" or name == "":
        log.error(f"[PlayerRuntime] Runtime mesh requires uuid and name: {path}")
        return False
    if not isinstance(layout_spec, list) or not isinstance(vertices_spec, list) or not isinstance(indices_spec, list):
        log.error(f"[PlayerRuntime] Runtime mesh requires layout, vertices and indices: {uuid_value}")
        return False

    layout = TcVertexLayout()
    floats_per_vertex = 0
    for attrib in layout_spec:
        if not isinstance(attrib, dict):
            log.error(f"[PlayerRuntime] Runtime mesh has invalid layout entry: {uuid_value}")
            return False
        attrib_name = _string(attrib, "name")
        attrib_type = _string(attrib, "type", "float32")
        components = int(attrib.get("components", 0))
        location = int(attrib.get("location", 0))
        if attrib_name == "" or attrib_type != "float32" or components <= 0:
            log.error(f"[PlayerRuntime] Runtime mesh has unsupported layout: {uuid_value}")
            return False
        layout.add(attrib_name, components, TcAttribType.FLOAT32, location)
        floats_per_vertex += components

    vertices = np.asarray(vertices_spec, dtype=np.float32)
    indices = np.asarray(indices_spec, dtype=np.uint32)
    if floats_per_vertex <= 0 or len(vertices) % floats_per_vertex != 0 or len(indices) == 0:
        log.error(f"[PlayerRuntime] Runtime mesh data does not match layout: {uuid_value}")
        return False

    draw_mode = TcDrawMode.LINES if _string(spec, "draw_mode") == "lines" else TcDrawMode.TRIANGLES
    mesh = TcMesh.from_interleaved(
        vertices,
        len(vertices) // floats_per_vertex,
        indices,
        layout,
        name,
        uuid_value,
        draw_mode,
    )
    if not mesh.is_valid:
        log.error(f"[PlayerRuntime] Failed to create runtime mesh: {uuid_value}")
        return False

    rm = DefaultResourceManager.instance()
    rm.register_mesh_asset(name, MeshAsset(mesh_data=mesh, name=name, source_path=path, uuid=uuid_value), str(path), uuid_value)
    return True


def _load_material(spec: dict[str, Any], path: Path, shaders: dict[str, _RuntimeShader]) -> bool:
    from tcbase import log
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin.materials import TcMaterial

    uuid_value = _string(spec, "uuid")
    name = _string(spec, "name", uuid_value)
    phases = spec.get("phases")
    if uuid_value == "" or name == "":
        log.error(f"[PlayerRuntime] Runtime material requires uuid and name: {path}")
        return False
    if not isinstance(phases, list):
        log.error(f"[PlayerRuntime] Runtime material requires phases: {uuid_value}")
        return False

    material = TcMaterial.get_or_create(uuid_value, name)
    if not material.is_valid:
        log.error(f"[PlayerRuntime] Failed to create runtime material: {uuid_value}")
        return False
    material.clear_phases()

    for phase_spec in phases:
        if not isinstance(phase_spec, dict):
            log.error(f"[PlayerRuntime] Runtime material has invalid phase: {uuid_value}")
            return False
        shader_uuid = _string(phase_spec, "shader")
        shader_info = shaders.get(shader_uuid)
        if shader_info is None or not shader_info.shader.is_valid:
            log.error(f"[PlayerRuntime] Runtime material references missing shader: {shader_uuid}")
            return False
        phase = material.add_phase(
            shader_info.shader,
            _string(phase_spec, "mark", "opaque"),
            int(phase_spec.get("priority", 0)),
        )
        _apply_default_material_textures(phase, shader_info.material_texture_resources, uuid_value)

    _apply_material_uniforms(material, spec.get("uniforms"), uuid_value)
    _apply_material_textures(material, spec.get("textures"), uuid_value)

    rm = DefaultResourceManager.instance()
    rm.register_material(name, material, str(path), uuid_value)
    rm._assets_by_uuid[uuid_value] = MaterialAsset(material=material, name=name, source_path=path, uuid=uuid_value)
    return True


def _material_texture_resources_from_shader_spec(package_dir: Path, spec: dict[str, Any]) -> tuple[str, ...]:
    from tcbase import log

    result: list[str] = []
    seen: set[str] = set()
    artifacts = spec.get("artifacts")
    if not isinstance(artifacts, dict):
        return ()

    for target_spec in artifacts.values():
        if not isinstance(target_spec, dict):
            continue
        for artifact_path in target_spec.values():
            if not isinstance(artifact_path, str) or artifact_path == "":
                continue
            layout_path = package_dir / f"{artifact_path}.layout.json"
            if not layout_path.exists():
                continue
            try:
                layout = json.loads(layout_path.read_text(encoding="utf-8"))
            except Exception as exc:
                log.error(f"[PlayerRuntime] Failed to read shader layout '{layout_path}': {exc}")
                continue
            resources = layout.get("resources")
            if not isinstance(resources, list):
                continue
            for resource in resources:
                if not isinstance(resource, dict):
                    continue
                if resource.get("kind") != "texture" or resource.get("scope") != "material":
                    continue
                name = resource.get("name")
                if not isinstance(name, str) or name == "" or name in seen:
                    continue
                seen.add(name)
                result.append(name)

    return tuple(result)


def _apply_default_material_textures(phase: Any, texture_names: tuple[str, ...], uuid_value: str) -> None:
    from tcbase import log

    for name in texture_names:
        tc_tex = _builtin_texture_for_material_slot(name)
        if tc_tex is None:
            log.error(f"[PlayerRuntime] Failed to resolve default texture '{name}' for material: {uuid_value}")
            continue
        phase.set_texture(name, tc_tex)


def _builtin_texture_for_material_slot(name: str) -> Any | None:
    from termin.render.texture_handle import get_normal_texture_handle, get_white_texture_handle

    if "normal" in name.lower():
        return get_normal_texture_handle()
    return get_white_texture_handle()


def _apply_material_textures(material: Any, textures: object, uuid_value: str) -> None:
    from tcbase import log
    from termin.default_assets.resource_manager import DefaultResourceManager

    if textures is None:
        return
    if not isinstance(textures, dict):
        log.error(f"[PlayerRuntime] Runtime material textures must be an object: {uuid_value}")
        return

    rm = DefaultResourceManager.instance()
    for name, value in textures.items():
        if not isinstance(name, str):
            log.error(f"[PlayerRuntime] Runtime material texture name must be a string: {uuid_value}")
            continue

        tc_tex = None
        if isinstance(value, dict):
            if value.get("kind") == "builtin":
                builtin_name = value.get("name")
                if builtin_name == "normal":
                    tc_tex = _builtin_texture_for_material_slot("normal")
                elif builtin_name == "white":
                    tc_tex = _builtin_texture_for_material_slot("white")
            else:
                texture_uuid = value.get("uuid")
                if isinstance(texture_uuid, str) and texture_uuid != "":
                    asset = rm.get_texture_asset_by_uuid(texture_uuid)
                    if asset is not None:
                        if asset.texture_data is None:
                            asset.ensure_loaded()
                        tc_tex = asset.texture_data
        elif isinstance(value, str) and value != "":
            asset = rm.get_texture_asset_by_uuid(value)
            if asset is not None:
                if asset.texture_data is None:
                    asset.ensure_loaded()
                tc_tex = asset.texture_data

        if tc_tex is None or not tc_tex.is_valid:
            log.error(f"[PlayerRuntime] Failed to resolve material texture '{name}': {uuid_value}")
            continue
        material.set_texture(name, tc_tex)


def _apply_material_uniforms(material: Any, uniforms: object, uuid_value: str) -> None:
    from tcbase import log
    from termin.geombase import Vec3, Vec4

    if uniforms is None:
        return
    if not isinstance(uniforms, dict):
        log.error(f"[PlayerRuntime] Runtime material uniforms must be an object: {uuid_value}")
        return

    for name, value in uniforms.items():
        if not isinstance(name, str):
            log.error(f"[PlayerRuntime] Runtime material uniform name must be a string: {uuid_value}")
            continue
        if isinstance(value, bool):
            material.set_uniform_int(name, 1 if value else 0)
        elif isinstance(value, int):
            material.set_uniform_int(name, value)
        elif isinstance(value, float):
            material.set_uniform_float(name, value)
        elif isinstance(value, list) and len(value) == 3 and _all_numbers(value):
            material.set_uniform_vec3(name, Vec3(float(value[0]), float(value[1]), float(value[2])))
        elif isinstance(value, list) and len(value) == 4 and _all_numbers(value):
            material.set_uniform_vec4(
                name,
                Vec4(float(value[0]), float(value[1]), float(value[2]), float(value[3])),
            )
        else:
            log.error(
                f"[PlayerRuntime] Runtime material uniform '{name}' has unsupported value: {uuid_value}"
            )


def _all_numbers(values: list[object]) -> bool:
    return all(isinstance(item, (int, float)) for item in values)


def _read_optional_text(package_dir: Path, rel_path: str) -> str:
    if rel_path == "":
        return ""
    path = package_dir / rel_path
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _string(data: dict[str, Any], key: str, default: str = "") -> str:
    value = data.get(key, default)
    return value if isinstance(value, str) else default
