import sys
import types

from termin.assets.resources import ResourceManager
from termin.render_framework.frame_pass_registry import FramePassRegistry
from termin.scene.component_registry import ComponentClassRegistry


def test_component_class_registry_registers_builtin_specs() -> None:
    module = types.ModuleType("_termin_component_registry_test_module")

    class ProbeComponent:
        pass

    module.ProbeComponent = ProbeComponent
    sys.modules[module.__name__] = module
    try:
        registry = ComponentClassRegistry()
        registered = registry.register_builtins([(module.__name__, "ProbeComponent")])

        assert registered == ["ProbeComponent"]
        assert registry.get("ProbeComponent") is ProbeComponent
        assert registry.list_names() == ["ProbeComponent"]
    finally:
        sys.modules.pop(module.__name__, None)


def test_frame_pass_registry_registers_builtin_specs() -> None:
    module = types.ModuleType("_termin_frame_pass_registry_test_module")

    class ProbeFramePass:
        pass

    module.ProbeFramePass = ProbeFramePass
    sys.modules[module.__name__] = module
    try:
        registry = FramePassRegistry()
        registered = registry.register_builtins([(module.__name__, "ProbeFramePass")])

        assert registered == ["ProbeFramePass"]
        assert registry.get("ProbeFramePass") is ProbeFramePass
        assert registry.list_names() == ["ProbeFramePass"]
    finally:
        sys.modules.pop(module.__name__, None)


def test_resource_manager_delegates_component_and_frame_pass_facades() -> None:
    rm = ResourceManager()

    class ProbeComponent:
        pass

    class ProbeFramePass:
        pass

    rm.register_component("ProbeComponent", ProbeComponent)
    rm.register_frame_pass("ProbeFramePass", ProbeFramePass)

    assert rm.component_registry.get("ProbeComponent") is ProbeComponent
    assert rm.components["ProbeComponent"] is ProbeComponent
    assert rm.get_component("ProbeComponent") is ProbeComponent
    assert rm.list_component_names() == ["ProbeComponent"]

    assert rm.frame_pass_registry.get("ProbeFramePass") is ProbeFramePass
    assert rm.frame_passes["ProbeFramePass"] is ProbeFramePass
    assert rm.get_frame_pass("ProbeFramePass") is ProbeFramePass
    assert rm.list_frame_pass_names() == ["ProbeFramePass"]
