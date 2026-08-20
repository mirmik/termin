from termin.player.runtime import PlayerRuntime


class _FakeDisplay:
    handle = (101, 7)


class _InputSink:
    def __init__(self):
        self.display_handle = None


class _Viewport:
    def __init__(self, name, input_mode, index, generation):
        self.name = name
        self.input_mode = input_mode
        self._index = index
        self._generation = generation
        self.render_target = None

    def _viewport_handle(self):
        return self._index, self._generation


class _BasicDisplayInputManager:
    instances = []

    def __init__(self, display_handle):
        self.display_handle = display_handle
        self.viewports = []
        self.tc_input_manager_ptr = 4242
        _BasicDisplayInputManager.instances.append(self)

    def add_viewport(self, index, generation):
        self.viewports.append((index, generation))
        return True

    def close(self):
        pass


def test_player_runtime_sets_up_display_router_and_viewport_input_managers(monkeypatch):
    import termin.display
    import termin.display.window

    def attach_input(window, index, generation):
        window.display_handle = (index, generation)

    monkeypatch.setattr(termin.display, "BasicDisplayInputManager", _BasicDisplayInputManager)
    monkeypatch.setattr(
        termin.display.window,
        "attach_window_input_display",
        attach_input,
    )
    _BasicDisplayInputManager.instances.clear()

    runtime = PlayerRuntime(".", "scene.json")
    runtime._display = _FakeDisplay()
    runtime.window = _InputSink()
    runtime._viewports = [
        _Viewport("Main", "simple", 1, 10),
        _Viewport("Overlay", "basic", 2, 20),
        _Viewport("Disabled", "none", 3, 30),
        _Viewport("EditorOnly", "editor", 4, 40),
    ]

    runtime._setup_input()

    assert len(_BasicDisplayInputManager.instances) == 1
    input_manager = _BasicDisplayInputManager.instances[0]
    assert input_manager.display_handle == (101, 7)
    assert input_manager.viewports == [(1, 10), (2, 20)]
    assert runtime._input_manager is input_manager
    assert runtime.window.display_handle == (101, 7)


def test_player_runtime_tracks_runtime_session_primary_viewports(monkeypatch):
    import termin.engine

    runtime = PlayerRuntime(".", "scene.json")
    handle = type("_SceneHandle", (), {"index": 4, "generation": 2})()

    class _Scene:
        def scene_handle(self):
            return handle

    runtime.scene = _Scene()
    viewports = [
        _Viewport("Main", "simple", 1, 10),
        _Viewport("Overlay", "basic", 2, 20),
    ]

    class _Context:
        primary_scene = runtime.scene

        def transition_to(self, scene_identity):
            assert scene_identity == "scene.json"
            return True

    class _Topology:
        def viewports(self, scene):
            assert scene is runtime.scene
            return viewports

    class _Manager:
        managed_render_targets = []
        topology = _Topology()

    class _Engine:
        def tick_and_render(self, dt):
            assert dt == 0.0

    monkeypatch.setattr(termin.engine, "require_world_context", lambda scene, scope: _Context())
    runtime._engine = _Engine()

    assert runtime._activate_primary_scene(_Manager())
    assert runtime._viewport is viewports[0]
    assert runtime._viewports == viewports


def test_player_runtime_reconciles_elevated_primary_scene(monkeypatch):
    import termin.engine

    runtime = PlayerRuntime(".", "Main.scene")
    old_handle = type("_SceneHandle", (), {"index": 4, "generation": 2})()
    new_handle = type("_SceneHandle", (), {"index": 8, "generation": 3})()

    class _Scene:
        def __init__(self, handle):
            self._handle = handle

        def scene_handle(self):
            return self._handle

    old_scene = _Scene(old_handle)
    new_scene = _Scene(new_handle)
    runtime.scene = old_scene
    viewports = [_Viewport("Secondary", "simple", 6, 12)]

    class _Context:
        primary_scene = new_scene

    class _Topology:
        def viewports(self, scene):
            assert scene is new_scene
            return viewports

    class _RenderingManager:
        managed_render_targets = []
        topology = _Topology()

    class _Manager:
        def key_of(self, scene):
            assert scene is new_scene
            return termin.engine.SceneKey(
                "Secondary.scene",
                termin.engine.SceneRole.RUNTIME,
            )

    class _Engine:
        scene_manager = _Manager()
        rendering_manager = _RenderingManager()

    class _InputManager:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    old_input = _InputManager()
    runtime._engine = _Engine()
    runtime._input_manager = old_input
    monkeypatch.setattr(
        termin.engine,
        "require_world_context",
        lambda scene, scope: _Context(),
    )
    monkeypatch.setattr(runtime, "_setup_input", lambda: None)

    runtime._reconcile_primary_scene()

    assert old_input.closed
    assert runtime.scene is new_scene
    assert runtime.scene_name == "Secondary.scene"
    assert runtime._viewport is viewports[0]
    assert runtime._viewports == viewports


def test_player_runtime_camera_follows_presented_viewport():
    runtime = PlayerRuntime(".", "scene.json")

    assert runtime.camera is None

    viewport = _Viewport("Main", "simple", 1, 10)
    runtime._viewport = viewport
    assert runtime.camera is None

    camera = object()
    viewport.render_target = type("_RenderTarget", (), {"camera": camera})()
    assert runtime.camera is camera


def test_player_runtime_shutdown_runs_after_failed_initialize():
    class _FailingRuntime(PlayerRuntime):
        def __init__(self):
            super().__init__(".", "scene.json")
            self.shutdown_called = False

        def initialize(self):
            return False

        def shutdown(self):
            self.shutdown_called = True

    runtime = _FailingRuntime()

    runtime.run()

    assert runtime.shutdown_called
