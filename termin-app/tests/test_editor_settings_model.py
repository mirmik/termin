import pytest

from termin.editor_core.settings_model import EditorSettingsController, EditorSettingsSnapshot


class _Settings:
    def __init__(self):
        self.text_editor = "/usr/bin/editor"
        self.slang_compiler = "/usr/bin/slangc"
        self.font_size = 14.0
        self.font_size_small = 11.0
        self.mcp_enabled = False
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
        )
    )

    assert saved.text_editor == "/opt/code"
    assert settings.text_editor == "/opt/code"
    assert settings.slang_compiler == "/opt/slangc"
    assert settings.font_size == 18.0
    assert settings.font_size_small == 12.0
    assert settings.mcp_enabled is True
    assert settings.sync_count == 1

    with pytest.raises(ValueError, match="8..32"):
        controller.save(
            EditorSettingsSnapshot("", "", 40.0, 11.0, False)
        )
    assert settings.sync_count == 1
