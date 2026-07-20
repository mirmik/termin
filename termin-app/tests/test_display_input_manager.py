from termin.display.input_manager import BasicDisplayInputManager
from termin.display.viewport_host import DisplayViewportHost


def test_basic_display_input_manager_releases_only_owned_viewport_managers(monkeypatch):
    import termin.display.input_manager as input_module

    freed_viewports = []
    next_pointer = iter((201, 202))
    monkeypatch.setattr(
        input_module,
        "_display_get_input_manager",
        lambda index, generation: index + generation + 101,
    )
    monkeypatch.setattr(input_module, "_viewport_get_input_manager", lambda _index, _generation: 0)
    monkeypatch.setattr(input_module, "_viewport_input_manager_new", lambda _index, _generation: next(next_pointer))
    monkeypatch.setattr(input_module, "_viewport_input_manager_free", freed_viewports.append)

    manager = BasicDisplayInputManager((7, 3))
    assert manager.tc_input_manager_ptr == 111
    assert manager.add_viewport(1, 2)
    assert manager.add_viewport(1, 2)
    assert manager.add_viewport(3, 4)
    assert manager.remove_viewport(1, 2)
    assert not manager.remove_viewport(1, 2)
    assert freed_viewports == [201]

    manager.close()
    manager.close()
    assert freed_viewports == [201, 202]


def test_display_viewport_host_routes_rendering_to_surface_and_input_to_display():
    class Surface:
        def is_valid(self):
            return True

        def get_tgfx_color_tex_id(self):
            return 17

        def framebuffer_size(self):
            return (800, 600)

        def resize(self, width, height):
            return (width, height) == (400, 300)

    class Display:
        def __init__(self):
            self.events = []

        def is_valid(self):
            return True

        def dispatch_pointer_move(self, x, y):
            self.events.append(("move", x, y))
            return True

        def dispatch_pointer_button(self, *args):
            self.events.append(("button", *args))
            return True

        def dispatch_wheel(self, *args):
            self.events.append(("wheel", *args))
            return True

        def dispatch_key(self, *args):
            self.events.append(("key", *args))
            return True

        def dispatch_text(self, codepoint):
            self.events.append(("text", codepoint))
            return True

    surface = Surface()
    display = Display()
    host = DisplayViewportHost(surface, display)
    assert host.is_valid()
    assert host.get_tgfx_color_tex_id() == 17
    assert host.framebuffer_size() == (800, 600)
    assert host.resize(400, 300)
    assert host.dispatch_pointer_move(40.0, 30.0)
    assert host.dispatch_pointer_button(0, 1, 2, 1)
    assert host.dispatch_scroll(0.0, -1.0, 2)
    assert host.dispatch_key(65, 4, 1, 2)
    assert host.dispatch_text(0x416)
    assert display.events == [
        ("move", 40.0, 30.0),
        ("button", 40.0, 30.0, 0, 1, 2, 1),
        ("wheel", 40.0, 30.0, 0.0, -1.0, 2),
        ("key", 65, 4, 1, 2),
        ("text", 0x416),
    ]


def test_surface_and_module_no_longer_export_display_input_ownership():
    import termin.display as display_module

    assert "DisplayInputRouter" not in dir(display_module)
    assert "set_input_manager" not in dir(display_module.FBOSurface)
    assert "dispatch_pointer_move" not in dir(display_module.FBOSurface)
