"""Sprite asset import and native-registry lifecycle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from termin.base import log

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


SPRITE_ASSET_TYPE_ID = "sprite_asset"
SPRITE_ASSET_FORMAT = "termin.sprite"
SPRITE_ASSET_FORMAT_VERSION = 1


class SpriteAssetImportPlugin:
    type_id = "sprite_asset"
    extensions = {".sprite"}
    priority = 10

    def preload(self, path: str) -> "PreLoadResult":
        from termin_assets import AssetIdentityPolicy, PreLoadResult, read_spec_file

        spec_data = read_spec_file(path)
        uuid = spec_data.get("uuid") if spec_data else None
        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            content=None,
            uuid=uuid,
            spec_data=spec_data,
            identity_policy=AssetIdentityPolicy.GENERATE_SIDECAR,
        )


class SpriteAssetRuntimePlugin:
    type_id = SPRITE_ASSET_TYPE_ID

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin_assets import AssetRecord

        handle = _load_native_sprite(
            uuid=context.uuid,
            name=context.name,
            path=result.path,
        )
        if handle is None or not handle.is_valid:
            log.error(
                f"[SpriteAssetRuntimePlugin] failed to register sprite: {context.uuid}"
            )
            return
        context.resource_manager.external_assets.upsert(
            AssetRecord(
                type_id=self.type_id,
                name=context.name,
                path=result.path,
                uuid=context.uuid,
                spec_data=result.spec_data,
            )
        )

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        self.register(context, result)

    def unregister(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.render_components import TcSpriteAsset

        handle = TcSpriteAsset.from_uuid(context.uuid)
        if handle.is_valid:
            handle.unload()
        context.resource_manager.external_assets.remove(self.type_id, context.uuid)


def _load_native_sprite(uuid: str, name: str, path: str):
    from termin.render_components import (
        SpriteRegion,
        SpriteSampling,
        TcSpriteAsset,
    )

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        _validate_payload(payload, path)
        texture = payload["texture"]
        texture_uuid = texture["uuid"] if isinstance(texture, dict) else texture
        region_values = payload["region"]
        source_size = payload["source_size"]
        pivot = payload.get("pivot", [0.5, 0.5])
        sampling_name = payload.get("sampling", "linear")
        sampling = (
            SpriteSampling.Nearest
            if sampling_name == "nearest"
            else SpriteSampling.Linear
        )
        handle = TcSpriteAsset.declare(uuid, name, path)
        if not handle.update(
            texture_uuid=texture_uuid,
            region=SpriteRegion(*region_values),
            source_width=source_size[0],
            source_height=source_size[1],
            pivot_x=pivot[0],
            pivot_y=pivot[1],
            pixels_per_unit=payload.get("pixels_per_unit", 100.0),
            sampling=sampling,
        ):
            return None
        return handle
    except Exception:
        log.error(f"[SpriteAssetRuntimePlugin] invalid sprite file: {path}", exc_info=True)
        return None


def _validate_payload(payload: object, path: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"Sprite payload must be an object: {path}")
    if payload.get("format") != SPRITE_ASSET_FORMAT:
        raise ValueError(f"Unsupported sprite format in {path}")
    if payload.get("version") != SPRITE_ASSET_FORMAT_VERSION:
        raise ValueError(f"Unsupported sprite version in {path}")
    texture = payload.get("texture")
    texture_uuid = texture.get("uuid") if isinstance(texture, dict) else texture
    if not isinstance(texture_uuid, str) or not texture_uuid:
        raise ValueError(f"Sprite texture UUID is missing in {path}")
    for field in ("region", "source_size"):
        value = payload.get(field)
        expected_size = 4 if field == "region" else 2
        if (
            not isinstance(value, list)
            or len(value) != expected_size
            or any(not isinstance(item, int) for item in value)
        ):
            raise ValueError(f"Sprite {field} is invalid in {path}")
    sampling = payload.get("sampling", "linear")
    if sampling not in {"linear", "nearest"}:
        raise ValueError(f"Sprite sampling is invalid in {path}")


def create_import_plugin() -> SpriteAssetImportPlugin:
    return SpriteAssetImportPlugin()


def create_runtime_plugin() -> SpriteAssetRuntimePlugin:
    return SpriteAssetRuntimePlugin()


def register_sprite_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(SpriteAssetImportPlugin())
