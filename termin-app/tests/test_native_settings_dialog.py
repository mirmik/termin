from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from termin.editor_core.settings_model import EditorSettingsController
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.editor_native.settings_dialog import build_native_settings_dialog
from termin.gui_native import Rect

from test_editor_settings_model import _Settings


def test_native_settings_dialog_loads_applies_saves_reopens_and_releases():
    settings = _Settings()
    controller = EditorSettingsController(settings)
    document = tc_ui_document_create()
    renders = []
    applied = []
    applied_display_policy = []
    viewport = lambda: Rect(0.0, 0.0, 900.0, 600.0)
    dialog_service = NativeDialogService(
        document,
        viewport=viewport,
        request_render=lambda: renders.append(True),
    )
    dialog = build_native_settings_dialog(
        document,
        controller,
        dialog_service=dialog_service,
        viewport=viewport,
        request_render=lambda: renders.append(True),
        apply_font_size=applied.append,
        apply_render_only_active_display=applied_display_policy.append,
    )

    assert dialog.show()
    editor_row = dialog.root.children[0]
    assert editor_row.bounds.x - dialog.root.bounds.x == EDITOR_UI_METRICS.dialog_padding
    assert editor_row.bounds.height == (
        EDITOR_UI_METRICS.compact_status_row
        + EDITOR_UI_METRICS.compact_spacing
        + EDITOR_UI_METRICS.field_row
    )
    assert editor_row.children[0].bounds.height == EDITOR_UI_METRICS.compact_status_row
    assert editor_row.children[1].bounds.height == EDITOR_UI_METRICS.field_row
    assert dialog.root.children[-2].bounds.height == EDITOR_UI_METRICS.field_row
    assert dialog.text_editor.text == "/usr/bin/editor"
    assert dialog.vsync_enabled.checked is True
    assert dialog.fps_limit.value == 60
    assert dialog.render_only_active_display.checked is True
    dialog.text_editor.text = " /opt/code "
    dialog.slang_compiler.text = " /opt/slangc "
    dialog.font_size.value = 18.0
    dialog.font_size_small.value = 12.0
    dialog.mcp_enabled.checked = True
    dialog.vsync_enabled.checked = False
    dialog.fps_limit.value = 120
    dialog.render_only_active_display.checked = False
    dialog.apply_live()
    assert applied == [18.0]
    assert settings.sync_count == 0

    assert dialog.dialog.activate("ok")
    assert settings.text_editor == "/opt/code"
    assert settings.slang_compiler == "/opt/slangc"
    assert settings.mcp_enabled is True
    assert settings.vsync_enabled is False
    assert settings.fps_limit == 120
    assert settings.render_only_active_display is False
    assert settings.sync_count == 1
    assert applied == [18.0, 18.0]
    assert applied_display_policy == [False]

    assert dialog.show()
    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    assert renders
    tc_ui_document_destroy(document)
