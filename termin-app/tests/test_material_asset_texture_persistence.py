import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from termin.assets.material_asset import _parse_material_content, _save_material_file
from termin.assets.resources import ResourceManager
from termin.assets.shader_asset import ShaderAsset
from termin.render.texture_asset import TextureAsset
from tgfx import TcTexture


def _stdlib_root() -> Path:
    return Path(__file__).resolve().parents[1] / "termin" / "resources" / "stdlib"


def _register_stdlib_shader(rm: ResourceManager, name: str) -> None:
    shader_path = _stdlib_root() / "shaders" / f"{name}.shader"
    shader_asset = ShaderAsset.from_file(shader_path, name=name)
    assert shader_asset.program is not None
    rm.register_shader(
        name,
        shader_asset.program,
        source_path=str(shader_path),
        uuid=shader_asset.uuid,
    )


def test_material_save_matches_texture_asset_by_uuid_without_loaded_asset_data(tmp_path) -> None:
    ResourceManager._reset_for_testing()
    rm = ResourceManager.instance()
    _register_stdlib_shader(rm, "CookTorrancePBR")

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

    material, _uuid = _parse_material_content(
        (_stdlib_root() / "materials" / "CookTorrancePBR.material").read_text(encoding="utf-8"),
        name="CookTorrancePBR",
        source_path=str(_stdlib_root() / "materials" / "CookTorrancePBR.material"),
    )
    material = material.copy("")
    assert material.set_texture("u_albedo_texture", texture) > 0

    material_path = tmp_path / "saved.material"
    _save_material_file(material, material_path, uuid="material-save-uuid")

    data = json.loads(material_path.read_text(encoding="utf-8"))
    assert data["textures"]["u_albedo_texture"] == texture_uuid


def test_material_load_resolves_texture_uuid_with_lazy_loaded_texture_asset(tmp_path) -> None:
    ResourceManager._reset_for_testing()
    rm = ResourceManager.instance()
    _register_stdlib_shader(rm, "CookTorrancePBR")

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


def test_builtin_registration_does_not_shadow_stdlib_materials() -> None:
    ResourceManager._reset_for_testing()
    rm = ResourceManager.instance()

    rm.register_builtin_materials()

    stdlib_materials = {
        path.stem
        for path in (_stdlib_root() / "materials").glob("*.material")
    }
    assert stdlib_materials.isdisjoint(rm.materials)


def test_builtin_registration_does_not_shadow_stdlib_shaders() -> None:
    from termin.assets.builtin_resources import register_builtin_shaders

    ResourceManager._reset_for_testing()
    rm = ResourceManager.instance()

    register_builtin_shaders(rm)

    stdlib_shaders = {
        path.stem
        for path in (_stdlib_root() / "shaders").glob("*.shader")
    }
    assert stdlib_shaders.isdisjoint(rm.shaders)
    assert "DefaultShader" not in rm.shaders
    assert "SkinnedShader" not in rm.shaders


def test_stdlib_normalized_pbr_applies_material_uniform_override() -> None:
    ResourceManager._reset_for_testing()
    rm = ResourceManager.instance()
    _register_stdlib_shader(rm, "CookTorrancePBR")

    material, _uuid = _parse_material_content(
        (_stdlib_root() / "materials" / "NormalizedPBR.material").read_text(encoding="utf-8"),
        name="NormalizedPBR",
        source_path=str(_stdlib_root() / "materials" / "NormalizedPBR.material"),
    )

    assert material.default_phase().uniforms["u_diffuse_mul"] == pytest.approx(3.14)
