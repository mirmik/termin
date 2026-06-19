import sys
import types

from termin.player.runtime import PlayerRuntime


class _FakeDisplay:
    tc_display_ptr = 101


class _InputSink:
    def __init__(self):
        self.input_manager_ptr = 0

    def set_input_manager(self, ptr):
        self.input_manager_ptr = ptr


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

    def __init__(self, display_ptr):
        self.display_ptr = display_ptr
        self.viewports = []
        self.tc_input_manager_ptr = 4242
        _BasicDisplayInputManager.instances.append(self)

    def add_viewport(self, index, generation):
        self.viewports.append((index, generation))
        return True


def test_player_runtime_sets_up_display_router_and_viewport_input_managers(monkeypatch):
    platform_module = types.ModuleType("termin.visualization.platform.input_manager")
    platform_module.BasicDisplayInputManager = _BasicDisplayInputManager
    monkeypatch.setitem(sys.modules, "termin.visualization.platform.input_manager", platform_module)
    _BasicDisplayInputManager.instances.clear()

    runtime = PlayerRuntime(".", "scene.json")
    runtime._display = _FakeDisplay()
    runtime.window = _InputSink()
    runtime.surface = _InputSink()
    runtime._viewports = [
        _Viewport("Main", "simple", 1, 10),
        _Viewport("Overlay", "basic", 2, 20),
        _Viewport("Disabled", "none", 3, 30),
        _Viewport("EditorOnly", "editor", 4, 40),
    ]

    runtime._setup_input()

    assert len(_BasicDisplayInputManager.instances) == 1
    input_manager = _BasicDisplayInputManager.instances[0]
    assert input_manager.display_ptr == 101
    assert input_manager.viewports == [(1, 10), (2, 20)]
    assert runtime._input_manager is input_manager
    assert runtime.window.input_manager_ptr == 4242
    assert runtime.surface.input_manager_ptr == 4242


def test_player_runtime_tracks_attached_viewports():
    runtime = PlayerRuntime(".", "scene.json")
    runtime.scene = object()
    viewports = [
        _Viewport("Main", "simple", 1, 10),
        _Viewport("Overlay", "basic", 2, 20),
    ]

    class _Manager:
        managed_render_targets = []

        def attach_scene_full(self, scene):
            assert scene is runtime.scene
            return viewports

    assert runtime._attach_scene_rendering(_Manager(), object())
    assert runtime._viewport is viewports[0]
    assert runtime._viewports == viewports
