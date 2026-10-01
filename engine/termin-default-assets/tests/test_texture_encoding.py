import json
import uuid
from pathlib import Path

import numpy as np
import pytest
from termin.graphics import TcTexture, TextureAddress, TextureEncoding, TextureFilter
from termin.image import write_png_rgba8_file

from termin.default_assets.render.texture_asset import TextureAsset
from termin.default_assets.render.texture_spec import TextureSpec


def test_texture_spec_defaults_ordinary_images_to_srgb(tmp_path: Path) -> None:
    assert TextureSpec.load(tmp_path / "missing.png.meta").encoding == "srgb"


def test_texture_spec_round_trips_encoding_and_removes_obsolete_field(
    tmp_path: Path,
) -> None:
    path = tmp_path / "normal.png.meta"
    path.write_text(
        json.dumps({"uuid": "normal-uuid", "color_space": "srgb"}),
        encoding="utf-8",
    )

    TextureSpec(encoding="linear").save(path, preserve_existing=True)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["uuid"] == "normal-uuid"
    assert saved["encoding"] == "linear"
    assert "color_space" not in saved


def test_texture_spec_rejects_obsolete_and_unknown_encodings(tmp_path: Path) -> None:
    obsolete = tmp_path / "obsolete.meta"
    obsolete.write_text(json.dumps({"color_space": "srgb"}), encoding="utf-8")
    with pytest.raises(ValueError, match="obsolete"):
        TextureSpec.load(obsolete)

    invalid = tmp_path / "invalid.meta"
    invalid.write_text(json.dumps({"encoding": "display-p3"}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported texture encoding"):
        TextureSpec.load(invalid)


def test_procedural_texture_encoding_is_explicit_and_part_of_identity() -> None:
    pixels = np.array([[[64, 128, 192, 255]]], dtype=np.uint8)

    srgb = TextureAsset.from_data(pixels, encoding="srgb", name="encoded-srgb")
    linear = TextureAsset.from_data(pixels, encoding="linear", name="encoded-linear")

    assert srgb.encoding == "srgb"
    assert linear.encoding == "linear"
    assert srgb.texture_data.encoding == TextureEncoding.SRGB
    assert linear.texture_data.encoding == TextureEncoding.LINEAR
    assert srgb.uuid != linear.uuid


def test_procedural_texture_requires_encoding() -> None:
    pixels = np.array([[[255, 255, 255, 255]]], dtype=np.uint8)
    with pytest.raises(TypeError, match="encoding"):
        TextureAsset.from_data(pixels)


def test_texture_sampler_round_trip_preserves_image_version() -> None:
    pixels = np.array([[[10, 20, 30, 255], [40, 50, 60, 255]]], dtype=np.uint8)
    texture = TcTexture.from_data(pixels, 2, 1, 4)
    version = texture.version
    assert texture.min_filter == TextureFilter.LINEAR
    assert texture.mag_filter == TextureFilter.LINEAR
    assert texture.mip_filter == TextureFilter.LINEAR
    assert not texture.clamp
    assert not texture.mipmap

    assert texture.set_filters(TextureFilter.NEAREST, TextureFilter.LINEAR, TextureFilter.NEAREST)
    texture.set_clamp(True)
    assert texture.min_filter == TextureFilter.NEAREST
    assert texture.mag_filter == TextureFilter.LINEAR
    assert texture.mip_filter == TextureFilter.NEAREST
    assert texture.clamp
    assert texture.version == version

    texture.set_clamp(False)
    assert not texture.clamp
    assert texture.min_filter == TextureFilter.NEAREST
    assert texture.mag_filter == TextureFilter.LINEAR
    assert texture.mip_filter == TextureFilter.NEAREST
    assert texture.version == version
    with pytest.raises(TypeError):
        texture.set_filters("nearest", TextureFilter.LINEAR, TextureFilter.NEAREST)
    assert texture.version == version
    assert texture.min_filter == TextureFilter.NEAREST

    texture.set_mipmap(True)
    assert texture.mipmap
    assert texture.version == version + 1
    texture.set_mipmap(True)
    assert texture.version == version + 1
    texture.set_mipmap(False)
    assert not texture.mipmap
    assert texture.version == version + 2
    np.testing.assert_array_equal(texture.data, pixels)


@pytest.mark.parametrize(
    "u,v,w",
    [
        (TextureAddress.MIRRORED_REPEAT, TextureAddress.REPEAT, TextureAddress.CLAMP_TO_EDGE),
        (TextureAddress.CLAMP_TO_EDGE, TextureAddress.MIRRORED_REPEAT, TextureAddress.CLAMP_TO_BORDER),
        (TextureAddress.CLAMP_TO_BORDER, TextureAddress.CLAMP_TO_EDGE, TextureAddress.REPEAT),
        (TextureAddress.REPEAT, TextureAddress.CLAMP_TO_BORDER, TextureAddress.MIRRORED_REPEAT),
    ],
)
def test_texture_addressing_round_trips_independent_axes_without_changing_image_version(
    u: TextureAddress, v: TextureAddress, w: TextureAddress
) -> None:
    pixels = np.array([[[45, 65, 85, 255]]], dtype=np.uint8)
    texture = TcTexture.from_data(pixels, 1, 1, 4)
    assert texture.set_filters(TextureFilter.NEAREST, TextureFilter.LINEAR, TextureFilter.NEAREST)
    version = texture.version
    assert texture.set_wraps(u, v, w)
    assert (texture.address_u, texture.address_v, texture.address_w) == (u, v, w)
    assert not texture.clamp
    assert texture.version == version
    assert texture.min_filter == TextureFilter.NEAREST
    assert texture.mag_filter == TextureFilter.LINEAR
    assert texture.mip_filter == TextureFilter.NEAREST

    with pytest.raises(TypeError):
        texture.set_wraps(TextureAddress.REPEAT, "mirrored_repeat", TextureAddress.REPEAT)
    assert (texture.address_u, texture.address_v, texture.address_w) == (u, v, w)
    assert texture.version == version

    texture.set_clamp(True)
    assert (texture.address_u, texture.address_v, texture.address_w) == (TextureAddress.CLAMP_TO_EDGE,) * 3
    assert texture.clamp
    texture.set_clamp(False)
    assert (texture.address_u, texture.address_v, texture.address_w) == (TextureAddress.REPEAT,) * 3
    assert not texture.clamp
    assert texture.min_filter == TextureFilter.NEAREST
    assert texture.mag_filter == TextureFilter.LINEAR
    assert texture.mip_filter == TextureFilter.NEAREST
    assert texture.version == version
    np.testing.assert_array_equal(texture.data, pixels)


@pytest.mark.parametrize(
    "initial_filter,initial_wrap,initial_mipmap,next_filter,next_wrap,next_mipmap",
    [
        ("nearest", "clamp", True, "linear", "repeat", False),
        ("linear", "repeat", False, "nearest", "clamp", True),
    ],
)
def test_texture_file_metadata_applies_sampler_on_initial_load_and_reload(
    tmp_path: Path,
    initial_filter: str,
    initial_wrap: str,
    initial_mipmap: bool,
    next_filter: str,
    next_wrap: str,
    next_mipmap: bool,
) -> None:
    path = tmp_path / "sampler.png"
    pixels = np.full((2, 2, 4), 127, dtype=np.uint8)
    write_png_rgba8_file(path, pixels)
    TextureSpec(filter=initial_filter, wrap=initial_wrap, mipmaps=initial_mipmap).save_for_texture(path)
    asset = TextureAsset.from_file(path, uuid=str(uuid.uuid4()))
    texture = asset.texture_data
    expected_filter = TextureFilter.NEAREST if initial_filter == "nearest" else TextureFilter.LINEAR
    assert texture.min_filter == expected_filter
    assert texture.mag_filter == expected_filter
    assert texture.mip_filter == expected_filter
    assert texture.clamp == (initial_wrap == "clamp")
    assert texture.mipmap == initial_mipmap

    assert asset.reload_with_spec(
        {"filter": next_filter, "wrap": next_wrap, "mipmaps": next_mipmap}
    )
    reloaded = asset.texture_data
    assert reloaded.uuid == texture.uuid
    expected_filter = TextureFilter.NEAREST if next_filter == "nearest" else TextureFilter.LINEAR
    for handle in (texture, reloaded):
        assert handle.min_filter == expected_filter
        assert handle.mag_filter == expected_filter
        assert handle.mip_filter == expected_filter
        assert handle.clamp == (next_wrap == "clamp")
        assert handle.mipmap == next_mipmap
        np.testing.assert_array_equal(handle.data, pixels)
    assert asset.filter == next_filter
    assert asset.wrap == next_wrap
    assert asset.mipmaps == next_mipmap

    with pytest.raises(ValueError, match="Unsupported texture filter"):
        asset.reload_with_spec({"filter": "cubic"})
    assert asset.filter == next_filter
    assert asset.wrap == next_wrap
    assert asset.mipmaps == next_mipmap
    assert reloaded.min_filter == expected_filter
    assert reloaded.clamp == (next_wrap == "clamp")
    assert reloaded.mipmap == next_mipmap


@pytest.mark.parametrize("field,value", [("filter", "cubic"), ("wrap", "mirror")])
def test_texture_file_rejects_unsupported_sampler_metadata(
    tmp_path: Path, field: str, value: str
) -> None:
    path = tmp_path / "invalid-sampler.png"
    write_png_rgba8_file(path, np.full((1, 1, 4), 255, dtype=np.uint8))
    Path(str(path) + ".meta").write_text(json.dumps({field: value}), encoding="utf-8")
    with pytest.raises(ValueError, match=f"Unsupported texture {field}"):
        TextureAsset.from_file(path)


def test_procedural_texture_sampler_matches_asset_defaults() -> None:
    asset = TextureAsset.from_data(np.full((1, 1, 4), 255, dtype=np.uint8), encoding="linear")
    texture = asset.texture_data
    assert asset.filter == "linear"
    assert texture.min_filter == TextureFilter.LINEAR
    assert texture.mag_filter == TextureFilter.LINEAR
    assert texture.mip_filter == TextureFilter.LINEAR
    assert asset.wrap == "clamp"
    assert texture.clamp
    assert not asset.mipmaps
    assert not texture.mipmap
