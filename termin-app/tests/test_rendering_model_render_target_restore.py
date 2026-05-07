import importlib.util
import sys
import types
from pathlib import Path


_MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "termin"
    / "editor_core"
    / "rendering_model.py"
)
_SPEC = importlib.util.spec_from_file_location("rendering_model_source", _MODEL_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
RenderingModel = _MODULE.RenderingModel


class _Pipeline:
    def __init__(self, name):
        self.name = name
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class _CameraComponent:
    pass


class _Entity:
    def __init__(self, uuid, camera):
        self.uuid = uuid
        self._camera = camera

    def get_component(self, component_type):
        assert component_type is _CameraComponent
        return self._camera


class _Scene:
    def __init__(self, mount, entities=None):
        self._mount = mount
        self.entities = entities or []

    def equal(self, other):
        return self is other


class _Mount:
    def __init__(self, configs, viewport_configs=None):
        self.render_target_configs = configs
        self.viewport_configs = viewport_configs or []

    def add_render_target_config(self, config):
        self.render_target_configs.append(config)

    def clear_render_target_configs(self):
        self.render_target_configs.clear()

    def render_target_config_count(self):
        return len(self.render_target_configs)

    def render_target_config_at(self, index):
        return self.render_target_configs[index]

    def remove_render_target_config(self, index):
        del self.render_target_configs[index]


class _RenderTargetConfig:
    def __init__(self):
        self.name = "Custom"
        self.camera_uuid = ""
        self.width = 320
        self.height = 200
        self.dynamic_resolution = False
        self.pipeline_uuid = ""
        self.pipeline_name = "Triangle"
        self.layer_mask = 7
        self.enabled = True


class _ViewportConfig:
    def __init__(self):
        self.camera_uuid = ""
        self.display_name = "Display"
        self.name = "Viewport"
        self.input_mode = "simple"


class _RenderTarget:
    _next_index = 1

    def __init__(self, name, pool):
        self.name = name
        self._pool = pool
        self.index = _RenderTarget._next_index
        _RenderTarget._next_index += 1
        self.generation = 1
        self.locked = False
        self.scene = None
        self.camera = None
        self.width = 0
        self.height = 0
        self.dynamic_resolution = False
        self.pipeline = None
        self.layer_mask = 0
        self.enabled = False

    def free(self):
        if self in self._pool:
            self._pool.remove(self)


class _Viewport:
    def __init__(self):
        self.name = "Viewport"
        self.render_target = None
        self.scene = None
        self.index = 0
        self.generation = 0


class _Manager:
    def __init__(self):
        self.created = []
        self.displays = []
        self.attached = []
        self.detached = []
        self.display_for_viewport = None
        self.standalone_render_targets = []
        self.registered = []
        self.unregistered = []

    def create_pipeline(self, name):
        self.created.append(name)
        return _Pipeline(name)

    def attach_scene(self, scene):
        self.attached.append(scene)
        return []

    def detach_scene_full(self, scene):
        self.detached.append(scene)

    def get_display_for_viewport(self, viewport):
        return self.display_for_viewport

    def register_standalone_render_target(self, rt):
        self.registered.append(rt)
        if rt not in self.standalone_render_targets:
            self.standalone_render_targets.append(rt)

    def unregister_standalone_render_target(self, rt):
        self.unregistered.append(rt)
        if rt in self.standalone_render_targets:
            self.standalone_render_targets.remove(rt)


def _install_native_stubs(monkeypatch, pool):
    native_module = types.ModuleType("termin.render_framework._render_framework_native")

    def render_target_pool_list():
        return pool

    def render_target_new(name):
        render_target = _RenderTarget(name, pool)
        pool.append(render_target)
        return render_target

    native_module.render_target_pool_list = render_target_pool_list
    native_module.render_target_new = render_target_new
    monkeypatch.setitem(sys.modules, "termin.render_framework._render_framework_native", native_module)

    scene_module = types.ModuleType("termin.visualization.core.scene")
    scene_module.scene_render_mount = lambda scene: scene._mount
    monkeypatch.setitem(sys.modules, "termin.visualization.core.scene", scene_module)

    camera_module = types.ModuleType("termin.visualization.core.camera")
    camera_module.CameraComponent = _CameraComponent
    monkeypatch.setitem(sys.modules, "termin.visualization.core.camera", camera_module)

    log = types.SimpleNamespace(error=lambda message: None)
    native_log_module = types.ModuleType("termin._native")
    native_log_module.log = log
    monkeypatch.setitem(sys.modules, "termin._native", native_log_module)

    rt_config_module = types.ModuleType("termin.visualization.core.render_target_config")
    rt_config_module.RenderTargetConfig = _RenderTargetConfig
    monkeypatch.setitem(sys.modules, "termin.visualization.core.render_target_config", rt_config_module)


def test_viewport_uses_restored_render_target_by_config_name(monkeypatch):
    pool = []
    _install_native_stubs(monkeypatch, pool)

    config = _RenderTargetConfig()
    scene = _Scene(_Mount([config]))
    manager = _Manager()
    model = RenderingModel(manager)
    viewport = _Viewport()
    render_target = model.ensure_viewport_render_target(
        viewport,
        scene=scene,
    )

    assert len(pool) == 1
    assert render_target is pool[0]
    assert viewport.render_target is render_target
    assert render_target.pipeline.name == "Default"
    assert manager.created == ["Default"]


def test_viewport_does_not_copy_camera_or_pipeline_from_render_target(monkeypatch):
    pool = []
    _install_native_stubs(monkeypatch, pool)

    scene = _Scene(_Mount([]))
    manager = _Manager()
    model = RenderingModel(manager)
    viewport = _Viewport()
    render_target = _RenderTarget("NativeRT", pool)
    camera = object()
    pipeline = _Pipeline("Triangle")
    render_target.camera = camera
    render_target.pipeline = pipeline
    viewport.render_target = render_target

    result = model.ensure_viewport_render_target(viewport, scene=scene)

    assert result is render_target
    assert "camera" not in vars(viewport)
    assert manager.created == []


def test_attach_scene_does_not_restore_render_target_configs_in_python(monkeypatch):
    pool = []
    _install_native_stubs(monkeypatch, pool)

    config = _RenderTargetConfig()
    scene = _Scene(_Mount([config]))
    manager = _Manager()
    model = RenderingModel(manager)

    viewports = model.attach_scene(scene)

    assert viewports == []
    assert pool == []
    assert manager.attached == [scene]


def test_detach_scene_delegates_to_rendering_manager_full_detach(monkeypatch):
    pool = []
    _install_native_stubs(monkeypatch, pool)

    scene = _Scene(_Mount([]))
    manager = _Manager()
    model = RenderingModel(manager)

    emptied = model.detach_scene(scene)

    assert emptied == set()
    assert manager.detached == [scene]


def test_remove_render_target_removes_live_target_and_scene_config(monkeypatch):
    pool = []
    _install_native_stubs(monkeypatch, pool)

    config = _RenderTargetConfig()
    scene = _Scene(_Mount([config]))
    manager = _Manager()
    model = RenderingModel(manager)
    render_target = _RenderTarget("Custom", pool)
    pool.append(render_target)
    manager.standalone_render_targets.append(render_target)

    model.remove_render_target(render_target, scene=scene)

    assert pool == []
    assert scene._mount.render_target_configs == []
    assert manager.unregistered == [render_target]


def test_sync_render_target_configs_writes_only_targets_from_scene(monkeypatch):
    pool = []
    _install_native_stubs(monkeypatch, pool)

    scene = _Scene(_Mount([]))
    other_scene = _Scene(_Mount([]))
    manager = _Manager()
    model = RenderingModel(manager)

    owned = _RenderTarget("Owned", pool)
    owned.scene = scene
    owned.camera = None
    owned.width = 100
    owned.height = 50
    owned.pipeline = None
    manager.standalone_render_targets.append(owned)

    foreign = _RenderTarget("Foreign", pool)
    foreign.scene = other_scene
    manager.standalone_render_targets.append(foreign)

    detached = _RenderTarget("Detached", pool)
    manager.standalone_render_targets.append(detached)

    model.sync_render_target_configs_to_scene(scene)

    assert [config.name for config in scene._mount.render_target_configs] == ["Owned"]


def test_sync_render_target_configs_only_includes_standalone_targets(monkeypatch):
    """Standalone targets from the scene are written; viewport-owned targets
    are not in standalone_render_targets to begin with."""
    pool = []
    _install_native_stubs(monkeypatch, pool)

    scene = _Scene(_Mount([]))
    manager = _Manager()
    model = RenderingModel(manager)

    standalone = _RenderTarget("StandaloneRT", pool)
    standalone.scene = scene
    manager.standalone_render_targets.append(standalone)

    viewport = _Viewport()
    viewport.render_target = _RenderTarget("ViewportRT", pool)
    viewport.render_target.scene = scene
    display = types.SimpleNamespace(viewports=[viewport])
    manager.displays = [display]

    model.sync_render_target_configs_to_scene(scene)

    assert [config.name for config in scene._mount.render_target_configs] == ["StandaloneRT"]


def test_standalone_render_targets_filters_viewport_owned_targets(monkeypatch):
    pool = []
    _install_native_stubs(monkeypatch, pool)

    manager = _Manager()
    manager.displays = []
    model = RenderingModel(manager)

    viewport_target = _RenderTarget("MainGameRT", pool)
    standalone_target = _RenderTarget("StandaloneRT", pool)
    pool.extend([viewport_target, standalone_target])

    viewport = _Viewport()
    viewport.render_target = viewport_target
    manager.displays = [types.SimpleNamespace(viewports=[viewport])]

    assert model.standalone_render_targets(pool) == [standalone_target]
