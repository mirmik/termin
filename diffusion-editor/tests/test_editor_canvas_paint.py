import numpy as np

from tcbase import MouseButton

from diffusion_editor.editor_canvas import EditorCanvas
from diffusion_editor.layer_stack import LayerStack


def test_paint_updates_layer_before_mouse_up():
    image = np.zeros((32, 32, 4), dtype=np.uint8)
    stack = LayerStack(tile_size=16)
    stack.init_from_image(image)
    canvas = EditorCanvas(stack, gpu_compositing=False)
    canvas._update_composite()
    canvas.brush.set_size(5)
    canvas.brush.set_hardness(1.0)
    canvas.brush.set_color(255, 0, 0, 255)

    canvas._handle_mouse_down(8, 8, MouseButton.LEFT)
    assert stack.active_layer.image[8, 8, 3] > 0

    canvas._handle_mouse_move(16, 8)
    assert stack.active_layer.image[8, 16, 3] > 0

    canvas._handle_mouse_up(16, 8)
    assert canvas._stroke_mask is None
