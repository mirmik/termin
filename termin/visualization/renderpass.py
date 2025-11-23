from dataclasses import dataclass
from termin.visualization.material import Material


@dataclass
class RenderState:
    """
    Полное состояние, никаких "None".
    Это "каким хочешь видеть рендер сейчас".
    """
    polygon_mode: str = "fill"     # fill / line
    cull: bool = True
    depth_test: bool = True
    depth_write: bool = True
    blend: bool = False
    blend_src: str = "src_alpha"
    blend_dst: str = "one_minus_src_alpha"


@dataclass
class RenderPass:
    material: Material
    state: RenderState = RenderState()
    phase: str = "main"
    name: str = "unnamed_pass"