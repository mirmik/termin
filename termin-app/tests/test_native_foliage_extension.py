from __future__ import annotations
from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy

from types import SimpleNamespace

from termin.editor_core.foliage_layer_editor_extension import FoliageLayerEditorExtension
from termin.editor_native.component_extensions import NativeComponentExtensionContext
from termin.editor_native.foliage_extension import project_native_foliage_extension
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import Rect


class _ComponentRef:
    def __init__(self, component: object) -> None:
        self._component = component

    def to_python(self) -> object:
        return self._component


def _find(root, debug_name: str):
    if root.debug_name == debug_name:
        return root
    for child in root.children:
        found = _find(child, debug_name)
        if found is not None:
            return found
    return None


def test_native_foliage_projector_tracks_shared_extension_state_and_lifetime():
    document = tc_ui_document_create()
    renders: list[bool] = []
    context = NativeComponentExtensionContext(
        engine=object(),
        document=document,
        request_render=lambda: renders.append(True),
        resource_manager=SimpleNamespace(external_assets=object()),
    )
    component = SimpleNamespace(foliage_uuid="", scale_min=0.8, scale_max=1.2)
    extension = FoliageLayerEditorExtension()
    extension.attach(context, object(), _ComponentRef(component))

    presentation = project_native_foliage_extension(extension, document)
    root = presentation.right_panel
    assert root is not None
    root.layout(Rect(0.0, 0.0, 340.0, 178.0))
    assert root.stable_id == "editor.inspector.extension.foliage"
    assert root.children[0].bounds.x == EDITOR_UI_METRICS.embedded_panel_padding
    assert root.children[0].bounds.height == EDITOR_UI_METRICS.section_row
    assert root.children[3].bounds.height == EDITOR_UI_METRICS.compact_row
    mode_label = _find(root, "native-foliage-mode")
    radius_label = _find(root, "native-foliage-radius")
    count_label = _find(root, "native-foliage-count")
    assert mode_label is not None
    assert radius_label is not None
    assert count_label is not None
    assert mode_label.name == "Mode: Off"

    extension.set_mode("paint")
    extension.change_radius(0.1)
    extension.change_count(2)
    assert context.active_viewport_tools == 1
    assert mode_label.name == "Mode: Paint"
    assert radius_label.name == "Radius: 0.60"
    assert count_label.name == "Count: 3"
    assert renders

    extension.detach()
    assert context.active_viewport_tools == 0
    assert not context.dispatch_viewport_click(object())
    assert not context.dispatch_viewport_key(object())
    tc_ui_document_destroy(document)


def test_native_component_extension_context_dispatches_latest_handler_first():
    document = tc_ui_document_create()
    context = NativeComponentExtensionContext(
        engine=object(),
        document=document,
        request_render=lambda: None,
        resource_manager=object(),
    )
    calls: list[str] = []

    def first(_event: object) -> bool:
        calls.append("first")
        return True

    def second(_event: object) -> bool:
        calls.append("second")
        return False

    context.add_viewport_click_interceptor(first)
    context.add_viewport_click_interceptor(second)
    context.add_viewport_pointer_handler(first)
    context.add_viewport_pointer_handler(second)
    assert context.dispatch_viewport_click(object())
    assert calls == ["second", "first"]
    calls.clear()
    assert context.dispatch_viewport_pointer(object())
    assert calls == ["second", "first"]
    context.remove_viewport_pointer_handler(second)
    context.remove_viewport_pointer_handler(first)
    context.remove_viewport_click_interceptor(second)
    context.remove_viewport_click_interceptor(first)
    tc_ui_document_destroy(document)
