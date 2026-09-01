import json
from pathlib import Path

import numpy as np
import pytest
from termin.graphics import TextureEncoding

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
