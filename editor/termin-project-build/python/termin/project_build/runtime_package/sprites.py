"""Runtime SpriteAsset export."""

from __future__ import annotations

import json
from pathlib import Path

from termin.project_build.runtime_package.models import RuntimePackageExportDiagnostic
from termin.project_build.runtime_package.package_files import project_relative_path, write_json


def write_sprites(
    project_root: Path,
    package_dir: Path,
    sprites: dict[str, str],
    textures: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    if not sprites:
        return

    sources = _index_sprite_sources(project_root, set(sprites), diagnostics)
    for uuid_value, name in sorted(sprites.items()):
        source = sources.get(uuid_value)
        output_rel = f"sprites/{uuid_value}.sprite.json"
        if source is None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=output_rel,
                    message=f"Runtime exporter could not find SpriteAsset UUID '{uuid_value}'",
                )
            )
            continue
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            _validate_sprite_payload(payload)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, source),
                    message=f"Runtime exporter rejected SpriteAsset: {exc}",
                )
            )
            continue

        texture_ref = payload["texture"]
        texture_uuid = texture_ref["uuid"] if isinstance(texture_ref, dict) else texture_ref
        texture_name = (
            texture_ref.get("name", texture_uuid)
            if isinstance(texture_ref, dict)
            else texture_uuid
        )
        textures[texture_uuid] = texture_name
        packaged = dict(payload)
        packaged["uuid"] = uuid_value
        packaged["name"] = name or uuid_value
        write_json(package_dir / output_rel, packaged)
        resources.append(
            {
                "type": "sprite_asset",
                "uuid": uuid_value,
                "name": name or uuid_value,
                "path": output_rel,
            }
        )


def _index_sprite_sources(
    project_root: Path,
    required: set[str],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Path]:
    result: dict[str, Path] = {}
    ignored = {".git", "__pycache__", "build", "dist"}
    for source in project_root.rglob("*.sprite"):
        if any(part in ignored for part in source.relative_to(project_root).parts):
            continue
        meta_path = Path(f"{source}.meta")
        if not meta_path.is_file():
            continue
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=project_relative_path(project_root, meta_path),
                    message=f"Runtime exporter failed to inspect SpriteAsset metadata: {exc}",
                )
            )
            continue
        uuid_value = metadata.get("uuid") if isinstance(metadata, dict) else None
        if uuid_value not in required:
            continue
        if uuid_value in result:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, source),
                    message=f"Duplicate SpriteAsset UUID '{uuid_value}'",
                )
            )
            continue
        result[uuid_value] = source
    return result


def _validate_sprite_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload root must be an object")
    if payload.get("format") != "termin.sprite" or payload.get("version") != 1:
        raise ValueError("unsupported format or version")
    texture = payload.get("texture")
    texture_uuid = texture.get("uuid") if isinstance(texture, dict) else texture
    if not isinstance(texture_uuid, str) or not texture_uuid:
        raise ValueError("texture UUID is missing")
    region = payload.get("region")
    source_size = payload.get("source_size")
    if not isinstance(region, list) or len(region) != 4:
        raise ValueError("region must contain four integers")
    if not isinstance(source_size, list) or len(source_size) != 2:
        raise ValueError("source_size must contain two integers")
