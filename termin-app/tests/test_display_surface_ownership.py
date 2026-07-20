import gc
import weakref

from termin.bootstrap import bootstrap_editor, shutdown_editor
from termin.display import Display


class _ExternalSurface:
    def __init__(self) -> None:
        self.size = (320, 200)

    def framebuffer_size(self) -> tuple[int, int]:
        return self.size

    def resize(self, width: int, height: int) -> bool:
        self.size = (width, height)
        return True

    def get_tgfx_color_tex_id(self) -> int:
        return 17

    def graphics_domain_key(self) -> int:
        return 0x1234


def test_python_wrapper_loss_does_not_destroy_display_owned_surface() -> None:
    bootstrap_editor()
    try:
        surface = _ExternalSurface()
        surface_ref = weakref.ref(surface)
        display = Display.from_surface(surface, name="external")
        handle = display.handle
        del surface
        del display
        gc.collect()

        # Native display storage retains the adapter body; a copied facade can
        # still use and explicitly destroy the same generation.
        assert surface_ref() is not None
        copied = Display.from_handle(*handle)
        assert copied.is_valid()
        assert copied.framebuffer_size() == (320, 200)
        assert copied.resize(640, 360)
        assert copied.destroy()
        gc.collect()
        assert surface_ref() is None
    finally:
        shutdown_editor()
