from termin.default_assets.audio.asset import AudioClipAsset
from termin.default_assets.audio.asset_plugin import create_import_plugin, create_runtime_plugin
from termin.default_assets.audio.handle import AudioClipHandle
from termin.audio import AudioClipAsset as PackageAudioClipAsset
from termin.audio import AudioClipHandle as PackageAudioClipHandle
from termin.audio.asset import AudioClipAsset as LegacyDomainAudioClipAsset
from termin.audio.asset_plugin import create_import_plugin as legacy_create_import_plugin
from termin.audio.asset_plugin import create_runtime_plugin as legacy_create_runtime_plugin
from termin.audio.audio_clip_asset import AudioClipAsset as LegacyAudioClipAsset
from termin.audio.audio_clip_handle import AudioClipHandle as LegacyAudioClipHandle
from termin.audio.handle import AudioClipHandle as LegacyDomainAudioClipHandle
from termin.assets.audio_clip_asset import AudioClipAsset as AppLegacyAudioClipAsset
from termin.assets.audio_clip_handle import AudioClipHandle as AppLegacyAudioClipHandle


def test_audio_clip_asset_legacy_modules_reexport_canonical_class() -> None:
    assert PackageAudioClipAsset is AudioClipAsset
    assert LegacyDomainAudioClipAsset is AudioClipAsset
    assert LegacyAudioClipAsset is AudioClipAsset
    assert AppLegacyAudioClipAsset is AudioClipAsset
    assert PackageAudioClipHandle is AudioClipHandle
    assert LegacyDomainAudioClipHandle is AudioClipHandle
    assert LegacyAudioClipHandle is AudioClipHandle
    assert AppLegacyAudioClipHandle is AudioClipHandle


def test_audio_clip_plugin_legacy_modules_reexport_factories() -> None:
    assert legacy_create_import_plugin is create_import_plugin
    assert legacy_create_runtime_plugin is create_runtime_plugin
    assert create_import_plugin().type_id == "audio_clip"
    assert create_runtime_plugin().type_id == "audio_clip"
