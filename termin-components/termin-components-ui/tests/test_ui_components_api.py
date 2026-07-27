import subprocess
import sys
import textwrap
from pathlib import Path

from termin.input import INPUT_SOURCE_EDITOR, INPUT_SOURCE_RUNTIME, InputComponent, MouseButtonEvent
from termin.input._input_native import accepts_input_source, is_input_handler
from termin.ui_components import UIComponent
from tcgui.widgets.ui import UI


def test_ui_component_is_exported_from_canonical_package() -> None:
    assert UIComponent.__name__ == "UIComponent"


def test_ui_component_uses_high_input_priority() -> None:
    ui = UIComponent()
    normal = InputComponent()

    assert is_input_handler(ui._tc.c_ptr_int())
    assert is_input_handler(normal._tc.c_ptr_int())
    assert ui.input_priority > normal.input_priority
    assert ui.input_priority == ui.priority


def test_input_component_defaults_to_runtime_source_only() -> None:
    component = InputComponent()
    c_ptr = component._tc.c_ptr_int()

    assert component.input_source_mask == INPUT_SOURCE_RUNTIME
    assert accepts_input_source(c_ptr, INPUT_SOURCE_RUNTIME)
    assert not accepts_input_source(c_ptr, INPUT_SOURCE_EDITOR)


def test_ui_component_defaults_to_runtime_source_only() -> None:
    ui = UIComponent()
    c_ptr = ui._tc.c_ptr_int()

    assert ui.input_source_mask == INPUT_SOURCE_RUNTIME
    assert accepts_input_source(c_ptr, INPUT_SOURCE_RUNTIME)
    assert not accepts_input_source(c_ptr, INPUT_SOURCE_EDITOR)


def test_ui_priority_updates_input_priority() -> None:
    ui = UIComponent(priority=7)

    assert ui.priority == 7
    assert ui.input_priority == 7
    ui.priority = 42
    assert ui.input_priority == 42


def test_mouse_button_event_exposes_handled_flag() -> None:
    event = MouseButtonEvent()

    assert event.handled is False
    assert event.source == INPUT_SOURCE_RUNTIME
    event.handled = True
    event.source = INPUT_SOURCE_EDITOR
    assert event.handled is True
    assert event.source == INPUT_SOURCE_EDITOR
    assert "source=" in repr(event)
    assert "handled=True" in repr(event)


def test_ui_close_releases_renderer_once() -> None:
    class RendererProbe:
        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1

    renderer = RendererProbe()
    ui = UI.__new__(UI)
    ui._renderer = renderer
    ui._closed = False

    ui.close()
    ui.close()

    assert renderer.close_count == 1


def test_ui_component_close_is_idempotent_and_preserves_root() -> None:
    class UIProbe:
        def __init__(self) -> None:
            self.root = object()
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1

    component = UIComponent()
    ui = UIProbe()
    component._ui = ui
    component._graphics = object()

    component.close()
    component.close()

    assert ui.close_count == 1
    assert component.ui is None
    assert component.root is ui.root
    assert component._graphics is None


def test_ui_component_lifecycle_closes_renderer_on_removal_and_scene_destroy() -> None:
    command = [sys.executable]
    source_overlay = (
        Path(__file__).resolve().parents[3]
        / "build"
        / "python-envs"
        / "test"
        / "overlay.json"
    )
    if source_overlay.is_file():
        command.extend(["--termin-overlay", str(source_overlay)])
    command.extend(
        [
            "-c",
            textwrap.dedent(
                """
                import termin.bootstrap
                from termin.scene import TcScene
                from termin.ui_components import UIComponent

                termin.bootstrap.bootstrap_player()

                class UIProbe:
                    def __init__(self):
                        self.root = object()
                        self.close_count = 0

                    def close(self):
                        self.close_count += 1

                removal_scene = TcScene.create("ui-component-removal")
                removal_entity = removal_scene.create_entity("entity")
                removal_component = UIComponent()
                removal_ui = UIProbe()
                removal_component._ui = removal_ui
                removal_component._graphics = object()
                removal_entity.add_component(removal_component)

                removal_entity.remove_component(removal_component)

                assert removal_ui.close_count == 1
                assert removal_component.ui is None
                assert removal_component.root is removal_ui.root
                removal_component.close()
                assert removal_ui.close_count == 1
                removal_scene.destroy()

                destroy_scene = TcScene.create("ui-component-scene-destroy")
                destroy_entity = destroy_scene.create_entity("entity")
                destroy_component = UIComponent()
                destroy_ui = UIProbe()
                destroy_component._ui = destroy_ui
                destroy_component._graphics = object()
                destroy_entity.add_component(destroy_component)

                destroy_scene.destroy()

                assert destroy_ui.close_count == 1
                assert destroy_component.ui is None
                assert destroy_component.root is destroy_ui.root
                destroy_component.close()
                assert destroy_ui.close_count == 1

                termin.bootstrap.shutdown_player()
                """
            ),
        ]
    )
    subprocess.run(
        command,
        check=True,
    )
