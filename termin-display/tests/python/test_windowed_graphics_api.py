from termin.display import BackendWindow, WindowedGraphicsSession
from tgfx import GraphicsHost, Tgfx2Context


def test_windowed_graphics_api_has_one_typed_graphics_host_boundary():
    assert WindowedGraphicsSession is not None
    assert GraphicsHost is not None
    assert hasattr(WindowedGraphicsSession, "graphics")
    assert hasattr(Tgfx2Context, "from_runtime")

    assert not hasattr(BackendWindow, "device")
    assert not hasattr(BackendWindow, "context")
    assert not hasattr(Tgfx2Context, "from_window")

