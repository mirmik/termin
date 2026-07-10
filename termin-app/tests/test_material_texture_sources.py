from termin.editor_core.material_texture_sources import MaterialTextureSourceCatalog


class _Resources:
    def list_texture_names(self):
        return ["__white_1x1__", "brick", "normal_map"]


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

    choices = catalog.choices("normal")

    assert [(choice.tag, choice.name) for choice in choices] == [
        ("default", ""),
        ("rt_color", "MainRT"),
        ("rt_depth", "MainRT"),
        ("file", "brick"),
        ("file", "normal_map"),
    ]
    assert catalog.resolve_render_target("MainRT", "color") is target.color_texture
    assert catalog.resolve_render_target("MainRT", "depth") is target.depth_texture
