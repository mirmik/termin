from types import SimpleNamespace

import numpy as np

from termin.editor_core.material_texture_sources import MaterialTextureSourceCatalog


class _Resources:
    def __init__(self):
        self.pixels = {
            "brick": np.array([[[128, 128, 128, 64]]], dtype=np.uint8),
            "normal_map": np.array([[[128, 128, 255, 64]]], dtype=np.uint8),
        }

    def list_texture_names(self):
        return ["__white_1x1__", "brick", "normal_map"]

    def get_texture_asset(self, name):
        class Asset:
            encoding = "srgb" if name == "brick" else "linear"

        return Asset() if name in {"brick", "normal_map"} else None

    def get_texture(self, name):
        pixels = self.pixels.get(name)
        return None if pixels is None else SimpleNamespace(_image_data=pixels)


class _RenderTarget:
    alive = True
    kind = "texture_2d"
    name = "MainRT"
    color_texture = object()
    depth_texture = object()

    def ensure_textures(self) -> None:
        pass


def test_material_texture_sources_merge_defaults_render_targets_and_files():
    target = _RenderTarget()
    catalog = MaterialTextureSourceCatalog(
        _Resources(),
        render_target_pool=lambda: (target,),
    )

    choices = catalog.choices("normal", expected_encoding="srgb")

    assert [(choice.tag, choice.name) for choice in choices] == [
        ("default", ""),
        ("rt_color", "MainRT"),
        ("rt_depth", "MainRT"),
        ("file", "brick"),
        ("file", "normal_map"),
    ]
    assert catalog.resolve_render_target("MainRT", "color") is target.color_texture
    assert catalog.resolve_render_target("MainRT", "depth") is target.depth_texture


def test_material_texture_file_previews_use_actual_asset_encoding():
    resources = _Resources()
    catalog = MaterialTextureSourceCatalog(resources, render_target_pool=tuple)

    srgb_preview = catalog.preview_pixels("file", "brick", "white", "linear")
    linear_preview = catalog.preview_pixels("file", "normal_map", "normal", "srgb")

    assert srgb_preview is resources.pixels["brick"]
    np.testing.assert_array_equal(
        linear_preview,
        np.array([[[188, 188, 255, 64]]], dtype=np.uint8),
    )
    np.testing.assert_array_equal(
        resources.pixels["normal_map"],
        np.array([[[128, 128, 255, 64]]], dtype=np.uint8),
    )
