"""Explicit standard-library resource preparation for runtime package export."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path


def prepare_standard_resources(
    mesh_refs: Mapping[str, str],
    material_refs: Mapping[str, str],
) -> None:
    """Register referenced engine-owned resources without relying on editor state."""
    from termin.bootstrap import bootstrap_player
    from termin.default_assets.builtin_uuids import BUILTIN_UUIDS
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.default_assets.render.shader_asset import ShaderAsset
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin.stdlib import stdlib_root

    bootstrap_player()
    resource_manager = DefaultResourceManager.instance()
    resource_manager.register_builtin_textures()

    builtin_mesh_uuids = set(BUILTIN_UUIDS.values())
    if builtin_mesh_uuids.intersection(mesh_refs):
        resource_manager.register_builtin_meshes()

    missing_material_uuids = {
        uuid_value
        for uuid_value in material_refs
        if resource_manager.get_material_asset_by_uuid(uuid_value) is None
    }
    if not missing_material_uuids:
        return

    resources_root = stdlib_root()
    for material_path in sorted((resources_root / "materials").glob("*.material")):
        document = _read_json_object(material_path)
        uuid_value = document.get("uuid")
        if uuid_value not in missing_material_uuids:
            continue

        shader_name = document.get("shader")
        if not isinstance(shader_name, str) or not shader_name:
            raise ValueError(
                f"standard material '{material_path}' has no canonical shader name"
            )
        if resource_manager.get_shader_asset(shader_name) is None:
            shader_path = resources_root / "shaders" / f"{shader_name}.shader"
            if not shader_path.is_file():
                raise FileNotFoundError(
                    f"standard material '{material_path.name}' references missing "
                    f"shader '{shader_path}'"
                )
            shader_asset = ShaderAsset.from_file(shader_path, name=shader_name)
            resource_manager.register_shader_asset(
                shader_name,
                shader_asset,
                source_path=str(shader_path),
                uuid=shader_asset.uuid,
            )

        material_asset = MaterialAsset.from_file(material_path, name=material_path.stem)
        resource_manager.register_material_asset(
            material_path.stem,
            material_asset,
            source_path=str(material_path),
            uuid=material_asset.uuid,
        )
        missing_material_uuids.remove(uuid_value)
        if not missing_material_uuids:
            return


def _read_json_object(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"standard resource JSON root must be an object: {path}")
    return document
