from types import SimpleNamespace

from termin.player import screenshot


def test_player_screenshot_uses_runtime_rendering_manager(monkeypatch):
    device = object()
    render_engine = SimpleNamespace(
        ensure_tgfx2=lambda: None,
        tgfx2_device=device,
    )
    runtime = SimpleNamespace(
        rendering_manager=SimpleNamespace(render_engine=render_engine),
        display=object(),
    )
    captured = []
    monkeypatch.setattr(
        screenshot,
        "capture_surface_screenshot",
        lambda surface, actual_device, **kwargs: captured.append(
            (surface, actual_device, kwargs)
        )
        or {"path": "/tmp/player.png"},
    )

    result = screenshot.capture_player_screenshot(runtime)

    assert result == {"path": "/tmp/player.png"}
    assert captured[0][0] is runtime.display
    assert captured[0][1] is device
