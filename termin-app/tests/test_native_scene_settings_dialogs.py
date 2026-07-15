import gc
import weakref

import pytest

from termin.bootstrap import bootstrap_player, shutdown_player
from termin.editor_core.scene_settings_model import (
    SceneNamesController,
    ScenePropertiesController,
    ShadowSettingsController,
)
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.editor_native.scene_settings_dialogs import (
    build_native_scene_names_dialog,
    build_native_scene_properties_dialog,
    build_native_shadow_settings_dialog,
)
from termin.gui_native import Document, Rect
from termin.scene import TcScene

@pytest.fixture(scope="module", autouse=True)
def _bootstrap():
    bootstrap_player()
    yield
    shutdown_player()


@pytest.fixture
def scene():
    value = TcScene.create("native-scene-settings-test")
    yield value
    value.destroy()


def _host():
    document = Document()
    renders = []
    viewport = lambda: Rect(0.0, 0.0, 1000.0, 700.0)
    render = lambda: renders.append(True)
    return document, renders, viewport, render


def test_native_scene_names_dialog_saves_reopens_and_releases(scene):
    document, renders, viewport, render = _host()
    dialog = build_native_scene_names_dialog(
        document,
        SceneNamesController(scene),
        viewport=viewport,
        request_render=render,
    )

    assert dialog.show()
    root = dialog.dialog.widget.children[0]
    assert root.children[0].children[0].bounds.height == EDITOR_UI_METRICS.section_row
    layers = dialog.layers.text.split("\n")
    layers[5] = "Effects"
    dialog.layers.text = "\n".join(layers)
    assert dialog.dialog.activate("ok")
    assert SceneNamesController(scene).load().layers[5] == "Effects"
    assert dialog.show()

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    reference = weakref.ref(dialog)
    del dialog
    gc.collect()
    assert reference() is None
    assert renders


def test_native_shadow_settings_dialog_applies_live_and_releases(scene):
    document, _renders, viewport, render = _host()
    controller = ShadowSettingsController(scene)
    dialog = build_native_shadow_settings_dialog(
        document,
        controller,
        viewport=viewport,
        request_render=render,
    )

    assert dialog.show()
    root = dialog.dialog.widget.children[0]
    assert root.children[0].bounds.height == EDITOR_UI_METRICS.field_row
    assert root.children[0].children[0].bounds.width == EDITOR_UI_METRICS.form_label
    dialog.method.selected_index = 1
    dialog.softness.value = 2.5
    dialog.bias.value = 0.004
    dialog.apply_controls()
    assert controller.load().softness == pytest.approx(2.5)

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)


def test_native_scene_properties_dialog_mutates_reopens_and_releases(scene):
    document, renders, viewport, render = _host()
    controller = ScenePropertiesController(scene)
    service = NativeDialogService(document, viewport=viewport, request_render=render)
    dialog = build_native_scene_properties_dialog(
        document,
        controller,
        dialog_service=service,
        viewport=viewport,
        request_render=render,
    )

    assert dialog.show()
    root = dialog.dialog.widget.children[0]
    assert root.children[0].children[0].bounds.width == EDITOR_UI_METRICS.form_label
    assert root.children[-1].bounds.height == EDITOR_UI_METRICS.field_row
    dialog.set_intensity(0.875)
    dialog.set_skybox_type(1)
    assert controller.load().ambient_intensity == pytest.approx(0.875)
    assert dialog.dialog.activate("close")
    assert dialog.show()

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    reference = weakref.ref(dialog)
    del dialog
    gc.collect()
    assert reference() is None
    assert renders
