import numpy as np

from tcbase import MouseButton, Mods

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


def test_move_tool_updates_cpu_composite_before_mouse_up():
    image = np.zeros((16, 16, 4), dtype=np.uint8)
    image[4, 4] = (255, 0, 0, 255)
    stack = LayerStack(tile_size=8)
    stack.init_from_image(image)
    canvas = EditorCanvas(stack, gpu_compositing=False)
    canvas._update_composite()
    canvas.set_brush_tool(BrushToolMode.MOVE)

    canvas._handle_mouse_down(4, 4, MouseButton.LEFT)
    canvas._handle_mouse_move(7, 5)

    assert stack.active_layer.image[5, 7, 3] == 255
    assert canvas._composite[5, 7, 3] == 255
    assert canvas._image_dirty is True


def test_move_tool_marks_gpu_compositor_dirty_before_mouse_up():
    class FakeCompositor:
        def __init__(self):
            self.marked_layer = None
            self.composite_calls = 0

        def mark_dirty(self, layer):
            self.marked_layer = layer

        def composite(self):
            self.composite_calls += 1

    image = np.zeros((16, 16, 4), dtype=np.uint8)
    image[4, 4] = (255, 0, 0, 255)
    stack = LayerStack(tile_size=8)
    stack.init_from_image(image)
    canvas = EditorCanvas(stack, gpu_compositing=False)
    fake = FakeCompositor()
    canvas._gpu_compositing = True
    canvas._gpu_compositor = fake
    canvas.set_brush_tool(BrushToolMode.MOVE)

    canvas._handle_mouse_down(4, 4, MouseButton.LEFT)
    canvas._handle_mouse_move(7, 5)

    assert stack.active_layer.image[5, 7, 3] == 255
    assert fake.marked_layer is stack.active_layer
    assert fake.composite_calls == 1
    assert canvas._composite_stale is True


def test_ctrl_left_click_picks_visible_color():
    image = np.zeros((8, 8, 4), dtype=np.uint8)
    image[3, 4] = (12, 34, 56, 255)
    stack = LayerStack(tile_size=8)
    stack.init_from_image(image)
    canvas = EditorCanvas(stack, gpu_compositing=False)
    picked = []
    canvas.on_color_picked = lambda r, g, b, a: picked.append((r, g, b, a))

    canvas._handle_mouse_down(4, 3, MouseButton.LEFT, Mods.CTRL.value)

    assert picked == [(12, 34, 56, 255)]


def test_pick_color_uses_layer_stack_when_canvas_composite_is_stale():
    image = np.zeros((8, 8, 4), dtype=np.uint8)
    image[3, 4] = (12, 34, 56, 255)
    stack = LayerStack(tile_size=8)
    stack.init_from_image(image)
    canvas = EditorCanvas(stack, gpu_compositing=False)
    canvas._composite = np.zeros_like(image)
    picked = []
    canvas.on_color_picked = lambda r, g, b, a: picked.append((r, g, b, a))

    canvas._pick_color(4, 3)

    assert picked == [(12, 34, 56, 255)]
