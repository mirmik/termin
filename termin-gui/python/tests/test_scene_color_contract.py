from __future__ import annotations

from tcgui.scene.item import RectItem
from tcgui.scene.widget import SceneView
from termin.geombase import SrgbColor


def test_scene_panel_defaults_use_authored_srgb_colors():
    view = SceneView()
    item = RectItem("sample")

    assert isinstance(view.background_color, SrgbColor)
    assert isinstance(view.grid_color, SrgbColor)
    assert isinstance(view.grid_axis_color, SrgbColor)
    assert isinstance(item.fill_color, SrgbColor)
    assert isinstance(item.border_color, SrgbColor)
    assert isinstance(item.text_color, SrgbColor)
