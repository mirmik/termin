"""Toolkit-neutral editor settings snapshot and persistence controller."""

from __future__ import annotations

from dataclasses import dataclass

from termin.editor_core.settings import EditorSettings


@dataclass(frozen=True)
class EditorSettingsSnapshot:
    text_editor: str
    slang_compiler: str
    font_size: float
    font_size_small: float
    mcp_server_enabled: bool
    vsync_enabled: bool
    fps_limit: int


class EditorSettingsController:
    def __init__(self, settings: EditorSettings | None = None) -> None:
        self._settings = settings or EditorSettings.instance()

    def load(self) -> EditorSettingsSnapshot:
        return EditorSettingsSnapshot(
            text_editor=self._settings.get_text_editor() or "",
            slang_compiler=self._settings.get_slang_compiler() or "",
            font_size=float(self._settings.get_font_size()),
            font_size_small=float(self._settings.get_font_size_small()),
            mcp_server_enabled=self._settings.get_mcp_server_enabled(),
            vsync_enabled=self._settings.get_vsync_enabled(),
            fps_limit=self._settings.get_fps_limit(),
        )

    def save(self, snapshot: EditorSettingsSnapshot) -> EditorSettingsSnapshot:
        validated = self.validate(snapshot)
        self._settings.set_text_editor(validated.text_editor or None)
        self._settings.set_slang_compiler(validated.slang_compiler or None)
        self._settings.set_font_size(validated.font_size)
        self._settings.set_font_size_small(validated.font_size_small)
        self._settings.set_mcp_server_enabled(validated.mcp_server_enabled)
        self._settings.set_vsync_enabled(validated.vsync_enabled)
        self._settings.set_fps_limit(validated.fps_limit)
        self._settings.sync()
        return validated

    @staticmethod
    def validate(snapshot: EditorSettingsSnapshot) -> EditorSettingsSnapshot:
        font_size = float(snapshot.font_size)
        small = float(snapshot.font_size_small)
        if not 8.0 <= font_size <= 32.0:
            raise ValueError("font size must be in range 8..32")
        if not 8.0 <= small <= 24.0:
            raise ValueError("small font size must be in range 8..24")
        fps_limit_value = float(snapshot.fps_limit)
        if not fps_limit_value.is_integer() or not 0.0 <= fps_limit_value <= 1000.0:
            raise ValueError("FPS limit must be zero (Unlimited) or an integer in range 1..1000")
        fps_limit = int(fps_limit_value)
        return EditorSettingsSnapshot(
            text_editor=snapshot.text_editor.strip(),
            slang_compiler=snapshot.slang_compiler.strip(),
            font_size=font_size,
            font_size_small=small,
            mcp_server_enabled=bool(snapshot.mcp_server_enabled),
            vsync_enabled=bool(snapshot.vsync_enabled),
            fps_limit=fps_limit,
        )


__all__ = ["EditorSettingsController", "EditorSettingsSnapshot"]
