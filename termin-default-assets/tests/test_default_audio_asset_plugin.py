import struct
import wave
from pathlib import Path

from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult
from termin.audio import TcAudioClip
from termin.default_assets.audio.asset import AudioClipAsset
from termin.default_assets.audio.asset_plugin import (
    create_import_plugin,
    create_runtime_plugin,
    register_audio_clip_import_plugin,
    register_audio_clip_runtime_plugin,
)


class FakeResourceManager:
    def __init__(self) -> None:
        self.by_name = {}
        self.by_uuid = {}

    def get_runtime_asset(self, type_id: str, name: str):
        return self.by_name.get((type_id, name))

    def get_runtime_asset_by_uuid(self, type_id: str, uuid: str):
        return self.by_uuid.get((type_id, uuid))

    def register_runtime_asset(self, type_id: str, name: str, asset, *, source_path=None, uuid=None) -> None:
        self.by_name[(type_id, name)] = asset
        if uuid is not None:
            self.by_uuid[(type_id, uuid)] = asset

    def get_audio_clip_asset(self, name: str):
        return self.by_name.get(("audio_clip", name))

    def get_audio_clip_asset_by_uuid(self, uuid: str):
        return self.by_uuid.get(("audio_clip", uuid))


def test_audio_clip_asset_from_file_uses_path_stem() -> None:
    asset = AudioClipAsset.from_file("/tmp/impact.wav")

    assert asset.name == "impact"
    assert asset.source_path == Path("/tmp/impact.wav")


def test_audio_clip_asset_declares_canonical_native_resource() -> None:
    asset = AudioClipAsset(name="impact", uuid="audio-uuid")

    resource_manager = FakeResourceManager()
    resource_manager.register_runtime_asset("audio_clip", asset.name, asset, uuid=asset.uuid)

    by_uuid = TcAudioClip.from_uuid("audio-uuid")

    assert by_uuid.is_valid
    assert by_uuid.uuid == asset.uuid
    assert by_uuid.name == asset.name
    assert by_uuid.serialize() == {
        "type": "uuid",
        "uuid": "audio-uuid",
        "name": "impact",
    }


def test_audio_clip_asset_decodes_wav_into_native_pcm(tmp_path: Path) -> None:
    path = tmp_path / "impulse.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8_000)
        output.writeframes(struct.pack("<4h", 0, 12_000, -12_000, 0))

    asset = AudioClipAsset.from_file(path, uuid="audio-wav-decode")

    assert asset.ensure_loaded()
    assert asset.clip.is_loaded
    assert asset.clip.sample_rate == 8_000
    assert asset.clip.channels == 1
    assert asset.clip.frame_count == 4


def test_audio_clip_plugins_register_with_asset_registry() -> None:
    registry = AssetTypeRegistry()

    register_audio_clip_import_plugin(registry)
    register_audio_clip_runtime_plugin(registry)

    assert registry.get_import("audio_clip") is not None
    assert registry.get_runtime("audio_clip") is not None
    assert registry.get_for_extension(".WAV")[0].type_id == "audio_clip"
    assert registry.get_for_extension(".ogg") == []


def test_audio_clip_runtime_plugin_registers_lazy_asset() -> None:
    resource_manager = FakeResourceManager()
    result = PreLoadResult(
        resource_type="audio_clip",
        path="/tmp/impact.wav",
        uuid="audio-uuid",
    )

    create_runtime_plugin().register(
        AssetContext(resource_manager=resource_manager, name="impact", uuid="audio-uuid"),
        result,
    )

    asset = resource_manager.get_audio_clip_asset("impact")
    assert isinstance(asset, AudioClipAsset)
    assert asset.uuid == "audio-uuid"
    assert asset.source_path == Path("/tmp/impact.wav")


def test_audio_clip_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "audio_clip"
    assert create_runtime_plugin().type_id == "audio_clip"
