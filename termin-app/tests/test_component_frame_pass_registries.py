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


def test_default_builtin_specs_live_below_app_layer() -> None:
    from termin.default_assets.builtin_types import (
        get_default_builtin_component_specs,
        get_default_builtin_frame_pass_specs,
    )

    component_specs = get_default_builtin_component_specs()
    frame_pass_specs = get_default_builtin_frame_pass_specs()

    assert ("termin.render_components", "CameraComponent") in component_specs
    assert ("termin.render_components", "CameraController") in component_specs
    assert ("termin.colliders.teleport_component", "TeleportComponent") in component_specs
    assert ("termin.render_passes", "HighlightPass") in frame_pass_specs
    assert ("termin.render_components", "MaterialPass") in frame_pass_specs
    assert (
        "termin.visualization.render.framegraph.passes.ui_widget",
        "UIWidgetPass",
    ) not in frame_pass_specs


def test_app_builtin_specs_extend_default_specs() -> None:
    from termin.assets.resources._builtins import (
        APP_BUILTIN_COMPONENTS,
        APP_BUILTIN_FRAME_PASSES,
        get_builtin_component_specs,
        get_builtin_frame_pass_specs,
    )

    component_specs = get_builtin_component_specs()
    frame_pass_specs = get_builtin_frame_pass_specs()

    assert APP_BUILTIN_COMPONENTS == []
    assert ("termin.colliders.teleport_component", "TeleportComponent") in component_specs
    assert ("termin.render_components", "CameraComponent") in component_specs
    assert ("termin.render_components", "CameraController") in component_specs

    app_ui_spec = (
        "termin.visualization.render.framegraph.passes.ui_widget",
        "UIWidgetPass",
    )
    assert app_ui_spec in APP_BUILTIN_FRAME_PASSES
    assert app_ui_spec in frame_pass_specs
    assert ("termin.render_passes", "HighlightPass") in frame_pass_specs
    assert ("termin.render_components", "MaterialPass") in frame_pass_specs
