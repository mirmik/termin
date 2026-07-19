from termin_assets import AssetContext, PreLoadResult
from termin.default_assets.render.texture_asset import TextureAsset
from termin.default_assets.render.texture_plugin import create_runtime_plugin


class FakeResourceManager:
    def __init__(self) -> None:
        self.by_name = {}
        self.by_uuid = {}

    def get_runtime_asset(self, type_id: str, name: str):
        return self.by_name.get((type_id, name))

    def get_runtime_asset_by_uuid(self, type_id: str, uuid: str):
        return self.by_uuid.get((type_id, uuid))


class FakeLoadedTextureAsset:
    is_loaded = True

    def __init__(self) -> None:
        self.parsed_spec = None
        self.reload_count = 0

    def should_reload_from_file(self) -> bool:
        return True

    def parse_spec(self, spec_data) -> None:
        self.parsed_spec = spec_data

    def reload(self) -> None:
        self.reload_count += 1


def test_texture_asset_does_not_expose_gpu_lifecycle_api() -> None:
    asset = TextureAsset(name="albedo")

    assert not hasattr(asset, "delete_gpu")


def test_texture_runtime_reload_stays_in_asset_layer() -> None:
    resource_manager = FakeResourceManager()
    asset = FakeLoadedTextureAsset()
    resource_manager.by_uuid[("texture", "texture-uuid")] = asset
    result = PreLoadResult(
        resource_type="texture",
        path="/tmp/albedo.png",
        uuid="texture-uuid",
        spec_data={"flip_y": False},
    )

    create_runtime_plugin().reload(
        AssetContext(resource_manager=resource_manager, name="albedo", uuid="texture-uuid"),
        result,
    )

    assert asset.parsed_spec == {"flip_y": False}
    assert asset.reload_count == 1
