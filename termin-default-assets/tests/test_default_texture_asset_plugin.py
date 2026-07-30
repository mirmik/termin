from pathlib import Path

import pytest

from termin_assets import AssetContext, PreLoadResult
from termin.default_assets.render.texture_asset import TextureAsset
from termin.default_assets.render.texture_plugin import (
    TextureImportPlugin,
    create_runtime_plugin,
)
from termin.image import SUPPORTED_RGBA8_EXTENSIONS


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
        self.reloaded_spec = None
        self.reload_count = 0

    def should_reload_from_file(self) -> bool:
        return True

    def reload_with_spec(self, spec_data) -> bool:
        self.reloaded_spec = spec_data
        self.reload_count += 1
        return True


class _DecodedTextureRecorder:
    def __init__(self, source_path: Path) -> None:
        self._source_path = source_path
        self._name = source_path.stem

    def _texture_from_decoded(self, decoded, source_path: str = ""):
        return decoded.format, source_path


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

    assert asset.reloaded_spec == {"flip_y": False}
    assert asset.reload_count == 1


def test_texture_import_plugin_uses_native_decoder_capabilities() -> None:
    assert TextureImportPlugin.extensions is SUPPORTED_RGBA8_EXTENSIONS
    assert TextureImportPlugin.extensions == {".jpeg", ".jpg", ".png", ".webp"}


@pytest.mark.parametrize(
    ("extension", "fixture_path", "expected_format"),
    [
        (".png", "termin-thirdparty/libjpeg-turbo/testimages/testorig.png", "png"),
        (".jpg", "termin-thirdparty/libjpeg-turbo/testimages/testorig.jpg", "jpeg"),
        (".jpeg", "termin-thirdparty/libjpeg-turbo/testimages/testorig.jpg", "jpeg"),
        (".webp", "termin-thirdparty/libwebp/examples/test.webp", "webp"),
    ],
)
def test_every_registered_texture_extension_decodes_through_asset_path(
    extension: str,
    fixture_path: str,
    expected_format: str,
) -> None:
    source = Path(__file__).resolve().parents[2] / fixture_path
    recorder = _DecodedTextureRecorder(source.with_suffix(extension))

    decoded_format, source_hint = TextureAsset._parse_content(
        recorder,
        source.read_bytes(),
    )

    assert extension in TextureImportPlugin.extensions
    assert decoded_format == expected_format
    assert source_hint.endswith(extension)
