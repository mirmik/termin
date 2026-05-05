from diffusion_editor.editor_window import EditorWindow


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
