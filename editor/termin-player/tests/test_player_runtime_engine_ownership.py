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


def test_source_player_transfers_selected_controller_after_module_publication(monkeypatch):
    import termin.player.runtime as player_runtime

    events = []
    module_runtime = object()
    controller = object()

    class _Engine:
        def begin_session(self, selected):
            events.append(("begin", selected))
            return True

    class _Runtime(PlayerRuntime):
        def _load_modules(self):
            events.append(("modules", None))
            return module_runtime

    def create_controller(project_path, *, log_prefix):
        events.append(("create", (project_path, log_prefix)))
        return controller

    monkeypatch.setattr(player_runtime, "create_project_world_controller", create_controller)
    runtime = _Runtime("/project", "Main.scene", engine=_Engine())

    runtime._start_project_session()

    assert events == [
        ("modules", None),
        ("create", (runtime.project_path, "[PlayerRuntime]")),
        ("begin", controller),
    ]
    assert runtime._project_modules_runtime is module_runtime
    assert runtime._session_started
