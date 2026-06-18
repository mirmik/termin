"""Compatibility re-export for audio clip asset plugins.

Canonical module: :mod:`termin.default_assets.audio.asset_plugin`.
"""

from termin.default_assets.audio.asset_plugin import (
    AudioClipAssetPlugin,
    AudioClipImportPlugin,
    AudioClipRuntimePlugin,
    create_import_plugin,
    create_runtime_plugin,
    register_audio_clip_asset_plugin,
    register_audio_clip_import_plugin,
    register_audio_clip_runtime_plugin,
)

__all__ = [
    "AudioClipAssetPlugin",
    "AudioClipImportPlugin",
    "AudioClipRuntimePlugin",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_audio_clip_asset_plugin",
    "register_audio_clip_import_plugin",
    "register_audio_clip_runtime_plugin",
]
