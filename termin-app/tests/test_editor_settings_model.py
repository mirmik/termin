import pytest

from termin.editor_core.settings_model import EditorSettingsController, EditorSettingsSnapshot


class _Settings:
    def __init__(self):
        self.text_editor = "/usr/bin/editor"
        self.slang_compiler = "/usr/bin/slangc"
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


def test_editor_settings_controller_validates_normalizes_and_persists():
    settings = _Settings()
    controller = EditorSettingsController(settings)

    assert controller.load().text_editor == "/usr/bin/editor"
    saved = controller.save(
        EditorSettingsSnapshot(
            text_editor="  /opt/code  ",
            slang_compiler="  /opt/slangc  ",
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
    assert settings.font_size == 18.0
    assert settings.font_size_small == 12.0
    assert settings.mcp_enabled is True
    assert settings.vsync_enabled is False
    assert settings.fps_limit == 144
    assert settings.render_only_active_display is False
    assert settings.sync_count == 1

    with pytest.raises(ValueError, match="8..32"):
        controller.save(
            EditorSettingsSnapshot("", "", 40.0, 11.0, False, True, 0, True)
        )
    assert settings.sync_count == 1

    with pytest.raises(ValueError, match="FPS limit"):
        controller.save(
            EditorSettingsSnapshot("", "", 14.0, 11.0, False, True, 60.5, True)
        )
    assert settings.sync_count == 1
