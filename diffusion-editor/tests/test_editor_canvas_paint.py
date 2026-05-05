import numpy as np

from tcbase import MouseButton

from diffusion_editor.editor_canvas import EditorCanvas
from diffusion_editor.layer_stack import LayerStack
from diffusion_editor.brush import BrushToolMode


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


def test_smudge_interpolates_fast_mouse_move():
    image = np.zeros((40, 40, 4), dtype=np.uint8)
    image[:, :, 3] = 255
    image[17:23, 5:11, :3] = (255, 0, 0)
    stack = LayerStack(tile_size=16)
    stack.init_from_image(image)
    canvas = EditorCanvas(stack, gpu_compositing=False)
    canvas._update_composite()
    canvas.set_brush_tool(BrushToolMode.SMUDGE)
    canvas.brush.set_size(6)
    canvas.brush.set_hardness(1.0)
    canvas.brush.set_flow(1.0)
    canvas.brush.set_color(255, 255, 255, 255)

    canvas._handle_mouse_down(8, 20, MouseButton.LEFT)
    canvas._handle_mouse_move(32, 20)

    assert stack.active_layer.image[20, 20, 0] > 0
    assert stack.active_layer.image[20, 32, 0] > 0

    before_up = stack.active_layer.image.copy()
    canvas._handle_mouse_up(32, 20)
    np.testing.assert_array_equal(stack.active_layer.image, before_up)
    assert canvas._smudge_buffer is None


def test_mask_paint_updates_overlay_before_mouse_up():
    image = np.zeros((32, 32, 4), dtype=np.uint8)
    stack = LayerStack(tile_size=16)
    stack.init_from_image(image)
    canvas = EditorCanvas(stack, gpu_compositing=False)
    canvas._update_composite()
    canvas.set_brush_tool(BrushToolMode.MASK)
    canvas.set_show_mask(True)
    canvas.set_mask_brush(5, 1.0, 1.0)

    canvas._handle_mouse_down(8, 8, MouseButton.LEFT)
    assert stack.active_layer.mask.data[8, 8] > 0.0
    assert canvas._overlay_data[8, 8, 3] > 0

    canvas._handle_mouse_move(16, 8)
    assert stack.active_layer.mask.data[8, 16] > 0.0
    assert canvas._overlay_data[8, 16, 3] > 0
