"""Standalone portable animation clip import and runtime plugins."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.base import log

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


def _validate_uuid(value: object, location: str) -> str:
    try:
        if type(value) is not str or not value or value.strip() != value or "\0" in value:
            raise ValueError("expected a nonempty string without outer whitespace or NUL")
        if len(value.encode("utf-8")) > 63:
            raise ValueError("UUID exceeds 63 UTF-8 bytes")
    except (ValueError, UnicodeError) as exc:
        log.error(f"[AnimationClipPlugin] Invalid UUID in {location}: {exc}")
        raise ValueError(f"Invalid animation UUID in {location}: {exc}") from exc
    return value


def _validate_runtime_identity(context: "AssetContext", result: "PreLoadResult") -> None:
    canonical_uuid = _validate_uuid(context.uuid, f"context for '{result.path}'")
    result_uuid = _validate_uuid(result.uuid, f"preload result for '{result.path}'")
    if result.resource_type != "animation_clip" or result_uuid != canonical_uuid:
        message = f"Preload identity does not match animation context for '{result.path}'"
        log.error(f"[AnimationClipPlugin] {message}")
        raise ValueError(message)
    if result.spec_data is not None:
        if type(result.spec_data) is not dict:
            message = f"Animation metadata must be an object for '{result.path}'"
            log.error(f"[AnimationClipPlugin] {message}")
            raise ValueError(message)
        metadata_uuid = _validate_uuid(result.spec_data.get("uuid"), f"metadata for '{result.path}'")
        if metadata_uuid != canonical_uuid:
            message = f"Metadata UUID does not match animation context for '{result.path}'"
            log.error(f"[AnimationClipPlugin] {message}")
            raise ValueError(message)


class AnimationClipImportPlugin:
    """Declare a .tanim source with persistent sidecar-owned identity."""

    type_id = "animation_clip"
    extensions = {".tanim"}
    priority = 10

    def preload(self, path: str) -> "PreLoadResult | None":
        from termin_assets import AssetIdentityPolicy, PreLoadResult, read_spec_file

        spec_data = read_spec_file(path)
        if spec_data is None and Path(path + ".meta").exists():
            log.error(f"[AnimationClipPlugin] Invalid existing metadata for '{path}'")
            return None
        uuid = None
        if spec_data is not None and "uuid" in spec_data:
            try:
                uuid = _validate_uuid(spec_data["uuid"], f"metadata for '{path}'")
            except ValueError:
                return None
        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            content=None,
            uuid=uuid,
            spec_data=spec_data,
            identity_policy=AssetIdentityPolicy.GENERATE_SIDECAR,
        )


class AnimationClipRuntimePlugin:
    """Register lazy canonical handles and reload their payload in place."""

    type_id = "animation_clip"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.animation._animation_native import tc_animation_declare
        from termin.default_assets.animation.asset import AnimationClipAsset

        _validate_runtime_identity(context, result)
        rm = context.resource_manager
        asset = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if asset is not None and not isinstance(asset, AnimationClipAsset):
            message = f"UUID '{context.uuid}' does not belong to an AnimationClipAsset"
            log.error(f"[AnimationClipPlugin] {message}")
            raise TypeError(message)
        if asset is None:
            asset = AnimationClipAsset(name=context.name, source_path=result.path, uuid=context.uuid)

        clip = asset.cached_data
        if asset.uuid != context.uuid or (clip is not None and (not clip.is_valid or clip.uuid != context.uuid)):
            message = f"Asset/native identity does not match animation UUID '{context.uuid}'"
            log.error(f"[AnimationClipPlugin] {message}")
            raise ValueError(message)
        if result.spec_data is not None:
            asset.parse_spec(result.spec_data)
        if clip is None:
            clip = tc_animation_declare(context.uuid, context.name)
            if not clip.is_valid:
                message = f"Failed to declare animation UUID '{context.uuid}' from '{result.path}'"
                log.error(f"[AnimationClipPlugin] {message}")
                raise RuntimeError(message)
            asset.set_runtime_data(clip, loaded=False)

        rm.register_runtime_asset(
            self.type_id, context.name, asset, source_path=result.path, uuid=context.uuid,
        )

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> bool:
        from termin.default_assets.animation.asset import AnimationClipAsset

        try:
            _validate_runtime_identity(context, result)
        except ValueError:
            return False
        asset = context.resource_manager.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if not isinstance(asset, AnimationClipAsset):
            log.error(f"[AnimationClipPlugin] Missing animation asset '{context.uuid}' for '{result.path}'")
            return False
        if not asset.is_loaded or not asset.should_reload_from_file():
            return True
        if not asset.reload():
            log.error(f"[AnimationClipPlugin] Failed to reload animation '{context.uuid}' from '{result.path}'")
            return False
        return True

    def unregister(self, context: "AssetContext", result: "PreLoadResult") -> None:
        _validate_runtime_identity(context, result)
        context.resource_manager.unregister_runtime_asset_by_uuid(self.type_id, context.uuid)


class AnimationClipAssetPlugin(AnimationClipImportPlugin, AnimationClipRuntimePlugin):
    """Combined plugin for explicit registration of both sides."""


def create_import_plugin() -> AnimationClipImportPlugin:
    return AnimationClipImportPlugin()


def create_runtime_plugin() -> AnimationClipRuntimePlugin:
    return AnimationClipRuntimePlugin()


def register_animation_clip_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(AnimationClipImportPlugin())


def register_animation_clip_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(AnimationClipRuntimePlugin())


def register_animation_clip_asset_plugin(registry: "AssetTypeRegistry") -> None:
    register_animation_clip_import_plugin(registry)
    register_animation_clip_runtime_plugin(registry)
