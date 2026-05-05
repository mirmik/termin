import numpy as np
from PIL import Image

from diffusion_editor.editor_window import EditorWindow
from diffusion_editor.layer_stack import LayerStack


class _Panel:
    def __init__(self):
        self.loaded = False

    def on_model_loaded(self, _result, _info):
        self.loaded = True


class _Engine:
    model_info = {"path": "model.safetensors"}

    def poll(self):
        return "load", "model.safetensors", None, None


class _Status:
    text = ""


def test_poll_diffusion_load_without_pending_request():
    window = object.__new__(EditorWindow)
    window._engine = _Engine()
    window._diffusion_panel = _Panel()
    window._statusbar = _Status()
    window._pending_request = None

    window._poll_diffusion()

    assert window._diffusion_panel.loaded
    assert window._statusbar.text == "Model loaded"


def _export_window(image):
    window = object.__new__(EditorWindow)
    window._layer_stack = LayerStack()
    window._layer_stack.init_from_image(image)
    window._statusbar = _Status()
    return window


def test_export_image_path_adds_png_extension_by_default(tmp_path):
    image = np.zeros((4, 4, 4), dtype=np.uint8)
    image[1, 2] = (10, 20, 30, 255)
    window = _export_window(image)
    path = tmp_path / "exported"

    assert window.export_image_path(str(path)) is True

    out_path = tmp_path / "exported.png"
    assert out_path.exists()
    out = np.array(Image.open(out_path).convert("RGBA"))
    assert tuple(out[1, 2]) == (10, 20, 30, 255)
    assert window._statusbar.text == "Exported: exported.png"


def test_export_image_path_rejects_unknown_extension(tmp_path):
    image = np.zeros((4, 4, 4), dtype=np.uint8)
    window = _export_window(image)
    path = tmp_path / "exported.xyz"

    assert window.export_image_path(str(path)) is False

    assert not path.exists()
    assert "Unknown export extension '.xyz'" in window._statusbar.text


def test_export_image_path_uses_layer_stack_composite_not_canvas_buffer(tmp_path):
    image = np.zeros((4, 4, 4), dtype=np.uint8)
    image[0, 0] = (255, 0, 0, 255)
    window = _export_window(image)
    window._canvas = object()
    path = tmp_path / "composite.png"

    assert window.export_image_path(str(path)) is True

    out = np.array(Image.open(path).convert("RGBA"))
    assert tuple(out[0, 0]) == (255, 0, 0, 255)
