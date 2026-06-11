import json

import numpy as np
from PIL import Image

from termin.assets.material_asset import _parse_material_content, _save_material_file
from termin.assets.resources import ResourceManager
from termin.assets.texture_asset import TextureAsset
from tgfx import TcTexture


def test_material_save_matches_texture_asset_by_uuid_without_loaded_asset_data(tmp_path) -> None:
    ResourceManager._reset_for_testing()
    rm = ResourceManager.instance()

    texture_uuid = "texture-save-uuid"
    texture = TcTexture.from_data(
        data=np.full((1, 1, 4), 255, dtype=np.uint8),
        width=1,
        height=1,
        channels=4,
        name="SavedTexture",
        uuid=texture_uuid,
    )
    texture_asset = TextureAsset(texture_data=None, name="SavedTexture", uuid=texture_uuid)
    rm.register_texture_asset("SavedTexture", texture_asset, uuid=texture_uuid)

    material = rm.get_material("PBRMaterial").copy("")
    assert material.set_texture("u_albedo_texture", texture) > 0

    material_path = tmp_path / "saved.material"
    _save_material_file(material, material_path, uuid="material-save-uuid")

    data = json.loads(material_path.read_text(encoding="utf-8"))
    assert data["textures"]["u_albedo_texture"] == texture_uuid


def test_material_load_resolves_texture_uuid_with_lazy_loaded_texture_asset(tmp_path) -> None:
    ResourceManager._reset_for_testing()
    rm = ResourceManager.instance()

    texture_uuid = "texture-load-uuid"
    texture_path = tmp_path / "albedo.png"
    Image.fromarray(np.full((1, 1, 4), 255, dtype=np.uint8), mode="RGBA").save(texture_path)

    texture_asset = TextureAsset(
        texture_data=None,
        name="Albedo",
        source_path=texture_path,
        uuid=texture_uuid,
    )
    rm.register_texture_asset("Albedo", texture_asset, source_path=str(texture_path), uuid=texture_uuid)

    material_data = {
        "uuid": "material-load-uuid",
        "shader": "CookTorrancePBR",
        "textures": {"u_albedo_texture": texture_uuid},
    }

    material, _uuid = _parse_material_content(
        json.dumps(material_data),
        name="LoadedMaterial",
        source_path=str(tmp_path / "loaded.material"),
    )

    texture = material.textures["u_albedo_texture"]
    assert texture.is_valid
    assert texture.uuid == texture_uuid
