from termin.display.input_manager import BasicDisplayInputManager


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


def test_display_is_the_only_exported_surface_and_input_host():
    import termin.display as display_module

    assert "DisplayInputRouter" not in dir(display_module)
    assert "FBOSurface" not in dir(display_module)
    assert "DisplayViewportHost" not in dir(display_module)
    for method_name in (
        "is_valid",
        "get_tgfx_color_tex_id",
        "framebuffer_size",
        "resize",
        "dispatch_pointer_move",
        "dispatch_pointer_button",
        "dispatch_wheel",
        "dispatch_key",
        "dispatch_text",
    ):
        assert callable(getattr(display_module.Display, method_name))
