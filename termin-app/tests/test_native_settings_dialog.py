from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from termin.editor_core.settings_model import EditorSettingsController
from termin.editor_native.dialog_service import NativeDialogService
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
    saved = []
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
        on_saved=saved.append,
    )

    assert dialog.show()
    assert dialog.tabs.page_count == 2
    assert dialog.tabs.page_title(1) == "Build Toolchain"
    dialog.tabs.selected_index = 1
    document.layout_roots(viewport())
    assert dialog.build_gradle.widget.stable_id == "editor.settings.build.gradle"
    assert dialog.build_android_home.widget.stable_id == "editor.settings.build.android-home"
    assert dialog.build_android_ndk_root.widget.stable_id == "editor.settings.build.android-ndk-root"
    assert dialog.build_java_home.widget.stable_id == "editor.settings.build.java-home"
    assert dialog.build_gradle.widget.bounds.height > 0
    assert dialog.build_adb.widget.bounds.y > dialog.build_gradle.widget.bounds.y
    assert dialog.text_editor.text == "/usr/bin/editor"
    assert dialog.build_gradle.text == "/opt/gradle/bin/gradle"
    assert dialog.vsync_enabled.checked is True
    assert dialog.fps_limit.value == 60
    assert dialog.render_only_active_display.checked is True
    dialog.text_editor.text = " /opt/code "
    dialog.slang_compiler.text = " /opt/slangc "
    dialog.build_sdk_root.text = " /opt/termin/sdk "
    dialog.build_android_home.text = " /opt/android/sdk "
    dialog.build_android_ndk_root.text = " /opt/android/ndk/27.2.12479018 "
    dialog.build_java_home.text = " /opt/jdk-17 "
    dialog.build_gradle.text = " /opt/gradle-8/bin/gradle "
    dialog.build_adb.text = " /opt/android/platform-tools/adb "
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
    assert settings.build_sdk_root == "/opt/termin/sdk"
    assert settings.build_android_home == "/opt/android/sdk"
    assert settings.build_android_ndk_root == "/opt/android/ndk/27.2.12479018"
    assert settings.build_java_home == "/opt/jdk-17"
    assert settings.build_gradle == "/opt/gradle-8/bin/gradle"
    assert settings.build_adb == "/opt/android/platform-tools/adb"
    assert settings.mcp_enabled is True
    assert settings.vsync_enabled is False
    assert settings.fps_limit == 120
    assert settings.render_only_active_display is False
    assert settings.sync_count == 1
    assert applied == [18.0, 18.0]
    assert applied_display_policy == [False]
    assert len(saved) == 1

    assert dialog.show()
    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    assert renders
    tc_ui_document_destroy(document)
