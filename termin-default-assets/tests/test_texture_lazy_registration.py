from pathlib import Path

import numpy as np
from PIL import Image

from termin.default_assets.resource_manager import DefaultResourceManager
from termin_assets import PreLoadResult
from tgfx import TcTexture, tc_texture_ensure_loaded, tc_texture_is_loaded


def test_texture_file_registration_declares_lazy_core_texture(tmp_path: Path) -> None:
    texture_path = tmp_path / "Grenade.png"
    pixels = np.zeros((2, 2, 4), dtype=np.uint8)
    pixels[:, :, 0] = 255
    pixels[:, :, 3] = 255
    Image.fromarray(pixels, "RGBA").save(texture_path)

    rm = DefaultResourceManager()
    try:
        result = PreLoadResult(
            resource_type="texture",
            path=str(texture_path),
            content=None,
            uuid="lazy-texture-uuid",
            spec_data={"uuid": "lazy-texture-uuid"},
        )

        rm.register_file(result)

        asset = rm.get_texture_asset_by_uuid("lazy-texture-uuid")
        assert asset is not None
        assert not asset.is_loaded

        texture = TcTexture.from_uuid("lazy-texture-uuid")
        assert texture.is_valid
        assert not tc_texture_is_loaded(texture)

        assert tc_texture_ensure_loaded(texture)

        loaded = TcTexture.from_uuid("lazy-texture-uuid")
        assert loaded.is_valid
        assert loaded.width == 2
        assert loaded.height == 2
        assert tc_texture_is_loaded(loaded)
        assert asset.is_loaded
    finally:
        rm.clear_runtime_state()
