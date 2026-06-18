from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult, set_resource_manager_factory
from termin.default_assets.audio.asset import AudioClipAsset
from termin.default_assets.audio.asset_plugin import (
    create_import_plugin,
    create_runtime_plugin,
    register_audio_clip_import_plugin,
    register_audio_clip_runtime_plugin,
)
from termin.default_assets.audio.handle import AudioClipHandle


class FakeAudioClip:
    duration = 2.5
    duration_ms = 2500
    is_valid = True


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
    assert str(asset.source_path) == "/tmp/impact.wav"


def test_audio_clip_handle_uses_configured_resource_manager_factory() -> None:
    asset = AudioClipAsset(name="impact", uuid="audio-uuid")
    asset._clip = FakeAudioClip()
    asset._loaded = True

    resource_manager = FakeResourceManager()
    resource_manager.register_runtime_asset("audio_clip", asset.name, asset, uuid=asset.uuid)

    set_resource_manager_factory(lambda: resource_manager)
    try:
        by_name = AudioClipHandle.from_name("impact")
        by_uuid = AudioClipHandle.from_uuid("audio-uuid")
    finally:
        set_resource_manager_factory(None)

    assert by_name.get_asset() is asset
    assert by_name.clip is asset.clip
    assert by_name.duration == 2.5
    assert by_name.duration_ms == 2500
    assert by_uuid.get_asset() is asset
    assert by_uuid.is_valid


def test_audio_clip_plugins_register_with_asset_registry() -> None:
    registry = AssetTypeRegistry()

    register_audio_clip_import_plugin(registry)
    register_audio_clip_runtime_plugin(registry)

    assert registry.get_import("audio_clip") is not None
    assert registry.get_runtime("audio_clip") is not None
    assert registry.get_for_extension(".WAV")[0].type_id == "audio_clip"


def test_audio_clip_runtime_plugin_registers_lazy_asset() -> None:
    resource_manager = FakeResourceManager()
    result = PreLoadResult(
        resource_type="audio_clip",
        path="/tmp/impact.wav",
        uuid="audio-uuid",
    )

    create_runtime_plugin().register(
        AssetContext(resource_manager=resource_manager, name="impact"),
        result,
    )

    asset = resource_manager.get_audio_clip_asset("impact")
    assert isinstance(asset, AudioClipAsset)
    assert asset.uuid == "audio-uuid"
    assert str(asset.source_path) == "/tmp/impact.wav"


def test_audio_clip_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "audio_clip"
    assert create_runtime_plugin().type_id == "audio_clip"
