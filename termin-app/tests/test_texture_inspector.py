from PIL import Image

from termin.assets.resources import ResourceManager
from termin.editor_tcgui.texture_inspector import TextureInspectorTcgui
from termin.loaders.texture_spec import TextureSpec


def test_texture_inspector_opens_unregistered_texture_file(tmp_path):
    texture_path = tmp_path / "preview.png"
    Image.new("RGBA", (2, 3), (20, 40, 60, 255)).save(texture_path)
    TextureSpec(flip_x=True, flip_y=False, transpose=True).save_for_texture(texture_path)

    inspector = TextureInspectorTcgui(ResourceManager())
    inspector.set_texture_by_path(str(texture_path))

    assert inspector._res_v.text == "2 x 3"
    assert inspector._channels_v.text == "4"
    assert inspector._flip_x.checked is True
    assert inspector._flip_y.checked is False
    assert inspector._transpose.checked is True
