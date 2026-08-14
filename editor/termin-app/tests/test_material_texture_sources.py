from types import SimpleNamespace

import numpy as np

from termin.editor_core.material_texture_sources import MaterialTextureSourceCatalog


class _Resources:
    def __init__(self):
        self.pixels = {
            "brick": np.array([[[128, 128, 128, 64]]], dtype=np.uint8),
            "normal_map": np.array([[[128, 128, 255, 64]]], dtype=np.uint8),
        }
        self.assets = tuple(
            SimpleNamespace(
                name=name,
                uuid=uuid,
                encoding=encoding,
                texture_data=SimpleNamespace(
                    is_valid=True,
                    data=self.pixels[name],
                    sync_to_cpu=lambda: None,
                ),
            )
            for name, uuid, encoding in (
                ("brick", "brick-uuid", "srgb"),
                ("normal_map", "normal-uuid", "linear"),
            )
        )

    def iter_runtime_assets(self, type_id):
        assert type_id == "texture"
        return self.assets

    def get_texture_asset_by_uuid(self, uuid):
        return next((asset for asset in self.assets if asset.uuid == uuid), None)


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

    assert [(choice.tag, choice.identifier) for choice in choices] == [
        ("default", ""),
        ("rt_color", "MainRT"),
        ("rt_depth", "MainRT"),
        ("file", "brick-uuid"),
        ("file", "normal-uuid"),
    ]
    assert catalog.resolve_render_target("MainRT", "color") is target.color_texture
    assert catalog.resolve_render_target("MainRT", "depth") is target.depth_texture


def test_material_texture_file_previews_use_actual_asset_encoding():
    resources = _Resources()
    catalog = MaterialTextureSourceCatalog(resources, render_target_pool=tuple)

    srgb_preview = catalog.preview_pixels("file", "brick-uuid", "white", "linear")
    linear_preview = catalog.preview_pixels("file", "normal-uuid", "normal", "srgb")

    assert srgb_preview is resources.pixels["brick"]
    np.testing.assert_array_equal(
        linear_preview,
        np.array([[[188, 188, 255, 64]]], dtype=np.uint8),
    )
    np.testing.assert_array_equal(
        resources.pixels["normal_map"],
        np.array([[[128, 128, 255, 64]]], dtype=np.uint8),
    )


def test_material_texture_sources_keep_duplicate_names_distinct_by_uuid():
    resources = _Resources()
    duplicate_pixels = np.array([[[255, 0, 0, 255]]], dtype=np.uint8)
    resources.assets += (
        SimpleNamespace(
            name="brick",
            uuid="other-brick-uuid",
            encoding="srgb",
            texture_data=SimpleNamespace(
                is_valid=True,
                data=duplicate_pixels,
                sync_to_cpu=lambda: None,
            ),
        ),
    )
    catalog = MaterialTextureSourceCatalog(resources, render_target_pool=tuple)

    choices = catalog.choices()

    brick_choices = [choice for choice in choices if choice.tag == "file" and choice.label.startswith("brick")]
    assert [(choice.label, choice.identifier) for choice in brick_choices] == [
        ("brick [brick-uu]", "brick-uuid"),
        ("brick [other-br]", "other-brick-uuid"),
    ]
    np.testing.assert_array_equal(
        catalog.preview_pixels("file", "other-brick-uuid", "white", "srgb"),
        duplicate_pixels,
    )
