"""Runtime mesh asset export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from termin.project_build.runtime_package.models import RuntimePackageExportDiagnostic
from termin.project_build.runtime_package.package_files import (
    append_project_file_diagnostic,
    project_relative_path,
    write_json,
)


PLACEHOLDER_MESH_VERTICES = [
    0.0, 0.65, 0.0, 1.0, 0.05, 0.05,
    -0.75, -0.55, 0.0, 0.05, 1.0, 0.05,
    0.75, -0.55, 0.0, 0.05, 0.20, 1.0,
]


def write_meshes(
    project_root: Path,
    package_dir: Path,
    meshes: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
    resource_policy: str,
) -> None:
    mesh_dir = package_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(meshes.items()):
        path = mesh_dir / f"{uuid_value}.tmesh.json"
        mesh_spec = export_mesh_spec(project_root, uuid_value, name, diagnostics, resource_policy)
        if mesh_spec is None:
            continue
        write_json(path, mesh_spec)
        resources.append(
            {
                "type": "mesh",
                "uuid": uuid_value,
                "path": f"meshes/{uuid_value}.tmesh.json",
            }
        )


def export_mesh_spec(
    project_root: Path,
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
    resource_policy: str,
) -> dict[str, Any] | None:
    mesh_source = find_mesh_source(project_root, uuid_value, name, diagnostics)
    if mesh_source is not None:
        try:
            return mesh_source_to_spec(mesh_source, uuid_value, name)
        except Exception as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=project_relative_path(project_root, mesh_source),
                    message=f"Runtime exporter failed to read mesh asset: {exc}",
                )
            )

    try:
        from tmesh import TcMesh

        mesh = TcMesh.from_uuid(uuid_value)
        if mesh.is_valid:
            return mesh_to_spec(mesh)
    except Exception as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"meshes/{uuid_value}.tmesh.json",
                message=f"Runtime exporter failed to read mesh registry entry: {exc}",
            )
        )

    if resource_policy_allows_fallback(resource_policy):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="warning",
                path=f"meshes/{uuid_value}.tmesh.json",
                message="Runtime exporter used fallback mesh because registry entry is unavailable",
            )
        )
        return fallback_mesh_spec(uuid_value, name)

    diagnostics.append(
        RuntimePackageExportDiagnostic(
            level="error",
            path=f"meshes/{uuid_value}.tmesh.json",
            message=(
                "Runtime exporter could not export mesh because no project source "
                "or runtime registry entry was found; fallback mesh requires "
                "resource_policy=dev_smoke"
            ),
        )
    )
    return None


def find_mesh_source(
    project_root: Path,
    uuid_value: str,
    name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Path | None:
    mesh_paths = list(iter_project_mesh_paths(project_root))

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
                if not isinstance(meta, dict):
                    append_project_file_diagnostic(
                        diagnostics,
                        project_root,
                        meta_path,
                        "Runtime exporter skipped mesh metadata because JSON root is not an object",
                    )
            except Exception as exc:
                append_project_file_diagnostic(
                    diagnostics,
                    project_root,
                    meta_path,
                    f"Runtime exporter failed to inspect mesh metadata: {exc}",
                )

    if name:
        for path in mesh_paths:
            if path.stem == name:
                return path

    return None


def iter_project_mesh_paths(project_root: Path):
    ignored_parts = {".git", "__pycache__", "build", "dist"}
    supported_suffixes = {".obj", ".stl"}
    for path in project_root.rglob("*"):
        rel = path.relative_to(project_root)
        if any(part in ignored_parts for part in rel.parts):
            continue
        if path.is_file() and path.suffix.lower() in supported_suffixes:
            yield path


def mesh_source_to_spec(source_path: Path, uuid_value: str, name: str) -> dict[str, Any]:
    from termin.default_assets.mesh.asset import MeshAsset

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
    return mesh_to_spec(mesh)


def mesh_to_spec(mesh: Any) -> dict[str, Any]:
    vertices_buffer = mesh.get_vertices_buffer()
    indices_buffer = mesh.get_indices_buffer()
    if vertices_buffer is None or indices_buffer is None:
        raise ValueError(f"Mesh '{mesh.uuid}' has no vertex or index data")

    return {
        "uuid": mesh.uuid,
        "name": mesh.name or mesh.uuid,
        "draw_mode": draw_mode_to_json(mesh.draw_mode),
        "layout": mesh_layout_to_json(mesh),
        "vertices": flat_number_list(vertices_buffer, float),
        "indices": flat_number_list(indices_buffer, int),
        "submeshes": mesh_submeshes_to_json(mesh),
        "vertex_count": int(mesh.vertex_count),
        "stride": int(mesh.stride),
    }


def mesh_submeshes_to_json(mesh: Any) -> list[dict[str, Any]]:
    submeshes = []
    for submesh in mesh.submeshes:
        submeshes.append(
            {
                "first_index": int(submesh.first_index),
                "index_count": int(submesh.index_count),
                "vertex_offset": int(submesh.vertex_offset),
                "material_slot": int(submesh.material_slot),
                "draw_mode": draw_mode_to_json(submesh.draw_mode),
                "name": str(submesh.name),
            }
        )
    return submeshes


def mesh_layout_to_json(mesh: Any) -> list[dict[str, Any]]:
    layout_obj = mesh.mesh.layout
    attributes: list[dict[str, Any]] = []
    for attr_name in ("position", "normal", "uv", "color", "tangent", "joints", "weights"):
        attr = layout_obj.find(attr_name)
        if attr is None:
            continue
        attr_type = attrib_type_to_json(attr["type"])
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


def fallback_mesh_spec(uuid_value: str, name: str) -> dict[str, Any]:
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
        "submeshes": [
            {
                "first_index": 0,
                "index_count": 3,
                "vertex_offset": 0,
                "material_slot": 0,
                "draw_mode": "triangles",
                "name": name,
            }
        ],
    }


def resource_policy_allows_fallback(resource_policy: str) -> bool:
    return resource_policy == "dev_smoke"


def flat_number_list(values: Any, converter: Any) -> list[Any]:
    import numpy as np

    values = np.asarray(values).reshape(-1).tolist()
    result: list[Any] = []
    for value in values:
        result.append(converter(value))
    return result


def draw_mode_to_json(value: Any) -> str:
    text = str(value)
    if text.endswith(".LINES"):
        return "lines"
    return "triangles"


def attrib_type_to_json(value: Any) -> str:
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
