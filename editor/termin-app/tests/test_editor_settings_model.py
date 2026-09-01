from dataclasses import replace
import os
from pathlib import Path

import pytest
from termin.base import Settings

from termin.project_build import ToolchainContext
from termin.editor_core.settings import EditorSettings
from termin.editor_core.settings_model import EditorSettingsController, EditorSettingsSnapshot


class _Settings:
    def __init__(self):
        self.text_editor = "/usr/bin/editor"
        self.slang_compiler = "/usr/bin/slangc"
        self.build_sdk_root = ""
        self.build_termin_root = ""
        self.build_android_sdk_root = ""
        self.build_android_home = ""
        self.build_android_ndk_root = ""
        self.build_java_home = ""
        self.build_shader_compiler = ""
        self.build_fxc = ""
        self.build_android_script = ""
        self.build_quest_openxr_script = ""
        self.build_gradle = "/opt/gradle/bin/gradle"
        self.build_adb = ""
        self.font_size = 14.0
        self.font_size_small = 11.0
        self.mcp_enabled = False
        self.vsync_enabled = True
        self.fps_limit = 60
        self.render_only_active_display = True
        self.sync_count = 0

    def get_text_editor(self):
        return self.text_editor

    def set_text_editor(self, value):
        self.text_editor = value or ""

    def get_slang_compiler(self):
        return self.slang_compiler

    def set_slang_compiler(self, value):
        self.slang_compiler = value or ""

    def get_build_sdk_root(self):
        return self.build_sdk_root

    def set_build_sdk_root(self, value):
        self.build_sdk_root = value or ""

    def get_build_termin_root(self):
        return self.build_termin_root

    def set_build_termin_root(self, value):
        self.build_termin_root = value or ""

    def get_build_android_sdk_root(self):
        return self.build_android_sdk_root

    def set_build_android_sdk_root(self, value):
        self.build_android_sdk_root = value or ""

    def get_build_android_home(self):
        return self.build_android_home

    def set_build_android_home(self, value):
        self.build_android_home = value or ""

    def get_build_android_ndk_root(self):
        return self.build_android_ndk_root

    def set_build_android_ndk_root(self, value):
        self.build_android_ndk_root = value or ""

    def get_build_java_home(self):
        return self.build_java_home

    def set_build_java_home(self, value):
        self.build_java_home = value or ""

    def get_build_shader_compiler(self):
        return self.build_shader_compiler

    def set_build_shader_compiler(self, value):
        self.build_shader_compiler = value or ""

    def get_build_fxc(self):
        return self.build_fxc

    def set_build_fxc(self, value):
        self.build_fxc = value or ""

    def get_build_android_script(self):
        return self.build_android_script

    def set_build_android_script(self, value):
        self.build_android_script = value or ""

    def get_build_quest_openxr_script(self):
        return self.build_quest_openxr_script

    def set_build_quest_openxr_script(self, value):
        self.build_quest_openxr_script = value or ""

    def get_build_gradle(self):
        return self.build_gradle

    def set_build_gradle(self, value):
        self.build_gradle = value or ""

    def get_build_adb(self):
        return self.build_adb

    def set_build_adb(self, value):
        self.build_adb = value or ""

    def get_font_size(self):
        return self.font_size

    def set_font_size(self, value):
        self.font_size = value

    def get_font_size_small(self):
        return self.font_size_small

    def set_font_size_small(self, value):
        self.font_size_small = value

    def get_mcp_server_enabled(self):
        return self.mcp_enabled

    def set_mcp_server_enabled(self, value):
        self.mcp_enabled = value

    def get_vsync_enabled(self):
        return self.vsync_enabled

    def set_vsync_enabled(self, value):
        self.vsync_enabled = value

    def get_fps_limit(self):
        return self.fps_limit

    def set_fps_limit(self, value):
        self.fps_limit = value

    def get_render_only_active_display(self):
        return self.render_only_active_display

    def set_render_only_active_display(self, value):
        self.render_only_active_display = value

    def sync(self):
        self.sync_count += 1


