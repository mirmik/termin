from termin.display.window import (
    BackendWindow,
    WindowHandle,
    WindowManager,
    WindowedGraphicsSession,
    attach_window_input_display,
)
from termin.graphics import GraphicsHost, Tgfx2Context


def test_windowed_graphics_api_has_one_typed_graphics_host_boundary():
    assert WindowedGraphicsSession is not None
    assert BackendWindow is not None
    assert WindowHandle is not None
    assert WindowManager is not None
    assert WindowHandle.__module__ == "termin.window._window_native"
    assert WindowManager.__module__ == "termin.window._window_native"
    assert GraphicsHost is not None
    assert hasattr(WindowedGraphicsSession, "graphics")
    assert hasattr(WindowManager, "create_window")
    assert hasattr(WindowManager, "pump_events")
    assert hasattr(BackendWindow, "content_scale")
    assert hasattr(BackendWindow, "window_size")
    assert hasattr(BackendWindow, "framebuffer_size")
    assert callable(attach_window_input_display)
    assert hasattr(Tgfx2Context, "from_runtime")


def test_display_is_the_viewport_surface_and_input_protocol():
    from termin.display import Display

    surface_methods = (
        "is_valid",
        "get_tgfx_color_tex_id",
        "framebuffer_size",
        "resize",
    )
    input_methods = (
        "dispatch_pointer_move",
        "dispatch_pointer_button",
        "dispatch_wheel",
        "dispatch_key",
        "dispatch_text",
    )
    for method_name in surface_methods + input_methods:
        assert callable(getattr(Display, method_name))
