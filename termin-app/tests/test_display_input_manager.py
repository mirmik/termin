from termin.display.input_manager import BasicDisplayInputManager


def test_basic_display_input_manager_explicitly_releases_viewports_and_router(monkeypatch):
    import termin.display.input_manager as input_module

    freed_viewports = []
    freed_routers = []
    next_pointer = iter((201, 202))
    monkeypatch.setattr(input_module, "_display_input_router_new", lambda display: display + 100)
    monkeypatch.setattr(input_module, "_display_input_router_base", lambda router: router + 1)
    monkeypatch.setattr(input_module, "_display_input_router_free", freed_routers.append)
    monkeypatch.setattr(input_module, "_viewport_get_input_manager", lambda _index, _generation: 0)
    monkeypatch.setattr(input_module, "_viewport_input_manager_new", lambda _index, _generation: next(next_pointer))
    monkeypatch.setattr(input_module, "_viewport_input_manager_free", freed_viewports.append)

    manager = BasicDisplayInputManager(7)
    assert manager.tc_input_manager_ptr == 108
    assert manager.add_viewport(1, 2)
    assert manager.add_viewport(1, 2)
    assert manager.add_viewport(3, 4)
    assert manager.remove_viewport(1, 2)
    assert not manager.remove_viewport(1, 2)
    assert freed_viewports == [201]

    manager.close()
    manager.close()
    assert freed_viewports == [201, 202]
    assert freed_routers == [107]
