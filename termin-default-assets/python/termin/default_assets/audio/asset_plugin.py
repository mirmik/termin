"""Audio clip asset plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


class AudioClipImportPlugin:
    """Import-side plugin for audio clip source files."""

    type_id = "audio_clip"
    extensions = {".wav", ".ogg", ".mp3", ".flac"}
    priority = 10

    def preload(self, path: str) -> "PreLoadResult | None":
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


class AudioClipRuntimePlugin:
    """Runtime-side plugin handling lazy audio clip registration and reload."""

    type_id = "audio_clip"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.default_assets.audio.asset import AudioClipAsset

        rm = context.resource_manager
        name = context.name
        asset = None
        candidate = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if isinstance(candidate, AudioClipAsset):
            asset = candidate

        if asset is None:
            asset = AudioClipAsset(
                name=name,
                source_path=result.path,
                uuid=context.uuid,
            )

        rm.register_runtime_asset(self.type_id, name, asset, source_path=result.path, uuid=context.uuid)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        rm = context.resource_manager
        asset = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.reload()

    def unregister(self, context: "AssetContext", result: "PreLoadResult") -> None:
        context.resource_manager.unregister_runtime_asset_by_uuid(self.type_id, context.uuid)


class AudioClipAssetPlugin(AudioClipImportPlugin, AudioClipRuntimePlugin):
    """Compatibility combined audio clip plugin."""


def create_import_plugin() -> AudioClipImportPlugin:
    return AudioClipImportPlugin()


def create_runtime_plugin() -> AudioClipRuntimePlugin:
    return AudioClipRuntimePlugin()


def register_audio_clip_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(AudioClipImportPlugin())


def register_audio_clip_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(AudioClipRuntimePlugin())


def register_audio_clip_asset_plugin(registry: "AssetTypeRegistry") -> None:
    register_audio_clip_import_plugin(registry)
    register_audio_clip_runtime_plugin(registry)
