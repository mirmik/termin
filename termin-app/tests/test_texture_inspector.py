import numpy as np

from termin.image import write_png_rgba8_file
from termin.editor_core.resource_manager import ResourceManager
from termin.editor_tcgui.texture_inspector import TextureInspectorTcgui
from termin.default_assets.render.texture_spec import TextureSpec


def test_texture_inspector_opens_unregistered_texture_file(tmp_path):
    texture_path = tmp_path / "preview.png"
    pixels = np.zeros((3, 2, 4), dtype=np.uint8)
    pixels[:, :, 0] = 20
    pixels[:, :, 1] = 40
    pixels[:, :, 2] = 60
    pixels[:, :, 3] = 255
    write_png_rgba8_file(texture_path, pixels)
    TextureSpec(flip_x=True, flip_y=False, transpose=True).save_for_texture(texture_path)

    inspector = TextureInspectorTcgui(ResourceManager())
    inspector.set_texture_by_path(str(texture_path))

    assert inspector._res_v.text == "2 x 3"
    assert inspector._channels_v.text == "4"
    assert inspector._flip_x.checked is True
    assert inspector._flip_y.checked is False
    assert inspector._transpose.checked is True
