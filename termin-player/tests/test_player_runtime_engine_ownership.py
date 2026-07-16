from termin.player.runtime import PlayerRuntime


class _BorrowedEngine:
    pass


def test_player_runtime_uses_explicit_borrowed_engine():
    engine = _BorrowedEngine()
    runtime = PlayerRuntime(".", "scene.json", engine=engine)

    assert runtime._ensure_engine_core()
    assert runtime._engine is engine
    assert not runtime._owns_engine


def test_player_runtime_creates_standalone_owned_engine(monkeypatch):
    import termin.engine

    created = []

    class _OwnedEngine:
        def __init__(self):
            created.append(self)

    monkeypatch.setattr(termin.engine, "EngineCore", _OwnedEngine)
    monkeypatch.setattr(termin.engine, "register_default_scene_extensions", lambda: None)
    runtime = PlayerRuntime(".", "scene.json")

    assert runtime._ensure_engine_core()
    assert runtime._engine is created[0]
    assert runtime._owns_engine
