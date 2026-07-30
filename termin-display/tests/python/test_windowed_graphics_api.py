from termin.display.window import (
    BackendWindow,
    WindowHandle,
    WindowManager,
    WindowedGraphicsSession,
)
from tgfx import GraphicsHost, Tgfx2Context


def test_windowed_graphics_api_has_one_typed_graphics_host_boundary():
    assert WindowedGraphicsSession is not None
    assert BackendWindow is not None
    assert WindowHandle is not None
    assert WindowManager is not None
    assert WindowHandle.__module__ == "termin.display._platform_native"
    assert WindowManager.__module__ == "termin.display._platform_native"
    assert GraphicsHost is not None
    assert hasattr(WindowedGraphicsSession, "graphics")
    assert hasattr(WindowManager, "create_window")
    assert hasattr(WindowManager, "pump_events")
    assert hasattr(BackendWindow, "content_scale")
    assert hasattr(BackendWindow, "window_size")
    assert hasattr(BackendWindow, "framebuffer_size")
    assert hasattr(Tgfx2Context, "from_runtime")
