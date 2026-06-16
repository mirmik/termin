"""Runtime package resource loader for the Python desktop player."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np


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
    shaders: dict[str, Any] = {}
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


def _load_resource(package_dir: Path, entry: dict[str, Any], shaders: dict[str, Any]) -> bool:
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
        shaders[shader.uuid] = shader
        return True
    if resource_type == "mesh":
        return _load_mesh(spec, path)
    if resource_type == "material":
        return _load_material(spec, path, shaders)

    log.error(f"[PlayerRuntime] Unsupported runtime package resource type: {resource_type}")
    return False


def _load_shader(package_dir: Path, spec: dict[str, Any], path: Path) -> Any | None:
    from tcbase import log
    import tgfx
    from termin.assets.shader_asset import shader_language_enum

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
    return shader


def _load_mesh(spec: dict[str, Any], path: Path) -> bool:
    from tcbase import log
    from tmesh import TcAttribType, TcDrawMode, TcMesh, TcVertexLayout
    from termin.assets.mesh_asset import MeshAsset
    from termin.assets.resources import ResourceManager

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

    rm = ResourceManager.instance()
    rm.register_mesh_asset(name, MeshAsset(mesh_data=mesh, name=name, source_path=path, uuid=uuid_value), str(path), uuid_value)
    return True


def _load_material(spec: dict[str, Any], path: Path, shaders: dict[str, Any]) -> bool:
    from tcbase import log
    from termin.assets.material_asset import MaterialAsset
    from termin.assets.resources import ResourceManager
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
        shader = shaders.get(shader_uuid)
        if shader is None or not shader.is_valid:
            log.error(f"[PlayerRuntime] Runtime material references missing shader: {shader_uuid}")
            return False
        material.add_phase(shader, _string(phase_spec, "mark", "opaque"), int(phase_spec.get("priority", 0)))

    rm = ResourceManager.instance()
    rm.register_material(name, material, str(path), uuid_value)
    rm._assets_by_uuid[uuid_value] = MaterialAsset(material=material, name=name, source_path=path, uuid=uuid_value)
    return True


def _read_optional_text(package_dir: Path, rel_path: str) -> str:
    if rel_path == "":
        return ""
    path = package_dir / rel_path
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _string(data: dict[str, Any], key: str, default: str = "") -> str:
    value = data.get(key, default)
    return value if isinstance(value, str) else default
