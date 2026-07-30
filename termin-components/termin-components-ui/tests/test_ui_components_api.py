import subprocess
import sys
import textwrap

from termin.gui_native import UiDocumentAsset
from termin.input import INPUT_SOURCE_EDITOR, INPUT_SOURCE_RUNTIME
from termin.input._input_native import (
    accepts_input_source,
    get_input_priority,
    is_input_handler,
)
from termin.ui_components import UIComponent
from termin.ui_components._ui_components_native import (
    has_scene_ui_document_capability,
)


SOURCE = """
uiscript: 2
root:
  type: termin.gui.Panel
  name: root
  background_color: [0.1, 0.2, 0.3, 1]
  children:
    - type: termin.gui.IconButton
      name: action
      icon: A
"""


def _declare_asset(uuid: str = "python-ui-component"):
    UiDocumentAsset.clear_registry_for_tests()
    asset = UiDocumentAsset.declare_source(
        uuid, "Python component UI", "UI/component.uiscript", SOURCE
    )
    assert asset.valid
    return asset


def test_ui_component_is_a_thin_native_projection() -> None:
    assert UIComponent.__name__ == "UIComponent"
    assert UIComponent.__module__ == "termin.ui_components.component"
    assert "tcgui" not in sys.modules

    component = UIComponent(priority=7)
    pointer = component.c_component_ptr()
    assert is_input_handler(pointer)
    assert has_scene_ui_document_capability(pointer)
    assert get_input_priority(pointer) == 7
    assert component.input_source_mask == INPUT_SOURCE_RUNTIME
    assert accepts_input_source(pointer, INPUT_SOURCE_RUNTIME)
    assert not accepts_input_source(pointer, INPUT_SOURCE_EDITOR)

    component.priority = 42
    component.input_source_mask = INPUT_SOURCE_RUNTIME | INPUT_SOURCE_EDITOR
    assert get_input_priority(pointer) == 42
    assert accepts_input_source(pointer, INPUT_SOURCE_RUNTIME)
    assert accepts_input_source(pointer, INPUT_SOURCE_EDITOR)


def test_asset_assignment_owns_independent_native_documents() -> None:
    asset = _declare_asset()
    first = UIComponent()
    second = UIComponent()

    first.ui_layout = asset
    second.ui_layout_uuid = asset.uuid
    assert first.ui_layout.uuid == asset.uuid
    assert second.ui_layout.uuid == asset.uuid
    assert first.has_document
    assert second.has_document
    assert first.document != second.document
    assert first.document.live_widget_count == 2
    assert second.document.live_widget_count == 2

    first.clear_document()
    assert not first.has_document
    assert second.has_document
    UiDocumentAsset.clear_registry_for_tests()


def test_reload_and_serialization_use_native_asset_handle() -> None:
    asset = _declare_asset("python-ui-reload")
    component = UIComponent(priority=13)
    component.ui_layout = asset
    old_root = component.document.root_at(0)

    assert not asset.reload_source(
        "uiscript: 2\nroot: {type: termin.gui.Missing}\n"
    )
    assert component.document.root_at(0) == old_root

    replacement = SOURCE.replace("name: action", "name: replacement")
    assert asset.reload_source(replacement)
    assert component.reload_document()
    assert component.document.root_at(0) != old_root

    data = component.serialize_data()
    assert data["ui_layout"]["type"] == "uuid"
    assert data["ui_layout"]["kind"] == "ui_document"
    assert data["ui_layout"]["uuid"] == asset.uuid
    assert component.priority == 13
    assert component.input_source_mask == INPUT_SOURCE_RUNTIME
    UiDocumentAsset.clear_registry_for_tests()


def test_native_scene_deserialization_does_not_import_tcgui() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                f"""
                import sys
                import termin.bootstrap
                from termin.gui_native import UiDocumentAsset
                from termin.scene import Entity, TcScene
                from termin.ui_components import UIComponent

                termin.bootstrap.bootstrap_player()
                asset = UiDocumentAsset.declare_source(
                    "native-scene-ui",
                    "Native scene UI",
                    "UI/scene.uiscript",
                    {SOURCE!r},
                )
                scene = TcScene.create("native-ui-deserialize")
                payload = {{
                    "uuid": "native-ui-entity",
                    "name": "UI",
                    "components": [{{
                        "type": "UIComponent",
                        "data": {{
                            "ui_layout": {{
                                "type": "uuid",
                                "kind": "ui_document",
                                "role": "ui_document",
                                "uuid": asset.uuid,
                                "name": asset.name,
                            }},
                            "priority": 31,
                            "input_source_mask": 1,
                        }},
                    }}],
                    "children": [],
                }}
                entity = Entity.deserialize_hierarchy(payload, scene, None)
                component = entity.get_component(UIComponent)
                assert component is not None
                assert component.ui_layout.uuid == asset.uuid
                assert component.has_document
                assert component.priority == 31
                assert "tcgui" not in sys.modules
                scene.destroy()
                termin.bootstrap.shutdown_player()
                """
            ),
        ],
        check=True,
    )
