import json
import numpy as np
import pytest

from termin.image import write_png_rgba8_file
from termin.materials import SurfaceContractRegistry
from termin.default_assets.render.material_asset import (
    _apply_canonical_texture_defaults,
    _parse_material_content,
    _save_material_file,
)
from termin.default_assets.resource_manager import DefaultResourceManager
from termin.default_assets.render.shader_asset import ShaderAsset
from termin.default_assets.render.texture_asset import TextureAsset
from termin.stdlib import stdlib_root
from tgfx import TcTexture, TextureEncoding


def _register_stdlib_shader(rm: DefaultResourceManager, name: str) -> None:
    assert SurfaceContractRegistry.register_builtins()
    shader_path = stdlib_root() / "shaders" / f"{name}.shader"
    shader_asset = ShaderAsset.from_file(shader_path, name=name)
    assert shader_asset.program is not None
    rm.register_shader_asset(name, shader_asset, source_path=str(shader_path))


def test_unconstrained_texture_default_keeps_its_native_encoding() -> None:
    class PhaseProbe:
        def __init__(self) -> None:
            self.declarations = []
            self.textures = {}

        def declare_texture(self, name, expected_encoding) -> None:
            self.declarations.append((name, expected_encoding))

        def set_texture(self, name, texture) -> bool:
            self.textures[name] = texture
            return True

    phase = PhaseProbe()

    _apply_canonical_texture_defaults(
        phase,
        [
            {
                "name": "u_input",
                "property_type": "Texture",
                "default": "white",
                "expected_encoding": None,
            }
        ],
    )

    assert phase.declarations == [("u_input", None)]
    assert phase.textures["u_input"].encoding == TextureEncoding.LINEAR


def test_material_save_matches_texture_asset_by_uuid_without_loaded_asset_data(tmp_path) -> None:
    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()
    _register_stdlib_shader(rm, "CookTorrancePBR")

    texture_uuid = "texture-save-uuid"
    texture = TcTexture.from_data(
        data=np.full((1, 1, 4), 255, dtype=np.uint8),
        width=1,
        height=1,
        channels=4,
        name="SavedTexture",
        uuid=texture_uuid,
        encoding=TextureEncoding.SRGB,
    )
    texture_asset = TextureAsset(texture_data=None, name="SavedTexture", uuid=texture_uuid)
    rm.register_texture_asset("SavedTexture", texture_asset, uuid=texture_uuid)

    material, _uuid = _parse_material_content(
        (stdlib_root() / "materials" / "CookTorrancePBR.material").read_text(encoding="utf-8"),
        name="CookTorrancePBR",
        source_path=str(stdlib_root() / "materials" / "CookTorrancePBR.material"),
    )
    material = material.copy("")
    assert material.set_texture("u_albedo_texture", texture) > 0

    material_path = tmp_path / "saved.material"
    _save_material_file(material, material_path, uuid="material-save-uuid")

    data = json.loads(material_path.read_text(encoding="utf-8"))
    assert data["textures"]["u_albedo_texture"] == texture_uuid


def test_material_load_resolves_texture_uuid_with_lazy_loaded_texture_asset(tmp_path) -> None:
    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()
    _register_stdlib_shader(rm, "CookTorrancePBR")

    texture_uuid = "texture-load-uuid"
    texture_path = tmp_path / "albedo.png"
    write_png_rgba8_file(texture_path, np.full((1, 1, 4), 255, dtype=np.uint8))

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


def test_material_texture_assignment_binds_encoding_mismatch() -> None:
    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()
    _register_stdlib_shader(rm, "CookTorrancePBR")

    material, _uuid = _parse_material_content(
        (stdlib_root() / "materials" / "CookTorrancePBR.material").read_text(
            encoding="utf-8"
        ),
        name="CookTorrancePBR",
    )
    linear = TcTexture.from_data(
        data=np.full((1, 1, 4), 255, dtype=np.uint8),
        width=1,
        height=1,
        channels=4,
        name="LinearData",
        encoding=TextureEncoding.LINEAR,
    )

    assert material.set_texture("u_albedo_texture", linear) > 0
    assert material.textures["u_albedo_texture"].uuid == linear.uuid


def test_material_load_binds_texture_encoding_mismatch() -> None:
    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()
    _register_stdlib_shader(rm, "CookTorrancePBR")

    texture_uuid = "linear-albedo-uuid"
    linear = TcTexture.from_data(
        data=np.full((1, 1, 4), 255, dtype=np.uint8),
        width=1,
        height=1,
        channels=4,
        name="LinearAlbedo",
        uuid=texture_uuid,
        encoding=TextureEncoding.LINEAR,
    )
    rm.register_texture_asset(
        "LinearAlbedo",
        TextureAsset(
            texture_data=linear,
            name="LinearAlbedo",
            uuid=texture_uuid,
            encoding="linear",
        ),
        uuid=texture_uuid,
    )

    material, _uuid = _parse_material_content(
        json.dumps(
            {
                "uuid": "material-mismatch",
                "shader": "CookTorrancePBR",
                "textures": {"u_albedo_texture": texture_uuid},
            }
        ),
        name="Mismatch",
    )

    assert material.textures["u_albedo_texture"].uuid == texture_uuid


def test_builtin_registration_does_not_shadow_stdlib_materials() -> None:
    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()

    rm.register_builtin_materials()

    stdlib_materials = {
        path.stem
        for path in (stdlib_root() / "materials").glob("*.material")
    }
    assert stdlib_materials.isdisjoint(rm.list_material_names())


def test_builtin_registration_does_not_shadow_stdlib_shaders() -> None:
    from termin.default_assets.builtin_resources import register_builtin_shaders

    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()

    register_builtin_shaders(rm)

    stdlib_shaders = {
        path.stem
        for path in (stdlib_root() / "shaders").glob("*.shader")
    }
    assert stdlib_shaders.isdisjoint(rm.list_shader_names())
    assert "DefaultShader" not in rm.list_shader_names()
    assert "SkinnedShader" not in rm.list_shader_names()


def test_stdlib_normalized_pbr_applies_material_uniform_override() -> None:
    DefaultResourceManager._reset_for_testing()
    rm = DefaultResourceManager.instance()
    _register_stdlib_shader(rm, "CookTorrancePBRSubsurface")

    material, _uuid = _parse_material_content(
        (stdlib_root() / "materials" / "NormalizedPBR.material").read_text(encoding="utf-8"),
        name="NormalizedPBR",
        source_path=str(stdlib_root() / "materials" / "NormalizedPBR.material"),
    )

    assert material.default_phase().uniforms["u_diffuse_mul"] == pytest.approx(3.14)
    assert material.default_phase().shader.name.startswith(
        "CookTorrancePBRSubsurface/"
    )