def test_editor_settings_use_common_config_and_migrate_legacy_values_once(
    tmp_path,
) -> None:
    common_path = tmp_path / "termin/settings.json"
    legacy_path = tmp_path / "TerminEditor/settings.json"
    common = Settings(str(common_path), True)
    legacy = Settings(str(legacy_path), True)
    common.set(EditorSettings.KEY_FONT_SIZE, 20)
    legacy.set(EditorSettings.KEY_FONT_SIZE, 16)
    legacy.set(EditorSettings.KEY_TEXT_EDITOR, "/legacy/editor")
    legacy.set(EditorSettings.KEY_BUILD_GRADLE, "/legacy/gradle")

    settings = EditorSettings(common, legacy)

    assert settings.path == common_path
    assert settings.get_font_size() == 20
    assert settings.get_text_editor() == "/legacy/editor"
    assert settings.get_build_gradle() == "/legacy/gradle"
    assert common.get(EditorSettings.KEY_LEGACY_MIGRATION, False) is True

    legacy.set(EditorSettings.KEY_TEXT_EDITOR, "/changed/legacy/editor")
    reloaded = EditorSettings(
        Settings(str(common_path), True),
        Settings(str(legacy_path), True),
    )

    assert reloaded.get_text_editor() == "/legacy/editor"


@pytest.mark.skipif(os.name == "nt", reason="Linux XDG config path contract")
def test_editor_settings_default_to_lowercase_termin_config(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    settings = EditorSettings(migrate_legacy=False)

    assert settings.path == tmp_path / "termin/settings.json"


def test_editor_settings_controller_validates_normalizes_and_persists():
    settings = _Settings()
    controller = EditorSettingsController(settings)

    assert controller.load().text_editor == "/usr/bin/editor"
    saved = controller.save(
        EditorSettingsSnapshot(
            text_editor="  /opt/code  ",
            slang_compiler="  /opt/slangc  ",
            build_sdk_root=" /opt/termin/sdk ",
            build_termin_root=" /src/termin ",
            build_android_sdk_root=" /opt/termin/sdk/android ",
            build_android_home=" /opt/android/sdk ",
            build_android_ndk_root=" /opt/android/ndk/27.2.12479018 ",
            build_java_home=" /opt/jdk-17 ",
            build_shader_compiler=" /opt/termin/sdk/bin/termin_shaderc ",
            build_fxc="",
            build_android_script=" /src/termin/build-android-apk.sh ",
            build_quest_openxr_script="",
            build_gradle=" /opt/gradle-8/bin/gradle ",
            build_adb=" /opt/android/platform-tools/adb ",
            font_size=18.0,
            font_size_small=12.0,
            mcp_server_enabled=True,
            vsync_enabled=False,
            fps_limit=144,
            render_only_active_display=False,
        )
    )

    assert saved.text_editor == "/opt/code"
    assert settings.text_editor == "/opt/code"
    assert settings.slang_compiler == "/opt/slangc"
    assert settings.build_sdk_root == "/opt/termin/sdk"
    assert settings.build_android_home == "/opt/android/sdk"
    assert settings.build_android_ndk_root == "/opt/android/ndk/27.2.12479018"
    assert settings.build_java_home == "/opt/jdk-17"
    assert settings.build_gradle == "/opt/gradle-8/bin/gradle"
    assert settings.build_adb == "/opt/android/platform-tools/adb"
    assert settings.font_size == 18.0
    assert settings.font_size_small == 12.0
    assert settings.mcp_enabled is True
    assert settings.vsync_enabled is False
    assert settings.fps_limit == 144
    assert settings.render_only_active_display is False
    assert settings.sync_count == 1
    assert controller.toolchain_context() == ToolchainContext(
        sdk_root=Path("/opt/termin/sdk"),
        termin_root=Path("/src/termin"),
        android_sdk_root=Path("/opt/termin/sdk/android"),
        android_home=Path("/opt/android/sdk"),
        android_ndk_root=Path("/opt/android/ndk/27.2.12479018"),
        java_home=Path("/opt/jdk-17"),
        shader_compiler=Path("/opt/termin/sdk/bin/termin_shaderc"),
        android_build_script=Path("/src/termin/build-android-apk.sh"),
        gradle=Path("/opt/gradle-8/bin/gradle"),
        adb=Path("/opt/android/platform-tools/adb"),
    )

    with pytest.raises(ValueError, match="8..32"):
        controller.save(replace(saved, font_size=40.0))
    assert settings.sync_count == 1

    with pytest.raises(ValueError, match="FPS limit"):
        controller.save(replace(saved, fps_limit=60.5))
    assert settings.sync_count == 1
